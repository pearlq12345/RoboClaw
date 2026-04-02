"""Unified service layer for all embodied operations.

Every interface (Dashboard, CLI, Agent Tool) calls EmbodiedService.
This is the single coordination point for embodiment locking, hardware
monitor integration, and operation lifecycle.
"""

from __future__ import annotations

from typing import Any

from roboclaw.embodied.engine import StatusCallback
from roboclaw.embodied.hardware_monitor import (
    ArmStatus,
    CameraStatus,
    HardwareMonitor,
    check_arm_status,
    check_camera_status,
)
from roboclaw.embodied.ops.helpers import group_arms
from roboclaw.embodied.service.calibration import CalibrationService
from roboclaw.embodied.service.scanning import ScanningService
from roboclaw.embodied.service.session import SessionService
from roboclaw.embodied.setup import load_setup


def _compute_readiness(
    arms: list[dict[str, Any]],
    arm_statuses: list[ArmStatus],
    camera_statuses: list[CameraStatus],
) -> tuple[bool, list[str]]:
    missing: list[str] = []
    grouped = group_arms(arms)
    if not grouped["followers"]:
        missing.append("No follower arm configured")
    if not grouped["leaders"]:
        missing.append("No leader arm configured")
    for s in arm_statuses:
        if not s.connected:
            missing.append(f"Arm '{s.alias}' is disconnected")
        elif not s.calibrated:
            missing.append(f"Arm '{s.alias}' is not calibrated")
    for s in camera_statuses:
        if not s.connected:
            missing.append(f"Camera '{s.alias}' is disconnected")
    f, l = grouped["followers"], grouped["leaders"]
    if f and l and len(f) != len(l):
        missing.append(f"Follower/leader count mismatch: {len(f)} vs {len(l)}")
    return len(missing) == 0, missing


class EmbodiedService:
    """Single point of control for ALL embodied operations.

    Two-layer mutex:
    - Layer 1: Embodiment lock — physical robot is one resource.
      Owner is a string like "teleop", "recording", "calibrating", "scanning".
    - Layer 2: Monitor coordination — recording_active lifecycle.

    Sub-services:
    - session: teleop/recording via OperationEngine
    - calibration: arm calibration via CalibrationSession
    - scanning: port/camera scanning via HardwareScanner
    """

    def __init__(
        self,
        hardware_monitor: HardwareMonitor | None = None,
        on_state_change: StatusCallback | None = None,
    ) -> None:
        self._monitor = hardware_monitor
        self._embodiment_owner: str = ""

        # Sub-services
        self.session = SessionService(self, external_callback=on_state_change)
        self.calibration = CalibrationService(self)
        self.scanning = ScanningService(self)

    # -- Embodiment lock ------------------------------------------------------

    @property
    def embodiment_busy(self) -> bool:
        return self._embodiment_owner != ""

    @property
    def busy(self) -> bool:
        return self.session.busy or self._embodiment_owner != ""

    @property
    def busy_reason(self) -> str:
        if self.session.busy:
            return self.session.state
        return self._embodiment_owner

    def acquire_embodiment(self, owner: str) -> None:
        if self.busy:
            raise RuntimeError(f"Embodiment busy: {self.busy_reason}")
        self._embodiment_owner = owner

    def release_embodiment(self) -> None:
        self._embodiment_owner = ""

    # -- Delegated: session ---------------------------------------------------

    def get_status(self) -> dict[str, Any]:
        return self.session.get_status()

    async def start_teleop(self, *, fps: int = 30) -> None:
        await self.session.start_teleop(fps=fps)

    async def start_recording(
        self,
        task: str,
        num_episodes: int = 10,
        fps: int = 30,
        episode_time_s: int = 300,
        reset_time_s: int = 10,
    ) -> str:
        return await self.session.start_recording(
            task=task,
            num_episodes=num_episodes,
            fps=fps,
            episode_time_s=episode_time_s,
            reset_time_s=reset_time_s,
        )

    async def stop(self) -> None:
        await self.session.stop()

    async def save_episode(self) -> None:
        await self.session.save_episode()

    async def discard_episode(self) -> None:
        await self.session.discard_episode()

    async def skip_reset(self) -> None:
        await self.session.skip_reset()

    # -- Delegated: calibration -----------------------------------------------

    async def start_calibration(self, arm_alias: str) -> dict[str, Any]:
        return await self.calibration.start(arm_alias)

    def get_calibration_status(self) -> dict[str, Any]:
        return self.calibration.get_status()

    async def set_calibration_homing(self) -> dict[str, Any]:
        return await self.calibration.set_homing()

    async def read_calibration_positions(self) -> dict[str, Any]:
        return await self.calibration.read_positions()

    async def finish_calibration(self) -> dict[str, Any]:
        return await self.calibration.finish()

    async def cancel_calibration(self) -> None:
        await self.calibration.cancel()

    # -- Delegated: scanning --------------------------------------------------

    def scan_ports(self) -> list[dict]:
        return self.scanning.scan_ports()

    def scan_cameras(self) -> list[dict]:
        return self.scanning.scan_cameras()

    def capture_camera_previews(self, output_dir: str) -> list[dict]:
        return self.scanning.capture_camera_previews(output_dir)

    def start_motion_detection(self) -> int:
        return self.scanning.start_motion_detection()

    def poll_motion(self) -> list[dict]:
        return self.scanning.poll_motion()

    def stop_motion_detection(self) -> None:
        self.scanning.stop_motion_detection()

    # -- Hardware status / servo (stays here until queries.py) ----------------

    def get_hardware_status(self) -> dict[str, Any]:
        setup = load_setup()
        arms = setup.get("arms", [])
        cameras = setup.get("cameras", [])
        arm_statuses = [check_arm_status(a) for a in arms]
        camera_statuses = [check_camera_status(c) for c in cameras]
        ready, missing = _compute_readiness(arms, arm_statuses, camera_statuses)
        return {
            "ready": ready,
            "missing": missing,
            "arms": [s.to_dict() for s in arm_statuses],
            "cameras": [s.to_dict() for s in camera_statuses],
            "session_busy": self.session.busy,
        }

    def read_servo_positions(self) -> dict[str, Any]:
        if self.busy:
            return {"error": "busy", "arms": {}}
        from roboclaw.embodied.motors import read_servo_positions
        return read_servo_positions()

    # -- Shutdown -------------------------------------------------------------

    async def shutdown(self) -> None:
        if self.session.busy:
            await self.session.stop()
        if self.calibration.active:
            await self.calibration.cancel()
        if self._monitor is not None:
            self._monitor.set_recording_active(False)
