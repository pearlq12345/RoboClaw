"""ReplaySession - thin wrapper over replay action helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from roboclaw.embodied.service.actions import do_replay

if TYPE_CHECKING:
    from roboclaw.embodied.manifest import Manifest
    from roboclaw.embodied.service import EmbodiedService


class ReplaySession:
    def __init__(self, parent: EmbodiedService):
        self._parent = parent

    async def replay(
        self,
        manifest: Manifest,
        kwargs: dict[str, Any],
        tty_handoff: Any,
    ) -> str:
        self._parent.acquire_embodiment("replaying")
        try:
            return await do_replay(manifest, kwargs, tty_handoff)
        finally:
            self._parent.release_embodiment()
