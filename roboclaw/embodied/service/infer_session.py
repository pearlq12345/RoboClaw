"""InferSession - thin wrapper over policy inference actions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from roboclaw.embodied.service.actions import do_run_policy

if TYPE_CHECKING:
    from roboclaw.embodied.manifest import Manifest
    from roboclaw.embodied.service import EmbodiedService


class InferSession:
    def __init__(self, parent: EmbodiedService):
        self._parent = parent

    async def run_policy(
        self,
        manifest: Manifest,
        kwargs: dict[str, Any],
        tty_handoff: Any,
    ) -> str:
        return await do_run_policy(manifest, kwargs, tty_handoff)
