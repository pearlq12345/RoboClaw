"""RynnRCP deployment routes."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from roboclaw.embodied.deploy.rynnrcp import RynnRCPBridge, RynnRCPSettings

_bridge: RynnRCPBridge | None = None


class RynnRCPSendRequest(BaseModel):
    checkpoint_path: str = ""
    actions: list[list[float]] = Field(default_factory=list)
    robot_type: str = ""
    action_dim: int = 6
    action_chunk_size: int = 20
    interpolation: str = "cubic"
    timestamp_ns: int = 0


def get_bridge() -> RynnRCPBridge:
    global _bridge
    if _bridge is None:
        _bridge = RynnRCPBridge()
    return _bridge


def reset_bridge() -> None:
    global _bridge
    _bridge = None


def register_deploy_rcp_routes(app: FastAPI) -> None:
    @app.post("/deploy/rynnrcp/send")
    async def deploy_rynnrcp_send(body: RynnRCPSendRequest) -> dict[str, Any]:
        bridge = get_bridge()
        settings = bridge.settings
        if body.robot_type and body.robot_type != settings.robot_type:
            raise HTTPException(
                status_code=400,
                detail=(
                    "robot_type does not match configured RynnRCP bridge. "
                    "Restart the bridge with ROBOCLAW_RYNNRCP_ROBOT_TYPE for a different robot."
                ),
            )
        if body.action_dim != settings.action_dim or body.action_chunk_size != settings.action_chunk_size:
            raise HTTPException(
                status_code=400,
                detail=(
                    "action_dim/action_chunk_size must match configured RynnRCP bridge "
                    f"({settings.action_dim}, {settings.action_chunk_size})."
                ),
            )
        if body.interpolation and body.interpolation != settings.interpolation:
            raise HTTPException(
                status_code=400,
                detail="interpolation must match configured RynnRCP bridge.",
            )
        try:
            bridge.send_action_chunk(body.actions, timestamp_ns=body.timestamp_ns)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            "message": "rynnrcp action chunk accepted",
            "enabled": bridge.enabled,
            "checkpoint_path": body.checkpoint_path,
            "robot_type": settings.robot_type,
            "channel": settings.lcm_channel,
            "action_chunk_size": settings.action_chunk_size,
            "action_dim": settings.action_dim,
        }

    @app.get("/deploy/rynnrcp/state")
    async def deploy_rynnrcp_state() -> dict[str, Any]:
        bridge = get_bridge()
        state = await asyncio.to_thread(bridge.request_state)
        return {
            "message": "rynnrcp state request sent",
            "enabled": bridge.enabled,
            "state": state,
        }

    @app.post("/deploy/rynnrcp/go_home")
    async def deploy_rynnrcp_go_home() -> dict[str, Any]:
        bridge = get_bridge()
        bridge.go_home()
        return {
            "message": "rynnrcp go-home request sent",
            "enabled": bridge.enabled,
            "robot_type": bridge.settings.robot_type,
            "channel": bridge.settings.lcm_channel,
        }
