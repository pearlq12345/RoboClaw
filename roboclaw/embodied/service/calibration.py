"""Calibration sub-service: arm calibration lifecycle."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from roboclaw.embodied.engine import CalibrationSession
from roboclaw.embodied.port_lock import port_locks
from roboclaw.embodied.setup import load_setup, mark_arm_calibrated

if TYPE_CHECKING:
    from roboclaw.embodied.service import EmbodiedService


def _find_arm(setup: dict, alias: str) -> dict:
    for arm in setup.get("arms", []):
        if arm.get("alias") == alias:
            return arm
    raise RuntimeError(f"Arm '{alias}' not found in setup.")


class CalibrationService:
    """Manages arm calibration sessions with port-lock coordination."""

    def __init__(self, parent: EmbodiedService) -> None:
        self._parent = parent
        self._session: CalibrationSession | None = None
        self._arm_alias: str = ""
        self._port_cm: Any = None

    async def start(self, arm_alias: str) -> dict[str, Any]:
        """Start calibrating an arm. Acquires embodiment lock + port lock."""
        self._parent.acquire_embodiment("calibrating")
        setup = load_setup()
        arm = _find_arm(setup, arm_alias)
        port = arm.get("port", "")
        if port:
            self._port_cm = port_locks.acquire(port)
            await self._port_cm.__aenter__()

        session = CalibrationSession(arm)
        try:
            await asyncio.to_thread(session.connect)
        except Exception:
            await self._cleanup()
            raise

        self._session = session
        self._arm_alias = arm_alias
        return {"state": session.state, "arm_alias": arm_alias}

    def get_status(self) -> dict[str, Any]:
        if self._session is None:
            return {"state": "idle", "arm_alias": ""}
        return {"state": self._session.state, "arm_alias": self._arm_alias}

    async def set_homing(self) -> dict[str, Any]:
        self._require_session()
        offsets = await asyncio.to_thread(self._session.set_homing)
        return {"state": self._session.state, "homing_offsets": offsets}

    async def read_positions(self) -> dict[str, Any]:
        self._require_session()
        if self._session.state != "recording":
            raise RuntimeError(f"Not recording (state={self._session.state})")
        snapshot = await asyncio.to_thread(self._session.read_range_positions)
        return {
            "positions": snapshot.positions,
            "mins": snapshot.mins,
            "maxes": snapshot.maxes,
        }

    async def finish(self) -> dict[str, Any]:
        self._require_session()
        calibration = await asyncio.to_thread(self._session.finish)
        mark_arm_calibrated(self._arm_alias)
        await self._cleanup()
        return {"state": "done", "calibration": calibration}

    async def cancel(self) -> None:
        if self._session is not None:
            await asyncio.to_thread(self._session.cancel)
        await self._cleanup()

    @property
    def active(self) -> bool:
        return self._session is not None

    def _require_session(self) -> None:
        if self._session is None:
            raise RuntimeError("No calibration session active.")

    async def _cleanup(self) -> None:
        if self._port_cm is not None:
            await self._port_cm.__aexit__(None, None, None)
            self._port_cm = None
        if self._session is not None:
            await asyncio.to_thread(self._session.disconnect)
            self._session = None
        self._arm_alias = ""
        self._parent.release_embodiment()
