"""Hardware status and servo position routes."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from roboclaw.embodied.service import EmbodiedService
from roboclaw.embodied.embodiment.hardware.scan import capture_named_camera_frames


HARDWARE_PREVIEW_DIR = Path("/tmp/roboclaw-camera-previews/hardware")


def register_hardware_routes(app: FastAPI, service: EmbodiedService) -> None:

    @app.get("/api/hardware/status")
    async def hardware_status() -> dict[str, Any]:
        return service.get_hardware_status()

    @app.post("/api/hardware/previews")
    async def hardware_previews() -> list[dict[str, Any]]:
        named_cameras = [
            (camera.alias, camera.interface)
            for camera in service.manifest.cameras
        ]
        try:
            previews = await asyncio.to_thread(
                capture_named_camera_frames,
                named_cameras,
                str(HARDWARE_PREVIEW_DIR),
            )
        except RuntimeError as exc:
            raise HTTPException(400, str(exc)) from exc
        return [
            {
                **preview,
                "preview_url": f"/api/hardware/previews/by-key/{preview['preview_key']}",
            }
            for preview in previews
        ]

    @app.get("/api/hardware/previews/by-key/{preview_key}")
    async def hardware_preview_image(preview_key: str):
        preview_path = HARDWARE_PREVIEW_DIR / f"{preview_key}.jpg"
        if preview_path.exists():
            return FileResponse(
                str(preview_path),
                media_type="image/jpeg",
                headers={"Cache-Control": "no-store"},
            )
        raise HTTPException(404, f"Preview not found for key {preview_key}")

    @app.get("/api/hardware/servos")
    async def servo_positions() -> dict[str, Any]:
        return await asyncio.to_thread(service.read_servo_positions)
