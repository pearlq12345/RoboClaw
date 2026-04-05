"""Embodied tool groups - bridges agent to the embodied robotics layer."""

from __future__ import annotations

import asyncio
from typing import Any

from roboclaw.agent.tools.base import Tool
from roboclaw.embodied.embodiment.arm.registry import all_arm_types
from roboclaw.embodied.embodiment.hand.registry import all_hand_types

_MANIFEST_ACTIONS = [
    "status",
    "bind_arm",
    "unbind_arm",
    "rename_arm",
    "bind_camera",
    "unbind_camera",
    "rename_camera",
    "bind_hand",
    "unbind_hand",
    "rename_hand",
    "describe",
]
_SETUP_ACTIONS = ["scan", "identify", "preview_cameras"]
_DOCTOR_ACTIONS = ["check"]
_CALIBRATION_ACTIONS = ["calibrate"]
_TELEOP_ACTIONS = ["teleoperate"]
_RECORD_ACTIONS = ["record"]
_REPLAY_ACTIONS = ["replay"]
_TRAIN_ACTIONS = ["train", "job_status", "list_datasets", "list_policies"]
_INFER_ACTIONS = ["run_policy"]
_EMBODIMENT_CONTROL_ACTIONS = ["hand_open", "hand_close", "hand_pose", "hand_status"]

