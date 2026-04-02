"""Setup wizard REST API routes for hardware discovery and configuration."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from roboclaw.embodied.engine import HardwareScanner
from roboclaw.embodied.setup import (
    load_setup,
    remove_arm,
    remove_camera,
    rename_arm,
    set_arm,
    set_camera,
)


# Request models


class AddArmRequest(BaseModel):
    alias: str
    arm_type: str
    port_id: str


class AddCameraRequest(BaseModel):
    alias: str
    camera_index: int


class RenameRequest(BaseModel):
    new_alias: str


def register_setup_routes(app: FastAPI) -> None:
    """Register setup wizard API endpoints."""

    scanner = HardwareScanner()
    app.state.setup_wizard = scanner

    def _get_service():
        return getattr(app.state, "embodied_service", None)

    def _acquire_hardware(reason: str) -> None:
        svc = _get_service()
        if svc is not None:
            try:
                svc.acquire_hardware(reason)
            except RuntimeError as exc:
                raise HTTPException(409, str(exc)) from exc

    def _release_hardware() -> None:
        svc = _get_service()
        if svc is not None:
            svc.release_hardware()

    @app.post("/api/dashboard/setup/scan")
    async def setup_scan() -> dict[str, Any]:
        _acquire_hardware("scanning")
        try:
            ports = await asyncio.to_thread(scanner.scan_ports)
            cameras = await asyncio.to_thread(scanner.scan_cameras_list)
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from exc
        finally:
            _release_hardware()
        scanner.stop_motion_detection()
        return {"ports": ports, "cameras": cameras}

    @app.post("/api/dashboard/setup/camera-previews")
    async def setup_camera_previews() -> list[dict]:
        _acquire_hardware("camera-preview")
        try:
            output_dir = str(Path("/tmp/roboclaw-camera-previews"))
            previews = await asyncio.to_thread(
                scanner.capture_camera_previews, output_dir,
            )
        except RuntimeError as exc:
            raise HTTPException(400, str(exc)) from exc
        finally:
            _release_hardware()
        return previews

    @app.get("/api/dashboard/setup/camera-preview/{index}")
    async def setup_camera_preview_image(index: int):
        from fastapi.responses import FileResponse

        preview_dir = Path("/tmp/roboclaw-camera-previews")
        for f in preview_dir.glob(f"{index:02d}_*.jpg"):
            return FileResponse(str(f), media_type="image/jpeg")
        raise HTTPException(404, f"Preview not found for camera index {index}")

    @app.post("/api/dashboard/setup/motion/start")
    async def motion_start() -> dict[str, Any]:
        _acquire_hardware("motion-detection")
        try:
            port_count = await asyncio.to_thread(scanner.start_motion_detection)
        except RuntimeError as exc:
            _release_hardware()
            raise HTTPException(400, str(exc)) from exc
        except Exception:
            _release_hardware()
            raise
        return {"status": "watching", "port_count": port_count}

    @app.get("/api/dashboard/setup/motion/poll")
    async def motion_poll() -> dict[str, Any]:
        if not scanner.motion_active:
            raise HTTPException(400, "Motion detection not started")
        results = await asyncio.to_thread(scanner.poll_motion)
        return {"ports": results}

    @app.post("/api/dashboard/setup/motion/stop")
    async def motion_stop() -> dict[str, str]:
        scanner.stop_motion_detection()
        _release_hardware()
        return {"status": "stopped"}

    @app.post("/api/dashboard/setup/arm")
    async def setup_add_arm(body: AddArmRequest) -> dict[str, Any]:
        await asyncio.to_thread(set_arm, body.alias, body.arm_type, body.port_id)
        return {"status": "added", "alias": body.alias}

    @app.delete("/api/dashboard/setup/arm/{alias}")
    async def setup_remove_arm(alias: str) -> dict[str, str]:
        await asyncio.to_thread(remove_arm, alias)
        return {"status": "removed", "alias": alias}

    @app.patch("/api/dashboard/setup/arm/{alias}/rename")
    async def setup_rename_arm(alias: str, body: RenameRequest) -> dict[str, str]:
        await asyncio.to_thread(rename_arm, alias, body.new_alias)
        return {"status": "renamed", "old": alias, "new": body.new_alias}

    @app.post("/api/dashboard/setup/camera")
    async def setup_add_camera(body: AddCameraRequest) -> dict[str, Any]:
        await asyncio.to_thread(set_camera, body.alias, body.camera_index)
        return {"status": "added", "alias": body.alias}

    @app.delete("/api/dashboard/setup/camera/{alias}")
    async def setup_remove_camera(alias: str) -> dict[str, str]:
        await asyncio.to_thread(remove_camera, alias)
        return {"status": "removed", "alias": alias}

    @app.get("/api/dashboard/setup/current")
    async def setup_current() -> dict[str, Any]:
        setup = load_setup()
        return {
            "arms": setup.get("arms", []),
            "cameras": setup.get("cameras", []),
            "hands": setup.get("hands", []),
        }
