"""RecordSession — interactive dataset recording driven by TtySession.

Implements the polling interaction protocol with additional save/discard keys.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from roboclaw.embodied.engine.helpers import _validate_dataset_name

if TYPE_CHECKING:
    from roboclaw.embodied.manifest import Manifest
    from roboclaw.embodied.service import EmbodiedService


class RecordSession:
    def __init__(self, parent: EmbodiedService) -> None:
        self._parent = parent
        self._kwargs: dict[str, Any] = {}

    async def record(
        self,
        manifest: Manifest,
        kwargs: dict[str, Any],
        tty_handoff: Any,
    ) -> str:
        dataset_name = kwargs.get("dataset_name")
        if dataset_name:
            error = _validate_dataset_name(dataset_name)
            if error:
                return error
        self._kwargs = kwargs
        if tty_handoff:
            from roboclaw.embodied.adapters.tty import TtySession

            return await TtySession(tty_handoff).run(self)
        return "This action requires a local terminal."

    def interaction_spec(self):
        from roboclaw.embodied.adapters.protocol import PollingSpec

        return PollingSpec(label="lerobot-record")

    async def start(self) -> None:
        dataset_name = await self._parent.start_recording(
            task=self._kwargs.get("task", "default_task"),
            num_episodes=self._kwargs.get("num_episodes", 10),
            fps=self._kwargs.get("fps", 30),
            episode_time_s=self._kwargs.get("episode_time_s", 300),
            reset_time_s=self._kwargs.get("reset_time_s", 10),
        )
        print(f"Recording -> {dataset_name}")
        print("  -> / <- = save / discard | ESC = stop\n")

    def status_line(self) -> str:
        status = self._parent.get_status()
        state = status.get("state", "idle")
        if state == "idle":
            return "  idle"
        if state == "preparing":
            return "  preparing..."
        if state == "teleoperating":
            elapsed = status.get("elapsed_seconds", 0)
            return f"  teleoperating  | {elapsed:.0f}s"
        phase = status.get("episode_phase", "")
        current = status.get("current_episode", 0)
        target = status.get("target_episodes", 0)
        saved = status.get("saved_episodes", 0)
        return f"  Episode {current}/{target} | Saved: {saved} | {phase or state}"

    async def on_key(self, key: str) -> None:
        if key in ("ctrl_c", "esc"):
            await self._parent.stop()
        elif key == "right":
            await self._parent.save_episode()
        elif key == "left":
            await self._parent.discard_episode()

    def is_done(self) -> bool:
        return not self._parent.busy

    def result(self) -> str:
        status = self._parent.get_status()
        error = status.get("error", "")
        if error:
            return f"Recording failed: {error}"
        saved = status.get("saved_episodes", 0)
        dataset = status.get("dataset")
        if dataset:
            return f"Recording finished. {saved} episodes saved to {dataset}."
        return f"Recording finished. {saved} episodes saved."

    async def stop(self) -> None:
        if self._parent.busy:
            await self._parent.stop()
