"""HandSession - dexterous hand control helpers."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from roboclaw.embodied.engine.helpers import ActionError
from roboclaw.embodied.manifest.binding import Binding

if TYPE_CHECKING:
    from roboclaw.embodied.manifest import Manifest
    from roboclaw.embodied.service import EmbodiedService


class HandSession:
    def __init__(self, parent: EmbodiedService) -> None:
        self._parent = parent

    async def open_hand(
        self,
        manifest: Manifest,
        kwargs: dict[str, Any],
        tty_handoff: Any,
    ) -> str:
        return await self._run_hand_method("open_hand", manifest, kwargs)

    async def close_hand(
        self,
        manifest: Manifest,
        kwargs: dict[str, Any],
        tty_handoff: Any,
    ) -> str:
        return await self._run_hand_method("close_hand", manifest, kwargs)

    async def set_pose(
        self,
        manifest: Manifest,
        kwargs: dict[str, Any],
        tty_handoff: Any,
    ) -> str:
        positions = kwargs.get("positions")
        if not positions:
            return "hand_pose requires positions (6 integers 0-1000)."
        return await self._run_hand_method("set_pose", manifest, kwargs, extra_args=(positions,))

    async def get_status(
        self,
        manifest: Manifest,
        kwargs: dict[str, Any],
        tty_handoff: Any,
    ) -> str:
        return await self._run_hand_method("get_status", manifest, kwargs)

    def _resolve_hand(self, manifest: Manifest, hand_name: str) -> Binding:
        hands = manifest.hands
        if not hands:
            raise ActionError("No hand configured. Use bind_hand to add one.")
        if not hand_name:
            return hands[0]
        hand = manifest.find_hand(hand_name)
        if hand is None:
            raise ActionError(f"No hand named '{hand_name}' in manifest.")
        return hand

    def _get_hand_controller(self, hand_type: str) -> Any:
        import importlib

        from roboclaw.embodied.embodiment.hand.registry import get_hand_spec

        spec = get_hand_spec(hand_type)
        mod = importlib.import_module(spec.controller_module)
        return getattr(mod, spec.controller_class)()

    async def _run_hand_method(
        self,
        method_name: str,
        manifest: Manifest,
        kwargs: dict[str, Any],
        extra_args: tuple[Any, ...] = (),
    ) -> str:
        hand = self._resolve_hand(manifest, kwargs.get("hand_name", ""))
        controller = self._get_hand_controller(hand.type_name)
        method = getattr(controller, method_name)
        if asyncio.iscoroutinefunction(method):
            return await method(hand.port, *extra_args, hand.slave_id)
        return await asyncio.to_thread(method, hand.port, *extra_args, hand.slave_id)
