"""Calibration driver contracts and registry."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from roboclaw.embodied.execution.orchestration.runtime.executor import (
        ExecutionContext,
        ProcedureExecutionResult,
    )


ProgressCallback = Callable[[str], Awaitable[None]]


class CalibrationDriver(Protocol):
    """Robot-specific calibration flow driver."""

    id: str

    async def begin(
        self,
        context: ExecutionContext,
        *,
        on_progress: ProgressCallback | None = None,
    ) -> ProcedureExecutionResult:
        """Start or resume calibration preparation for one runtime."""

    async def advance(
        self,
        context: ExecutionContext,
        user_input: str | None = None,
        *,
        on_progress: ProgressCallback | None = None,
    ) -> ProcedureExecutionResult:
        """Advance one interactive calibration flow."""

    def describe(self, context: ExecutionContext) -> ProcedureExecutionResult:
        """Describe the current calibration phase without advancing it."""

    def phase(self, context: ExecutionContext) -> str | None:
        """Return the current in-memory calibration phase for one runtime."""

    def cleanup(self, runtime_id: str) -> None:
        """Clean up any in-memory calibration state for one runtime."""


class CalibrationDriverRegistry:
    """Registry of robot-specific calibration drivers."""

    def __init__(self) -> None:
        self._entries: dict[str, CalibrationDriver] = {}

    def register(self, driver: CalibrationDriver) -> None:
        self._entries[driver.id] = driver

    def get(self, driver_id: str | None) -> CalibrationDriver | None:
        if driver_id is None:
            return None
        return self._entries.get(driver_id)

    def list(self) -> tuple[CalibrationDriver, ...]:
        return tuple(self._entries.values())


_CALIBRATION_DRIVERS = CalibrationDriverRegistry()


def register_calibration_driver(driver: CalibrationDriver) -> None:
    """Register one calibration driver."""

    _CALIBRATION_DRIVERS.register(driver)


def get_calibration_driver(driver_id: str | None) -> CalibrationDriver | None:
    """Resolve one calibration driver by id."""

    return _CALIBRATION_DRIVERS.get(driver_id)


def list_calibration_drivers() -> tuple[CalibrationDriver, ...]:
    """List all calibration drivers."""

    return _CALIBRATION_DRIVERS.list()


__all__ = [
    "CalibrationDriver",
    "CalibrationDriverRegistry",
    "ProgressCallback",
    "get_calibration_driver",
    "list_calibration_drivers",
    "register_calibration_driver",
]
