"""DoctorService - thin wrapper over doctor action helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from roboclaw.embodied.service.actions import do_doctor

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
        return await do_doctor(manifest, kwargs, tty_handoff)
