"""Provider construction helpers shared by CLI and Web runtime."""

from __future__ import annotations

import importlib
import os
from pathlib import Path
from typing import Any

from roboclaw.config import load_config
from roboclaw.config.schema import Config
from roboclaw.providers.azure_openai_provider import AzureOpenAIProvider
from roboclaw.providers.base import GenerationSettings, LLMProvider, LLMResponse
from roboclaw.providers.custom_provider import CustomProvider
from roboclaw.providers.litellm_provider import LiteLLMProvider
from roboclaw.providers.openai_codex_provider import OpenAICodexProvider
from roboclaw.providers.registry import find_by_name


class ProviderConfigurationError(RuntimeError):
    """Raised when the configured provider cannot be used."""

    def __init__(self, message: str, hint: str = ""):
        super().__init__(message)
        self.hint = hint


def build_provider(config: Config) -> LLMProvider:
    """Create the active provider from config or raise ProviderConfigurationError."""
    stub_module = os.environ.get("ROBOCLAW_STUB_LLM")
    if stub_module and os.environ.get("ROBOCLAW_STUB"):
        mod = importlib.import_module(stub_module)
        return mod.create_provider(config)

    model = config.agents.defaults.model
    provider_name = config.get_provider_name(model)
    provider_config = config.get_provider(model)

    if provider_name == "openai_codex" or model.startswith("openai-codex/"):
        provider = OpenAICodexProvider(default_model=model)
    elif provider_name == "custom":
        if not provider_config or not provider_config.api_base:
            raise ProviderConfigurationError(
                "Custom provider requires api_base.",
                "Set the global base URL in the Web Settings page or in providers.custom.api_base.",
            )
        provider = CustomProvider(
            api_key=provider_config.api_key if provider_config else "no-key",
            api_base=provider_config.api_base,
            default_model=model,
        )
    elif provider_name == "azure_openai":
        if not provider_config or not provider_config.api_key or not provider_config.api_base:
            raise ProviderConfigurationError(
                "Azure OpenAI requires api_key and api_base.",
                "Set them in ~/.roboclaw/config.json under providers.azure_openai section.",
            )
        provider = AzureOpenAIProvider(
            api_key=provider_config.api_key,
            api_base=provider_config.api_base,
            default_model=model,
        )
    else:
        spec = find_by_name(provider_name)
        if (
            not model.startswith("bedrock/")
            and not (provider_config and provider_config.api_key)
            and not (spec and (spec.is_oauth or spec.is_local))
        ):
            raise ProviderConfigurationError(
                "No API key configured.",
                "Set one in ~/.roboclaw/config.json under providers section.",
            )
        provider = LiteLLMProvider(
            api_key=provider_config.api_key if provider_config else None,
            api_base=config.get_api_base(model),
            default_model=model,
            extra_headers=provider_config.extra_headers if provider_config else None,
            provider_name=provider_name,
        )

    defaults = config.agents.defaults
    provider.generation = GenerationSettings(
        temperature=defaults.temperature,
        max_tokens=defaults.max_tokens,
        reasoning_effort=defaults.reasoning_effort,
    )
    return provider


class ConfigBackedProvider(LLMProvider):
    """Lazy provider that reloads config so the Web UI can update settings live."""

    def __init__(self, config_path: Path | None = None):
        super().__init__(api_key=None, api_base=None)
        self._config_path = config_path

    def _load(self) -> Config:
        return load_config(self._config_path)

    def _config_error_response(self, exc: ProviderConfigurationError) -> LLMResponse:
        hint = f" {exc.hint}" if exc.hint else ""
        return LLMResponse(
            content=(
                f"Provider is not configured. {exc}{hint} "
                "Open Settings > Provider in the Web UI and save your configuration."
            ),
            finish_reason="error",
        )

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        reasoning_effort: str | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> LLMResponse:
        try:
            provider = build_provider(self._load())
        except ProviderConfigurationError as exc:
            return self._config_error_response(exc)
        return await provider.chat(
            messages=messages,
            tools=tools,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            reasoning_effort=reasoning_effort,
            tool_choice=tool_choice,
        )

    async def chat_with_retry(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: object = LLMProvider._SENTINEL,
        temperature: object = LLMProvider._SENTINEL,
        reasoning_effort: object = LLMProvider._SENTINEL,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> LLMResponse:
        try:
            provider = build_provider(self._load())
        except ProviderConfigurationError as exc:
            return self._config_error_response(exc)
        return await provider.chat_with_retry(
            messages=messages,
            tools=tools,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            reasoning_effort=reasoning_effort,
            tool_choice=tool_choice,
        )

    def get_default_model(self) -> str:
        return self._load().agents.defaults.model
