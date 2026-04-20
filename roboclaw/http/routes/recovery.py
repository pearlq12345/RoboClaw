"""Recovery routes for active faults and dashboard self-restart."""

from __future__ import annotations

import asyncio
import os
import sys
from typing import Any

from fastapi import FastAPI
from loguru import logger

from roboclaw.embodied.embodiment.hardware.monitor import HardwareMonitor
from roboclaw.http.recovery import get_recovery_guides_json


def schedule_dashboard_restart(delay_s: float = 0.5) -> None:
    """Restart the current dashboard process in-place after a short delay."""

    async def _restart() -> None:
        await asyncio.sleep(delay_s)
        logger.info("Restarting dashboard process")
        os.execv(sys.executable, [sys.executable, "-m", "roboclaw", *sys.argv[1:]])

    asyncio.create_task(_restart())


def register_recovery_routes(app: FastAPI) -> None:

    @app.get("/api/recovery/guides")
    async def recovery_guides() -> dict[str, Any]:
        return get_recovery_guides_json()

    @app.get("/api/recovery/faults")
    async def recovery_faults() -> dict[str, Any]:
        monitor: HardwareMonitor = app.state.hardware_monitor
        return {"faults": [fault.to_dict() for fault in monitor.active_faults]}

    @app.post("/api/recovery/recheck")
    async def recovery_recheck() -> dict[str, Any]:
        monitor: HardwareMonitor = app.state.hardware_monitor
        faults = monitor.check_hardware()
        return {"faults": [fault.to_dict() for fault in faults]}

    @app.post("/api/recovery/restart-dashboard")
    async def recovery_restart_dashboard() -> dict[str, str]:
        schedule_dashboard_restart()
        return {"status": "restarting"}
