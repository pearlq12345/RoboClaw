"""CalibrationSession — CLI calibration entry point (thin wrapper)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from roboclaw.embodied.service.actions import do_calibrate

if TYPE_CHECKING:
    from roboclaw.embodied.manifest import Manifest
    from roboclaw.embodied.service import EmbodiedService


class CalibrationSession:
    """Wraps the CLI interactive calibration flow."""

    def __init__(self, parent: EmbodiedService) -> None:
        self._parent = parent

    async def calibrate(
        self, manifest: Manifest, kwargs: dict[str, Any], tty_handoff: Any,
    ) -> str:
        result = await do_calibrate(manifest, kwargs, tty_handoff)
        self._parent.manifest.reload()
        return result
