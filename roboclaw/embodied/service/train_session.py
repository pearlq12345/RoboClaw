"""TrainSession - thin wrapper over training actions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from roboclaw.embodied.service.actions import do_job_status, do_train

if TYPE_CHECKING:
    from roboclaw.embodied.manifest import Manifest
    from roboclaw.embodied.service import EmbodiedService


class TrainSession:
    def __init__(self, parent: EmbodiedService):
        self._parent = parent

    async def train(
        self,
        manifest: Manifest,
        kwargs: dict[str, Any],
        tty_handoff: Any,
    ) -> str:
        return await do_train(manifest, kwargs, tty_handoff)

    async def job_status(
        self,
        manifest: Manifest,
        kwargs: dict[str, Any],
        tty_handoff: Any,
    ) -> str:
        return await do_job_status(manifest, kwargs, tty_handoff)
