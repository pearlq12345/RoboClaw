"""FastAPI server for the RoboClaw web chat UI."""

from __future__ import annotations

import asyncio
import json
from contextlib import suppress
from typing import Any

from fastapi import Body
import httpx
from loguru import logger

from roboclaw.agent.loop import AgentLoop
from roboclaw.bus.queue import MessageBus
from roboclaw.channels.web import WebChannel
from roboclaw.cli.commands import _load_runtime_config
from roboclaw.config.loader import get_config_path, load_config, save_config
from roboclaw.providers.base import GenerationSettings
from roboclaw.providers.factory import ConfigBackedProvider
from roboclaw.providers.registry import PROVIDERS
from roboclaw.session.manager import SessionManager
from roboclaw.utils.helpers import sync_workspace_templates


def _merge_web_config(raw: Any) -> dict[str, Any]:
    defaults = WebChannel.default_config()
    if raw is None:
        return defaults
    if isinstance(raw, dict):
        return {**defaults, **raw}

    values = defaults.copy()
    for key in defaults:
        values[key] = getattr(raw, key, defaults[key])
    return values


def _provider_options(config: Any) -> list[dict[str, Any]]:
    options = []
    for spec in PROVIDERS:
        provider_config = getattr(config.providers, spec.name, None)
        api_key = provider_config.api_key if provider_config and provider_config.api_key else ""
        if spec.is_oauth:
            configured = False
        elif spec.name == "azure_openai":
            configured = bool(provider_config and provider_config.api_key and provider_config.api_base)
        elif spec.is_local or spec.name == "custom":
            configured = bool(provider_config and provider_config.api_base)
        else:
            configured = bool(provider_config and provider_config.api_key)
        options.append(
            {
                "name": spec.name,
                "label": spec.label,
                "oauth": spec.is_oauth,
                "local": spec.is_local,
                "direct": spec.is_direct,
                "configured": configured,
                "api_base": provider_config.api_base if provider_config and provider_config.api_base else "",
                "has_api_key": bool(api_key),
                "masked_api_key": (
                    f"{api_key[:6]}...{api_key[-4:]}" if len(api_key) >= 10 else ("已保存" if api_key else "")
                ),
                "extra_headers": provider_config.extra_headers if provider_config and provider_config.extra_headers else {},
            }
        )
    return options


def _provider_status_payload(config: Any) -> dict[str, Any]:
    providers = _provider_options(config)
    active_provider = config.get_provider_name(config.agents.defaults.model)
    active_option = next((item for item in providers if item["name"] == active_provider), None)
    custom_option = next((item for item in providers if item["name"] == "custom"), None)
    return {
        "default_model": config.agents.defaults.model,
        "default_provider": config.agents.defaults.provider,
        "active_provider": active_provider,
        "active_provider_configured": bool(active_option and active_option["configured"]),
        "custom_provider": custom_option or {
            "name": "custom",
            "label": "Custom",
            "configured": False,
            "api_base": "",
            "has_api_key": False,
            "masked_api_key": "",
            "extra_headers": {},
        },
        "providers": providers,
    }


async def _discover_custom_model(api_base: str, api_key: str | None) -> str | None:
    if not api_base:
        return None
    url = api_base.rstrip("/") + "/models"
    headers: dict[str, str] = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        logger.warning("Failed to auto-discover models from {}: {}", url, exc)
        return None

    data = payload.get("data", [])
    if not isinstance(data, list):
        return None
    for item in data:
        if isinstance(item, dict) and item.get("id"):
            return str(item["id"])
    return None


def _refresh_agent_defaults(agent: AgentLoop, config: Any) -> None:
    agent.model = config.agents.defaults.model
    agent.provider.generation = GenerationSettings(
        temperature=config.agents.defaults.temperature,
        max_tokens=config.agents.defaults.max_tokens,
        reasoning_effort=config.agents.defaults.reasoning_effort,
    )
    agent.memory_consolidator.model = config.agents.defaults.model
    agent.subagents.model = config.agents.defaults.model


