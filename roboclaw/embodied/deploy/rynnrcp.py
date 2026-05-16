"""RynnRCP deployment bridge backed by LCM when available."""

from __future__ import annotations

import importlib
import json
import logging
import os
import threading
import time
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Callable


K_STATE_FEEDBACK_REQUEST = 1
K_GO_HOME_REQUEST = 2
K_ACTION_CHUNK_COMMAND = 10

_REQUEST_MODULE_CANDIDATES = (
    "act_request",
    "common.lcm.act_request",
    "rcp_framework.lcm.act_request",
    "robot_motion.lcm.act_request",
)
_COMMAND_MODULE_CANDIDATES = (
    "act_command",
    "common.lcm.act_command",
    "rcp_framework.lcm.act_command",
    "robot_motion.lcm.act_command",
)

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class RynnRCPSettings:
    lcm_channel: str = "rcp_robotmotion"
    inference_rate: float = 30.0
    timeout_seconds: float = 30.0
    robot_type: str = "so101"
    action_dim: int = 6
    action_chunk_size: int = 20
    interpolation: str = "cubic"

    @classmethod
    def from_env(cls) -> "RynnRCPSettings":
        return cls(
            lcm_channel=os.environ.get("ROBOCLAW_RYNNRCP_CHANNEL", cls.lcm_channel).strip() or cls.lcm_channel,
            inference_rate=_env_float("ROBOCLAW_RYNNRCP_INFERENCE_RATE", cls.inference_rate),
            timeout_seconds=_env_float("ROBOCLAW_RYNNRCP_TIMEOUT_SECONDS", cls.timeout_seconds),
            robot_type=os.environ.get("ROBOCLAW_RYNNRCP_ROBOT_TYPE", cls.robot_type).strip() or cls.robot_type,
            action_dim=_env_int("ROBOCLAW_RYNNRCP_ACTION_DIM", cls.action_dim),
            action_chunk_size=_env_int("ROBOCLAW_RYNNRCP_ACTION_CHUNK_SIZE", cls.action_chunk_size),
            interpolation=os.environ.get("ROBOCLAW_RYNNRCP_INTERPOLATION", cls.interpolation).strip()
            or cls.interpolation,
        )