_TOOL_GROUPS: dict[str, dict[str, Any]] = {
    "manifest": {
        "description": "Inspect and edit the embodied hardware manifest.",
        "actions": _MANIFEST_ACTIONS,
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": _MANIFEST_ACTIONS,
                    "description": "The manifest action to perform.",
                },
                "alias": {
                    "type": "string",
                    "description": "Existing arm or hand alias to update or remove.",
                },
                "arm_type": {
                    "type": "string",
                    "enum": list(all_arm_types()),
                    "description": "Arm hardware type for bind_arm.",
                },
                "port": {
                    "type": "string",
                    "description": "Serial port path for bind_arm or bind_hand.",
                },
                "new_alias": {
                    "type": "string",
                    "description": "New alias for rename_arm, rename_camera, or rename_hand.",
                },
                "camera_name": {
                    "type": "string",
                    "description": "Camera alias for bind_camera, unbind_camera, or rename_camera.",
                },
                "camera_index": {
                    "type": "integer",
                    "description": "Index into the detected camera list for bind_camera.",
                },
                "target_action": {
                    "type": "string",
                    "description": "Action name to describe.",
                },
                "hand_type": {
                    "type": "string",
                    "enum": list(all_hand_types()),
                    "description": "Hand hardware type for bind_hand.",
                },
            },
            "required": ["action"],
            "additionalProperties": False,
        },
    },
    "setup": {
        "description": "Scan hardware, identify arms, and preview cameras.",
        "actions": _SETUP_ACTIONS,
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": _SETUP_ACTIONS,
                    "description": "The setup action to perform.",
                },
                "model": {
                    "type": "string",
                    "description": "Robot model name to narrow scan protocol.",
                },
            },
            "required": ["action"],
            "additionalProperties": False,
        },
    },
    "doctor": {
        "description": "Check embodied environment health and summarize the current setup.",
        "actions": _DOCTOR_ACTIONS,
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": _DOCTOR_ACTIONS,
                    "description": "The doctor action to perform.",
                },
            },
            "required": ["action"],
            "additionalProperties": False,
        },
    },
    "calibration": {
        "description": "Calibrate one or more configured arms.",
        "actions": _CALIBRATION_ACTIONS,
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": _CALIBRATION_ACTIONS,
                    "description": "The calibration action to perform.",
                },
                "arms": {
                    "type": "string",
                    "description": "Comma-separated arm port paths (by-id from status).",
                },
            },
            "required": ["action"],
            "additionalProperties": False,
        },
    },
    "teleop": {
        "description": "Run live teleoperation.",
        "actions": _TELEOP_ACTIONS,
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": _TELEOP_ACTIONS,
                    "description": "The teleop action to perform.",
                },
                "arms": {
                    "type": "string",
                    "description": "Comma-separated arm port paths (by-id from status).",
                },
                "fps": {
                    "type": "integer",
                    "description": "Frames per second for teleoperation.",
                },
            },
            "required": ["action"],
            "additionalProperties": False,
        },
    },
    "record": {
        "description": "Record a dataset from one or two leader/follower pairs.",
        "actions": _RECORD_ACTIONS,
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": _RECORD_ACTIONS,
                    "description": "The recording action to perform.",
                },
                "arms": {
                    "type": "string",
                    "description": "Comma-separated arm port paths (by-id from status).",
                },
                "dataset_name": {
                    "type": "string",
                    "description": "Dataset slug for record.",
                },
                "task": {
                    "type": "string",
                    "description": "Task description for recording.",
                },
                "use_cameras": {
                    "type": "boolean",
                    "default": True,
                    "description": "Whether recording should include configured cameras.",
                },
                "num_episodes": {
                    "type": "integer",
                    "description": "Number of episodes to record.",
                },
                "fps": {
                    "type": "integer",
                    "description": "Frames per second for recording.",
                },
                "episode_time_s": {
                    "type": "integer",
                    "description": "Duration per episode in seconds.",
                },
                "reset_time_s": {
                    "type": "integer",
                    "description": "Duration of reset period between episodes in seconds.",
                },
            },
            "required": ["action"],
            "additionalProperties": False,
        },
    },
    "replay": {
        "description": "Replay a recorded dataset episode on follower arms.",
        "actions": _REPLAY_ACTIONS,
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": _REPLAY_ACTIONS,
                    "description": "The replay action to perform.",
                },
                "arms": {
                    "type": "string",
                    "description": "Comma-separated arm port paths (by-id from status).",
                },
                "dataset_name": {
                    "type": "string",
                    "description": "Dataset slug for replay.",
                },
                "episode": {
                    "type": "integer",
                    "description": "Episode index to replay.",
                },
                "fps": {
                    "type": "integer",
                    "description": "Frames per second for replay.",
                },
            },
            "required": ["action"],
            "additionalProperties": False,
        },
    },
    "train": {
        "description": "Train ACT, inspect training jobs, and list datasets or policies.",
        "actions": _TRAIN_ACTIONS,
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": _TRAIN_ACTIONS,
                    "description": "The training action to perform.",
                },
                "dataset_name": {
                    "type": "string",
                    "description": "Dataset slug for training.",
                },
                "steps": {
                    "type": "integer",
                    "description": "Number of training steps.",
                },
                "device": {
                    "type": "string",
                    "description": "Device for training.",
                },
                "job_id": {
                    "type": "string",
                    "description": "ID of a background training job.",
                },
            },
            "required": ["action"],
            "additionalProperties": False,
        },
    },
    "infer": {
        "description": "Run a trained policy on the configured follower arms.",
        "actions": _INFER_ACTIONS,
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": _INFER_ACTIONS,
                    "description": "The inference action to perform.",
                },
                "arms": {
                    "type": "string",
                    "description": "Comma-separated arm port paths (by-id from status).",
                },
                "dataset_name": {
                    "type": "string",
                    "description": "Optional evaluation dataset slug.",
                },
                "source_dataset": {
                    "type": "string",
                    "description": "Dataset name to resolve the default checkpoint from.",
                },
                "checkpoint_path": {
                    "type": "string",
                    "description": "Path to a trained policy checkpoint.",
                },
                "task": {
                    "type": "string",
                    "description": "Task label for policy rollout.",
                },
                "use_cameras": {
                    "type": "boolean",
                    "default": True,
                    "description": "Whether inference should include configured cameras.",
                },
                "num_episodes": {
                    "type": "integer",
                    "description": "Number of rollout episodes to run.",
                },
            },
            "required": ["action"],
            "additionalProperties": False,
        },
    },
    "embodiment_control": {
        "description": "Control a dexterous hand: open, close, pose, and query status.",
        "actions": _EMBODIMENT_CONTROL_ACTIONS,
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": _EMBODIMENT_CONTROL_ACTIONS,
                    "description": "The embodiment-control action to perform.",
                },
                "hand_name": {
                    "type": "string",
                    "description": "Hand alias. Uses first configured hand if omitted.",
                },
                "positions": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "6 finger positions 0-1000 for hand_pose.",
                },
            },
            "required": ["action"],
            "additionalProperties": False,
        },
    },
}


