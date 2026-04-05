"""TeleopSession — interactive teleoperation driven by TtySession.

Implements the polling interaction protocol: status_line, on_key, is_done.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from roboclaw.embodied.manifest import Manifest
    from roboclaw.embodied.service import EmbodiedService


class TeleopSession:
    def __init__(self, parent: EmbodiedService) -> None:
        self._parent = parent
        self._kwargs: dict[str, Any] = {}

    async def teleoperate(
        self,
        manifest: Manifest,
        kwargs: dict[str, Any],
        tty_handoff: Any,
    ) -> str:
        self._kwargs = kwargs
        if tty_handoff:
            from roboclaw.embodied.adapters.tty import TtySession

            return await TtySession(tty_handoff).run(self)
        return "This action requires a local terminal."

    def interaction_spec(self):
        from roboclaw.embodied.adapters.protocol import PollingSpec

        return PollingSpec(label="lerobot-teleoperate")

    async def start(self) -> None:
        await self._parent.start_teleop(fps=self._kwargs.get("fps", 30))
        print("Teleoperating... Press Ctrl+C to stop.\n")

    def status_line(self) -> str:
        status = self._parent.get_status()
        state = status.get("state", "idle")
        if state == "idle":
            return "  idle"
        if state == "preparing":
            return "  preparing..."
        elapsed = status.get("elapsed_seconds", 0)
        return f"  teleoperating  | {elapsed:.0f}s"

    async def on_key(self, key: str) -> None:
        if key in ("ctrl_c", "esc"):
            await self._parent.stop()

    def is_done(self) -> bool:
        return not self._parent.busy

    def result(self) -> str:
        status = self._parent.get_status()
        error = status.get("error", "")
        if error:
            return f"Teleoperation failed: {error}"
        return "Teleoperation finished."

    async def stop(self) -> None:
        if self._parent.busy:
            await self._parent.stop()