class RynnRCPBridge:
    """Bridge between RoboClaw policy inference and RynnRCP robot execution."""

    def __init__(
        self,
        settings: RynnRCPSettings | None = None,
        *,
        lcm_client: Any | None = None,
        clock_ns: Callable[[], int] | None = None,
    ) -> None:
        self.settings = settings or RynnRCPSettings.from_env()
        self._clock_ns = clock_ns or time.time_ns
        self._lcm_client = lcm_client if lcm_client is not None else self._build_lcm_client()
        self._last_command: Any | None = None
        self._last_request: Any | None = None
        self._last_state_feedback: dict[str, Any] | None = None
        if self._lcm_client is None:
            _LOGGER.warning("RynnRCP LCM client unavailable, bridge disabled")

    @property
    def enabled(self) -> bool:
        return bool(self.settings.lcm_channel and self._lcm_client is not None)

    @property
    def last_command(self) -> Any | None:
        return self._last_command

    @property
    def last_request(self) -> Any | None:
        return self._last_request

    def send_action_chunk(self, actions: list[list[float]], *, timestamp_ns: int = 0) -> None:
        """Send an action chunk over the configured RynnRCP LCM channel."""

        self._validate_actions(actions)
        command = self._make_act_command(actions, timestamp_ns=timestamp_ns or self._clock_ns())
        self._last_command = command
        self._publish(command)

    def request_state(self) -> dict[str, Any]:
        """Request state feedback from RynnRCP and return the latest payload."""

        feedback_event = threading.Event()

        def _on_feedback(_channel: str, payload: bytes) -> None:
            self._last_state_feedback = {"raw": payload.decode("utf-8", errors="replace")}
            feedback_event.set()

        subscription = None
        if self.enabled and hasattr(self._lcm_client, "subscribe"):
            try:
                subscription = self._lcm_client.subscribe(f"{self.settings.lcm_channel}_state_feedback", _on_feedback)
            except Exception:
                subscription = None
        request = self._make_act_request(K_STATE_FEEDBACK_REQUEST)
        self._last_request = request
        self._publish(request)
        if self.enabled and hasattr(self._lcm_client, "handle_timeout"):
            deadline = time.monotonic() + self.settings.timeout_seconds
            while not feedback_event.is_set() and time.monotonic() < deadline:
                self._lcm_client.handle_timeout(50)
        if subscription is not None and hasattr(self._lcm_client, "unsubscribe"):
            try:
                self._lcm_client.unsubscribe(subscription)
            except Exception:
                pass
        if self._last_state_feedback is not None:
            return dict(self._last_state_feedback)
        return {
            "status": "requested",
            "robot_type": self.settings.robot_type,
            "channel": self.settings.lcm_channel,
            "timeout_seconds": self.settings.timeout_seconds,
        }

    def go_home(self) -> None:
        """Send a RynnRCP go-home request."""

        request = self._make_act_request(K_GO_HOME_REQUEST)
        self._last_request = request
        self._publish(request)

    def _publish(self, message: Any) -> None:
        if not self.enabled:
            return
        payload = message.encode() if hasattr(message, "encode") else _json_bytes(_message_to_dict(message))
        self._lcm_client.publish(self.settings.lcm_channel, payload)

    def _validate_actions(self, actions: list[list[float]]) -> None:
        if len(actions) != self.settings.action_chunk_size:
            raise ValueError(
                f"actions must contain {self.settings.action_chunk_size} steps, got {len(actions)}."
            )
        for index, action in enumerate(actions):
            if len(action) != self.settings.action_dim:
                raise ValueError(
                    f"actions[{index}] must contain {self.settings.action_dim} values, got {len(action)}."
                )

    def _make_act_command(self, actions: list[list[float]], *, timestamp_ns: int) -> Any:
        message = _message_instance(_COMMAND_MODULE_CANDIDATES, "act_command")
        _set_field(message, "command_type", K_ACTION_CHUNK_COMMAND)
        _set_field(message, "robot_type", self.settings.robot_type)
        _set_field(message, "timestamp_ns", int(timestamp_ns))
        _set_field(message, "inference_rate", float(self.settings.inference_rate))
        _set_field(message, "interpolation", self.settings.interpolation)
        _set_field(message, "action_dim", self.settings.action_dim)
        _set_field(message, "action_chunk_size", self.settings.action_chunk_size)
        _set_field(message, "actions", [[float(value) for value in action] for action in actions])
        return message

    def _make_act_request(self, request_type: int) -> Any:
        message = _message_instance(_REQUEST_MODULE_CANDIDATES, "act_request")
        _set_field(message, "request_type", request_type)
        _set_field(message, "robot_type", self.settings.robot_type)
        _set_field(message, "timestamp_ns", self._clock_ns())
        return message

    @staticmethod
    def _build_lcm_client() -> Any | None:
        try:
            lcm = importlib.import_module("lcm")
            return lcm.LCM()
        except Exception:
            return None


def _message_instance(module_names: tuple[str, ...], class_name: str) -> Any:
    for module_name in module_names:
        try:
            module = importlib.import_module(module_name)
        except Exception:
            continue
        cls = getattr(module, class_name, None)
        if cls is not None:
            return cls()
    return SimpleNamespace()


def _set_field(message: Any, name: str, value: Any) -> None:
    setattr(message, name, value)


def _message_to_dict(message: Any) -> dict[str, Any]:
    if hasattr(message, "__dict__"):
        return dict(message.__dict__)
    return {"value": repr(message)}


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    return float(raw)


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    return int(raw)


__all__ = [
    "K_ACTION_CHUNK_COMMAND",
    "K_GO_HOME_REQUEST",
    "K_STATE_FEEDBACK_REQUEST",
    "RynnRCPBridge",
    "RynnRCPSettings",
]