class EmbodiedToolGroup(Tool):
    """A single embodied tool group with group-local dispatch."""

    def __init__(self, group_name: str, spec: dict[str, Any], tty_handoff: Any = None):
        self._group_name = group_name
        self._spec = spec
        self._tty_handoff = tty_handoff
        self.embodied_service = None

    @property
    def name(self) -> str:
        return self._group_name

    @property
    def description(self) -> str:
        return self._spec["description"]

    @property
    def parameters(self) -> dict[str, Any]:
        return self._spec["parameters"]

    async def execute(self, **kwargs: Any) -> str | list:
        action = kwargs.get("action", "")
        if action not in self._spec["actions"]:
            return f"Unknown action '{action}' for tool {self._group_name}."
        if self._group_name == "manifest":
            return await self._execute_manifest(kwargs)
        if self._group_name == "setup":
            return await self._execute_setup(kwargs)
        if self._group_name == "doctor":
            return await self._execute_doctor(kwargs)
        if self._group_name == "calibration":
            return await self._execute_calibration(kwargs)
        if self._group_name == "teleop":
            return await self._execute_teleop(kwargs)
        if self._group_name == "record":
            return await self._execute_record(kwargs)
        if self._group_name == "replay":
            return await self._execute_replay(kwargs)
        if self._group_name == "train":
            return await self._execute_train(kwargs)
        if self._group_name == "infer":
            return await self._execute_infer(kwargs)
        if self._group_name == "embodiment_control":
            return await self._execute_embodiment_control(kwargs)
        return f"Unknown tool group: {self._group_name}"

    async def _execute_manifest(self, kwargs: dict[str, Any]) -> str | list:
        svc = _get_service(self.embodied_service)
        action = kwargs["action"]
        if action == "status":
            return svc.queries.get_manifest()
        if action == "describe":
            return svc.queries.describe_actions(kwargs.get("target_action", ""))
        if action == "bind_arm":
            return svc.config.set_arm(kwargs.get("alias", ""), kwargs.get("arm_type", ""), kwargs.get("port", ""))
        if action == "unbind_arm":
            return svc.config.remove_arm(kwargs.get("alias", ""))
        if action == "rename_arm":
            return svc.config.rename_arm(kwargs.get("alias", ""), kwargs.get("new_alias", ""))
        if action == "bind_camera":
            return svc.config.set_camera(kwargs.get("camera_name", ""), kwargs.get("camera_index", 0))
        if action == "unbind_camera":
            return svc.config.remove_camera(kwargs.get("camera_name", ""))
        if action == "rename_camera":
            return svc.config.rename_camera(kwargs.get("camera_name", ""), kwargs.get("new_alias", ""))
        if action == "bind_hand":
            return svc.config.set_hand(kwargs.get("alias", ""), kwargs.get("hand_type", ""), kwargs.get("port", ""))
        if action == "unbind_hand":
            return svc.config.remove_hand(kwargs.get("alias", ""))
        return svc.config.rename_hand(kwargs.get("alias", ""), kwargs.get("new_alias", ""))

    async def _execute_setup(self, kwargs: dict[str, Any]) -> str | list:
        svc = _get_service(self.embodied_service)
        action = kwargs["action"]
        if action == "scan":
            result = await asyncio.to_thread(svc.setup.run_full_scan, kwargs.get("model", ""))
            return _format_scan(result)
        if action == "preview_cameras":
            return svc.setup.preview_cameras()
        return await _run_with_manifest(
            svc,
            lambda manifest: svc.setup.identify(manifest, kwargs, self._tty_handoff),
        )

    async def _execute_doctor(self, kwargs: dict[str, Any]) -> str | list:
        svc = _get_service(self.embodied_service)
        return await _run_with_manifest(
            svc,
            lambda manifest: svc.doctor.check(manifest, kwargs, self._tty_handoff),
        )

    async def _execute_calibration(self, kwargs: dict[str, Any]) -> str | list:
        svc = _get_service(self.embodied_service)
        return await _run_with_manifest(
            svc,
            lambda manifest: svc.calibration_session.calibrate(manifest, kwargs, self._tty_handoff),
        )

    async def _execute_teleop(self, kwargs: dict[str, Any]) -> str | list:
        svc = _get_service(self.embodied_service)
        return await _run_with_manifest(
            svc,
            lambda manifest: svc.teleop.teleoperate(manifest, kwargs, self._tty_handoff),
        )

    async def _execute_record(self, kwargs: dict[str, Any]) -> str | list:
        svc = _get_service(self.embodied_service)
        return await _run_with_manifest(
            svc,
            lambda manifest: svc.record.record(manifest, kwargs, self._tty_handoff),
        )

    async def _execute_replay(self, kwargs: dict[str, Any]) -> str | list:
        svc = _get_service(self.embodied_service)
        return await _run_with_manifest(
            svc,
            lambda manifest: svc.replay.replay(manifest, kwargs, self._tty_handoff),
        )

    async def _execute_train(self, kwargs: dict[str, Any]) -> str | list:
        svc = _get_service(self.embodied_service)
        action = kwargs["action"]
        return await _run_with_manifest(
            svc,
            lambda manifest: _run_train_action(svc.train, action, manifest, kwargs, self._tty_handoff),
        )

    async def _execute_infer(self, kwargs: dict[str, Any]) -> str | list:
        svc = _get_service(self.embodied_service)
        return await _run_with_manifest(
            svc,
            lambda manifest: svc.infer.run_policy(manifest, kwargs, self._tty_handoff),
        )

    async def _execute_embodiment_control(self, kwargs: dict[str, Any]) -> str | list:
        svc = _get_service(self.embodied_service)
        action = kwargs["action"]
        return await _run_with_manifest(
            svc,
            lambda manifest: _run_hand_action(svc.hand, action, manifest, kwargs, self._tty_handoff),
        )


