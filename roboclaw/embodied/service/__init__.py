"""Unified service layer for all embodied operations.

Every interface (Dashboard, CLI, Agent Tool) calls EmbodiedService.
This is the single coordination point for embodiment locking, hardware
monitor integration, and operation lifecycle.
"""

from __future__ import annotations

import threading
from typing import Any

from roboclaw.embodied.events import EventBus
from roboclaw.embodied.hardware.monitor import HardwareMonitor
from roboclaw.embodied.manifest import Manifest
from roboclaw.embodied.service.calibration import CalibrationService
from roboclaw.embodied.service.calibration_session import CalibrationSession as CalibrationCLI
from roboclaw.embodied.service.config import ConfigService
from roboclaw.embodied.service.doctor_service import DoctorService
from roboclaw.embodied.service.hand_session import HandSession
from roboclaw.embodied.service.infer_session import InferSession
from roboclaw.embodied.service.queries import QueryService
from roboclaw.embodied.service.record_session import RecordSession
from roboclaw.embodied.service.replay_session import ReplaySession
from roboclaw.embodied.service.session import SessionService
from roboclaw.embodied.service.setup_session import SetupSession
from roboclaw.embodied.service.teleop_session import TeleopSession
from roboclaw.embodied.service.train_session import TrainSession


class EmbodimentBusyError(RuntimeError):
    """Raised when the embodiment lock cannot be acquired."""


class EmbodiedService:
    """Single point of control for ALL embodied operations.

    Two-layer mutex:
    - Layer 1: Embodiment lock — physical robot is one resource.
      Owner is a string like "teleop", "recording", "calibrating", "scanning".
    - Layer 2: Monitor coordination — recording_active lifecycle.

    Sub-services:
    - session: teleop/recording via OperationEngine
    - calibration: arm calibration via CalibrationSession
    - setup: hardware setup workflow via SetupSession
    """

    def __init__(
        self,
        hardware_monitor: HardwareMonitor | None = None,
        event_bus: EventBus | None = None,
        manifest: Manifest | None = None,
    ) -> None:
        self._monitor = hardware_monitor
        self._bus = event_bus or EventBus()
        self.manifest = manifest or Manifest(event_bus=self._bus)
        self._lock = threading.Lock()
        self._embodiment_owner: str = ""

        # Sub-services
        self.session = SessionService(self, event_bus=self._bus)
        self.calibration = CalibrationService(self, event_bus=self._bus)
        self.setup = SetupSession(self)
        self.config = ConfigService(self)
        self.queries = QueryService(self)
        self.teleop = TeleopSession(self)
        self.record = RecordSession(self)
        self.replay = ReplaySession(self)
        self.train = TrainSession(self)
        self.infer = InferSession(self)
        self.hand = HandSession(self)
        self.doctor = DoctorService(self)
        self.calibration_session = CalibrationCLI(self)

    @property
    def event_bus(self) -> EventBus:
        return self._bus

    # -- Embodiment lock ------------------------------------------------------

    @property
    def embodiment_busy(self) -> bool:
        with self._lock:
            return self._embodiment_owner != ""

    @property
    def busy(self) -> bool:
        with self._lock:
            return self.session.busy or self._embodiment_owner != ""

    @property
    def busy_reason(self) -> str:
        with self._lock:
            if self.session.busy:
                return self.session.state
            return self._embodiment_owner

    def acquire_embodiment(self, owner: str) -> None:
        with self._lock:
            if self.session.busy or self._embodiment_owner:
                reason = self.session.state if self.session.busy else self._embodiment_owner
                raise EmbodimentBusyError(f"Embodiment busy: {reason}")
            self._embodiment_owner = owner

    def release_embodiment(self, owner: str = "") -> None:
        """Release the embodiment lock. If owner is specified, only release if it matches."""
        with self._lock:
            if owner and self._embodiment_owner != owner:
                return
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

    # -- Setup is accessed via service.setup directly --------------------------

    # -- Delegated: queries ----------------------------------------------------

    def get_hardware_status(self) -> dict[str, Any]:
        return self.queries.get_hardware_status()

    def read_servo_positions(self) -> dict[str, Any]:
        return self.queries.read_servo_positions()

    # -- Shutdown -------------------------------------------------------------

    async def shutdown(self) -> None:
        if self.session.busy:
            await self.session.stop()
        if self.calibration.active:
            await self.calibration.cancel()
        if self.setup.motion_active:
            self.setup.stop_motion_detection()
        if self._monitor is not None:
            self._monitor.set_recording_active(False)
