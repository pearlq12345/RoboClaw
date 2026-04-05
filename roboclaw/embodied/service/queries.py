"""Query sub-service: read-only status and action descriptions."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from roboclaw.embodied.hardware.monitor import (
    ArmStatus,
    CameraStatus,
    check_arm_status,
    check_camera_status,
)
from roboclaw.embodied.engine.helpers import group_arms
from roboclaw.embodied.manifest import Manifest
from roboclaw.embodied.manifest.binding import Binding

if TYPE_CHECKING:
    from roboclaw.embodied.service import EmbodiedService

_ACTION_DESCRIPTIONS = {
    "scan": "Scan for serial ports with motors and available cameras.",
    "check": "Check LeRobot availability and show the current embodied setup.",
    "identify": "Launch the interactive arm-identification flow for detected serial ports.",
    "describe": "Explain adjustable parameters for a target embodied action.",
    "calibrate": "Calibrate one or more configured arms. If arms is omitted, calibrate every uncalibrated arm.",
    "teleoperate": "Run live teleoperation. Select arms with a comma-separated port list.",
    "record": "Record a dataset with one follower/leader pair or two pairs for bimanual capture.",
    "replay": "Replay a recorded dataset episode on one or two follower arms.",
    "train": "Start ACT training for a recorded dataset as a detached job.",
    "run_policy": "Run a trained policy rollout with one or two follower arms.",
    "job_status": "Inspect the status and recent logs for a detached training job.",
    "status": "Show hardware status: configured arms/cameras, connectivity, calibration, readiness.",
    "bind_arm": "Create or update one configured arm alias.",
    "rename_arm": "Rename an existing configured arm alias.",
    "unbind_arm": "Remove one configured arm alias.",
    "bind_camera": "Assign a scanned camera to a stable camera name.",
    "rename_camera": "Rename an existing configured camera alias.",
    "preview_cameras": "Capture one preview image for each scanned camera.",
    "unbind_camera": "Remove a configured camera.",
    "bind_hand": "Create or update one configured hand alias.",
    "unbind_hand": "Remove a configured hand alias.",
    "rename_hand": "Rename an existing configured hand alias.",
    "hand_open": "Open all fingers of a dexterous hand.",
    "hand_close": "Close all fingers of a dexterous hand.",
    "hand_pose": "Set individual finger positions on a dexterous hand.",
    "hand_status": "Read current finger angles and forces from a dexterous hand.",
    "list_datasets": "List recorded datasets with episode counts.",
    "list_policies": "List trained policy checkpoints.",
}


def _compute_readiness(
    arms: list[Binding],
    arm_statuses: list[ArmStatus],
    camera_statuses: list[CameraStatus],
) -> tuple[bool, list[str]]:
    missing: list[str] = []
    grouped = group_arms(arms)
    if not grouped["followers"]:
        missing.append("No follower arm configured")
    if not grouped["leaders"]:
        missing.append("No leader arm configured")
    for s in arm_statuses:
        if not s.connected:
            missing.append(f"Arm '{s.alias}' is disconnected")
        elif not s.calibrated:
            missing.append(f"Arm '{s.alias}' is not calibrated")
    for s in camera_statuses:
        if not s.connected:
            missing.append(f"Camera '{s.alias}' is disconnected")
    f, l = grouped["followers"], grouped["leaders"]
    if f and l and len(f) != len(l):
        missing.append(f"Follower/leader count mismatch: {len(f)} vs {len(l)}")
    return len(missing) == 0, missing


class QueryService:
    """Read-only queries: manifest, hardware status, datasets, policies, previews."""

    def __init__(self, parent: EmbodiedService) -> None:
        self._parent = parent

    def get_current_config(self) -> dict[str, Any]:
        """Return current manifest config (arms, cameras, hands)."""
        return {
            "arms": [binding.to_dict() for binding in self._parent.manifest.arms],
            "cameras": [binding.to_dict() for binding in self._parent.manifest.cameras],
            "hands": [binding.to_dict() for binding in self._parent.manifest.hands],
        }

    def get_manifest(self) -> str:
        """Return manifest config + hardware connectivity status.

        Same data as the web hardware-status endpoint — config + connectivity
        + calibration + readiness. Discovery of new hardware uses the separate
        ``scan`` action (service.setup.run_full_scan).
        """
        snapshot = self._parent.manifest.snapshot
        snapshot["status"] = self.get_hardware_status(self._parent.manifest)
        return json.dumps(snapshot, indent=2, ensure_ascii=False)

    def describe_actions(self, target_action: str = "") -> str:
        if not target_action:
            return json.dumps(_ACTION_DESCRIPTIONS, indent=2, ensure_ascii=False)
        if target_action not in _ACTION_DESCRIPTIONS:
            return f"Unknown target_action: {target_action}"
        return f"{target_action}: {_ACTION_DESCRIPTIONS[target_action]}"

    def get_hardware_status(self, manifest: Manifest | None = None) -> dict[str, Any]:
        if manifest is None:
            manifest = self._parent.manifest
        arms = manifest.arms
        cameras = manifest.cameras
        arm_statuses = [check_arm_status(a) for a in arms]
        camera_statuses = [check_camera_status(c) for c in cameras]
        ready, missing = _compute_readiness(arms, arm_statuses, camera_statuses)
        return {
            "ready": ready,
            "missing": missing,
            "arms": [s.to_dict() for s in arm_statuses],
            "cameras": [s.to_dict() for s in camera_statuses],
            "session_busy": self._parent.session.busy,
        }

    def read_servo_positions(self) -> dict[str, Any]:
        if self._parent.busy:
            return {"error": "busy", "arms": {}}
        from roboclaw.embodied.hardware.motors import read_servo_positions
        return read_servo_positions(self._parent.manifest.arms)