def create_embodied_tools(tty_handoff: Any = None) -> list[EmbodiedToolGroup]:
    """Return a list of EmbodiedToolGroup instances for all tool groups."""
    return [EmbodiedToolGroup(name, spec, tty_handoff=tty_handoff) for name, spec in _TOOL_GROUPS.items()]


def _format_scan(result: dict[str, Any]) -> str:
    ports = result["ports"]
    cameras = result["cameras"]
    lines = [f"Found {len(ports)} serial port(s) and {len(cameras)} camera(s)."]
    if ports:
        lines.append("\nPorts:")
        for port in ports:
            port_id = port.by_id or port.dev or "?"
            lines.append(f"  - {port_id}  ({len(port.motor_ids)} motors)")
    if cameras:
        lines.append("\nCameras:")
        for camera in cameras:
            lines.append(f"  - {camera.dev or '?'}  ({camera.width}x{camera.height} @ {camera.fps}fps)")
    return "\n".join(lines)


def _get_service(service: Any) -> Any:
    if service is not None:
        return service
    from roboclaw.embodied.service import EmbodiedService

    return EmbodiedService()


async def _run_with_manifest(service: Any, func: Any) -> str | list:
    from roboclaw.embodied.engine.helpers import ActionError
    from roboclaw.embodied.manifest.helpers import ensure_manifest

    manifest = ensure_manifest()
    service.manifest = manifest
    try:
        return await func(manifest)
    except ActionError as exc:
        return str(exc)


async def _run_train_action(
    train: Any,
    action: str,
    manifest: Any,
    kwargs: dict[str, Any],
    tty_handoff: Any,
) -> str:
    if action == "train":
        return await train.train(manifest, kwargs, tty_handoff)
    if action == "job_status":
        return await train.job_status(manifest, kwargs, tty_handoff)
    if action == "list_datasets":
        return train.list_datasets(manifest)
    return train.list_policies(manifest)


async def _run_hand_action(
    hand: Any,
    action: str,
    manifest: Any,
    kwargs: dict[str, Any],
    tty_handoff: Any,
) -> str:
    if action == "hand_open":
        return await hand.open_hand(manifest, kwargs, tty_handoff)
    if action == "hand_close":
        return await hand.close_hand(manifest, kwargs, tty_handoff)
    if action == "hand_pose":
        return await hand.set_pose(manifest, kwargs, tty_handoff)
    return await hand.get_status(manifest, kwargs, tty_handoff)
