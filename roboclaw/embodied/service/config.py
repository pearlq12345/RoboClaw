"""Configuration sub-service: CRUD for arms, cameras, and hands."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from roboclaw.embodied.service import EmbodiedService


class ConfigService:
    """Manages setup configuration: add/remove/rename arms, cameras, hands."""

    def __init__(self, parent: EmbodiedService) -> None:
        self._parent = parent

    def set_arm(self, alias: str, arm_type: str, port: str) -> str:
        from roboclaw.embodied.setup import arm_display_name, find_arm, set_arm

        if not all([alias, arm_type, port]):
            return "set_arm requires alias, arm_type, and port."
        updated = set_arm(alias, arm_type, port)
        arm = find_arm(updated["arms"], alias)
        display = arm_display_name(arm)
        return f"Arm '{display}' configured.\n{json.dumps(arm, indent=2)}"

    def rename_arm(self, old_alias: str, new_alias: str) -> str:
        from roboclaw.embodied.setup import find_arm, rename_arm

        if not old_alias or not new_alias:
            return "rename_arm requires alias and new_alias."
        updated = rename_arm(old_alias, new_alias)
        arm = find_arm(updated["arms"], new_alias)
        return f"Arm renamed from '{old_alias}' to '{new_alias}'.\n{json.dumps(arm, indent=2)}"

    def remove_arm(self, alias: str) -> str:
        from roboclaw.embodied.setup import remove_arm

        if not alias:
            return "remove_arm requires alias."
        if self._parent.embodiment_busy:
            return f"Cannot remove arm while embodiment is busy: {self._parent.busy_reason}"
        remove_arm(alias)
        return f"Arm '{alias}' removed."

    def set_camera(self, camera_name: str, camera_index: int) -> str:
        from roboclaw.embodied.setup import find_camera, set_camera

        if not camera_name or camera_index is None:
            return "set_camera requires camera_name and camera_index."
        updated = set_camera(camera_name, camera_index)
        cam = find_camera(updated["cameras"], camera_name)
        return f"Camera '{camera_name}' configured.\n{json.dumps(cam, indent=2)}"

    def remove_camera(self, camera_name: str) -> str:
        from roboclaw.embodied.setup import remove_camera

        if not camera_name:
            return "remove_camera requires camera_name."
        if self._parent.embodiment_busy:
            return f"Cannot remove camera while embodiment is busy: {self._parent.busy_reason}"
        remove_camera(camera_name)
        return f"Camera '{camera_name}' removed."

    def set_hand(self, alias: str, hand_type: str, port: str) -> str:
        from roboclaw.embodied.setup import find_hand, set_hand

        if not all([alias, hand_type, port]):
            return "set_hand requires alias, hand_type, and port."
        updated = set_hand(alias, hand_type, port)
        hand = find_hand(updated["hands"], alias)
        return f"Hand '{alias}' configured.\n{json.dumps(hand, indent=2)}"

    def remove_hand(self, alias: str) -> str:
        from roboclaw.embodied.setup import remove_hand

        if not alias:
            return "remove_hand requires alias."
        remove_hand(alias)
        return f"Hand '{alias}' removed."
