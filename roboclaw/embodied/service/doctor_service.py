"""DoctorService - embodied environment health checks."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from roboclaw.embodied.manifest import Manifest
    from roboclaw.embodied.service import EmbodiedService


class DoctorService:
    def __init__(self, parent: EmbodiedService):
        self._parent = parent

    async def check(
        self,
        manifest: Manifest,
        kwargs: dict[str, Any],
        tty_handoff: Any,
    ) -> str:
        from roboclaw.embodied.engine.command_builder import ArmCommandBuilder
        from roboclaw.embodied.runner import LocalLeRobotRunner

        result = await LocalLeRobotRunner().run(ArmCommandBuilder().doctor())
        returncode, stdout, stderr = result
        if returncode != 0:
            output = f"Command failed (exit {returncode}).\nstdout: {stdout}\nstderr: {stderr}"
        else:
            output = stdout or "Done."
        return output + f"\n\nCurrent setup:\n{json.dumps(manifest.snapshot, indent=2, ensure_ascii=False)}"