def _register_system_routes(app, agent: AgentLoop) -> None:
    @app.get("/api/system/provider-status")
    async def provider_status() -> dict[str, Any]:
        config = load_config(get_config_path())
        return _provider_status_payload(config)

    @app.get("/api/system/runtime-info")
    async def runtime_info() -> dict[str, Any]:
        return {
            "web_runtime_version": 2,
            "features": {
                "provider_settings": True,
                "chat_session_bootstrap": True,
                "dict_allow_from": True,
            },
        }

    @app.get("/api/system/provider-config")
    async def provider_config() -> dict[str, Any]:
        config = load_config(get_config_path())
        return _provider_status_payload(config)

    @app.post("/api/system/provider-config")
    async def save_provider_config(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        config = load_config(get_config_path())
        section = config.providers.custom

        if payload.get("clear_api_key"):
            section.api_key = ""

        api_key = payload.get("api_key")
        if isinstance(api_key, str) and api_key.strip():
            section.api_key = api_key.strip()

        api_base = payload.get("api_base")
        if isinstance(api_base, str):
            section.api_base = api_base.strip() or None

        extra_headers = payload.get("extra_headers")
        if isinstance(extra_headers, str):
            try:
                extra_headers = json.loads(extra_headers) if extra_headers.strip() else {}
            except json.JSONDecodeError:
                return {"status": "error", "message": "extra_headers must be valid JSON."}
        if isinstance(extra_headers, dict):
            section.extra_headers = extra_headers or None

        discovered_model = await _discover_custom_model(section.api_base or "", section.api_key or None)
        if discovered_model:
            config.agents.defaults.model = discovered_model
        config.agents.defaults.provider = "custom" if section.api_base else "auto"

        save_config(config, get_config_path())
        _refresh_agent_defaults(agent, config)
        return {"status": "ok", **_provider_status_payload(config)}


def create_app(
    *,
    config_path: str | None = None,
    workspace: str | None = None,
    host: str | None = None,
    port: int | None = None,
):
    """Build the FastAPI app plus its agent runtime hooks."""
    config = _load_runtime_config(config_path, workspace)
    sync_workspace_templates(config.workspace_path)

    web_config = _merge_web_config(getattr(config.channels, "web", None))
    if host is not None:
        web_config["host"] = host
    if port is not None:
        web_config["port"] = port

    provider = ConfigBackedProvider(get_config_path())
    bus = MessageBus()
    sessions = SessionManager(config.workspace_path)
    channel = WebChannel(web_config, bus, session_manager=sessions)
    agent = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=config.workspace_path,
        model=config.agents.defaults.model,
        max_iterations=config.agents.defaults.max_tool_iterations,
        context_window_tokens=config.agents.defaults.context_window_tokens,
        web_search_config=config.tools.web.search,
        web_proxy=config.tools.web.proxy or None,
        exec_config=config.tools.exec,
        restrict_to_workspace=config.tools.restrict_to_workspace,
        session_manager=sessions,
        mcp_servers=config.tools.mcp_servers,
        channels_config=config.channels,
    )
    _refresh_agent_defaults(agent, config)

    app = channel.app
    _register_system_routes(app, agent)
    app.state.web_host = web_config["host"]
    app.state.web_port = web_config["port"]
    app.state.agent = agent
    app.state.channel = channel
    app.state.dispatch_task = None
    app.state.agent_task = None
    app.state.channel_task = None

    async def _dispatch_outbound() -> None:
        while True:
            try:
                msg = await asyncio.wait_for(bus.consume_outbound(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            if msg.channel != channel.name:
                logger.debug("Dropping outbound message for unsupported web-runtime channel {}", msg.channel)
                continue
            if msg.metadata.get("_progress"):
                if msg.metadata.get("_tool_hint") and not config.channels.send_tool_hints:
                    continue
                if not msg.metadata.get("_tool_hint") and not config.channels.send_progress:
                    continue
            await channel.send(msg)

    @app.on_event("startup")
    async def _startup() -> None:
        app.state.agent_task = asyncio.create_task(agent.run(), name="roboclaw-web-agent")
        app.state.channel_task = asyncio.create_task(channel.start(), name="roboclaw-web-channel")
        app.state.dispatch_task = asyncio.create_task(_dispatch_outbound(), name="roboclaw-web-dispatch")

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        agent.stop()
        await channel.stop()

        for task_name in ("dispatch_task", "channel_task", "agent_task"):
            task = getattr(app.state, task_name, None)
            if task is None:
                continue
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

        await agent.close_mcp()

    return app


def main(
    *,
    config_path: str | None = None,
    workspace: str | None = None,
    host: str | None = None,
    port: int | None = None,
) -> None:
    """Run the web server with uvicorn."""
    import uvicorn

    app = create_app(config_path=config_path, workspace=workspace, host=host, port=port)
    logger.info("Starting RoboClaw Web UI at http://{}:{}", app.state.web_host, app.state.web_port)
    uvicorn.run(app, host=app.state.web_host, port=app.state.web_port, log_level="info")
