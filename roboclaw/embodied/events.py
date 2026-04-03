"""Typed domain events and async EventBus.

Domain events are transport-agnostic — they carry no ``dashboard.*``
prefix.  The transport layer (WebChannel, CLI, …) subscribes to the
bus and maps events to its own wire format.
"""

from __future__ import annotations

import inspect
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Awaitable, Callable

from loguru import logger

# ---------------------------------------------------------------------------
# Event hierarchy
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Event:
    """Base class for all domain events."""

    ts: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["timestamp"] = d.pop("ts")
        return d


# -- Session -----------------------------------------------------------------


@dataclass(frozen=True)
class SessionStateChangedEvent(Event):
    state: str = "idle"
    episode_phase: str = ""
    saved_episodes: int = 0
    current_episode: int = 0
    target_episodes: int = 0
    total_frames: int = 0
    elapsed_seconds: float = 0.0
    dataset: str | None = None
    rerun_web_port: int = 0
    error: str = ""


# -- Hardware faults ---------------------------------------------------------


@dataclass(frozen=True)
class FaultDetectedEvent(Event):
    fault_type: str = ""
    device_alias: str = ""
    message: str = ""


@dataclass(frozen=True)
class FaultResolvedEvent(Event):
    fault_type: str = ""
    device_alias: str = ""


# -- Calibration -------------------------------------------------------------


@dataclass(frozen=True)
class CalibrationStateChangedEvent(Event):
    state: str = "idle"
    arm_alias: str = ""


# ---------------------------------------------------------------------------
# EventBus
# ---------------------------------------------------------------------------

Subscriber = Callable[["Event"], Awaitable[None] | None]


class EventBus:
    """Lightweight async pub/sub.

    * Subscribe by event *class* (or ``None`` for wildcard).
    * ``emit`` snapshots the subscriber list before awaiting, so
      subscribe/unsubscribe during emission is safe.
    * A failing subscriber is logged but never breaks other subscribers
      or the emitter.
    """

    def __init__(self) -> None:
        self._subs: dict[type[Event] | None, list[Subscriber]] = {}

    def on(self, event_cls: type[Event] | None, handler: Subscriber) -> None:
        """Subscribe *handler* to *event_cls* (``None`` = all events)."""
        self._subs.setdefault(event_cls, []).append(handler)

    def off(self, event_cls: type[Event] | None, handler: Subscriber) -> None:
        """Remove *handler* from *event_cls*."""
        handlers = self._subs.get(event_cls, [])
        if handler in handlers:
            handlers.remove(handler)

    async def emit(self, event: Event) -> None:
        """Fire *event* to matching + wildcard subscribers."""
        handlers = [
            *self._subs.get(type(event), []),
            *self._subs.get(None, []),
        ]
        for handler in handlers:
            try:
                result = handler(event)
                if inspect.isawaitable(result):
                    await result
            except Exception:
                logger.exception("EventBus handler error for {}", type(event).__name__)
