"""Configuration sub-service: CRUD for arms, cameras, and hands."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from roboclaw.embodied.manifest.helpers import (
    _probe_hand_slave_id,
    _resolve_serial_interface,
    arm_display_name,
)

if TYPE_CHECKING:
    from roboclaw.embodied.service import EmbodiedService


class ConfigService:
    """Manages setup configuration: add/remove/rename arms, cameras, hands."""

    def __init__(self, parent: EmbodiedService) -> None:
        self._parent = parent

    def set_arm(self, alias: str, arm_type: str, port: str) -> str:
        if not all([alias, arm_type, port]):
            return "bind_arm requires alias, arm_type, and port."
        interface = _resolve_serial_interface(port)
        self._parent.manifest.set_arm(alias, arm_type, interface)
        arm = self._parent.manifest.find_arm(alias)
        display = arm_display_name(arm)
        return f"Arm '{display}' configured.\n{json.dumps(arm.to_dict(), indent=2)}"

    def rename_arm(self, old_alias: str, new_alias: str) -> str:
        if not old_alias or not new_alias:
            return "rename_arm requires alias and new_alias."
        self._parent.manifest.rename_arm(old_alias, new_alias)
        arm = self._parent.manifest.find_arm(new_alias)
        return (
            f"Arm renamed from '{old_alias}' to '{new_alias}'.\n"
            f"{json.dumps(arm.to_dict(), indent=2)}"
        )

    def remove_arm(self, alias: str) -> str:
        if not alias:
            return "unbind_arm requires alias."
        if self._parent.embodiment_busy:
            return f"Cannot remove arm while embodiment is busy: {self._parent.busy_reason}"
        self._parent.manifest.remove_arm(alias)
        return f"Arm '{alias}' removed."

    def set_camera(self, camera_name: str, camera_index: int) -> str:
        if not camera_name or camera_index is None:
            return "bind_camera requires camera_name and camera_index."
        from roboclaw.embodied.hardware.scan import scan_cameras

        scanned = scan_cameras()
        if camera_index < 0 or camera_index >= len(scanned):
            return (
                f"camera_index {camera_index} out of range. "
                f"Found {len(scanned)} camera(s)."
            )
        interface = scanned[camera_index]
        if not interface.address:
            return f"Scanned camera at index {camera_index} has no usable path."
        self._parent.manifest.set_camera(camera_name, interface)
        cam = self._parent.manifest.find_camera(camera_name)
        return f"Camera '{camera_name}' configured.\n{json.dumps(cam.to_dict(), indent=2)}"

    def remove_camera(self, camera_name: str) -> str:
        if not camera_name:
            return "unbind_camera requires camera_name."
        if self._parent.embodiment_busy:
            return f"Cannot remove camera while embodiment is busy: {self._parent.busy_reason}"
        self._parent.manifest.remove_camera(camera_name)
        return f"Camera '{camera_name}' removed."

    def rename_camera(self, old_name: str, new_name: str) -> str:
        if not old_name or not new_name:
            return "rename_camera requires camera_name and new_alias."
        camera = self._parent.manifest.find_camera(old_name)
        if camera is None:
            return f"No camera with alias '{old_name}'."
        if self._parent.manifest.find_camera(new_name) is not None:
            return f"Camera alias '{new_name}' already exists."
        self._parent.manifest.remove_camera(old_name)
        self._parent.manifest.set_camera(new_name, camera.interface)
        camera = self._parent.manifest.find_camera(new_name)
        return (
            f"Camera renamed from '{old_name}' to '{new_name}'.\n"
            f"{json.dumps(camera.to_dict(), indent=2)}"
        )

    def set_hand(self, alias: str, hand_type: str, port: str) -> str:
        if not all([alias, hand_type, port]):
            return "bind_hand requires alias, hand_type, and port."
        interface = _resolve_serial_interface(port)
        slave_id = _probe_hand_slave_id(hand_type, interface.address)
        self._parent.manifest.set_hand(alias, hand_type, interface, slave_id)
        hand = self._parent.manifest.find_hand(alias)
        return f"Hand '{alias}' configured.\n{json.dumps(hand.to_dict(), indent=2)}"

    def remove_hand(self, alias: str) -> str:
        if not alias:
            return "unbind_hand requires alias."
        self._parent.manifest.remove_hand(alias)
        return f"Hand '{alias}' removed."

    def rename_hand(self, old_alias: str, new_alias: str) -> str:
        if not old_alias or not new_alias:
            return "rename_hand requires alias and new_alias."
        hand = self._parent.manifest.find_hand(old_alias)
        if hand is None:
            return f"No hand with alias '{old_alias}'."
        if self._parent.manifest.find_hand(new_alias) is not None:
            return f"Hand alias '{new_alias}' already exists."
        self._parent.manifest.remove_hand(old_alias)
        self._parent.manifest.set_hand(
            new_alias,
            hand.type_name,
            hand.interface,
            hand.slave_id,
        )
        hand = self._parent.manifest.find_hand(new_alias)
        return (
            f"Hand renamed from '{old_alias}' to '{new_alias}'.\n"
            f"{json.dumps(hand.to_dict(), indent=2)}"
        )
