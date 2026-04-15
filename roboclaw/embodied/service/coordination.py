"""Coordination service: uncertainty-driven correction and salient failure memory.

This module keeps the first PR intentionally lightweight and model-agnostic:
- replan/slow/normal decision from uncertainty
- salient failure scoring
- in-memory ranking of high-value failures for retry guidance
"""

from __future__ import annotations

from dataclasses import dataclass
from time import time
from typing import Any


def _as_unit_interval(name: str, value: Any) -> float:
    """Convert to float and validate [0, 1]."""
    try:
        num = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a number in [0, 1].") from exc
    if num < 0.0 or num > 1.0:
        raise ValueError(f"{name} must be in [0, 1], got {num}.")
    return num


def _normalize_context(context: str) -> str:
    cleaned = (context or "").strip()
    return cleaned or "default"


@dataclass(slots=True)
class FailureEvent:
    """A single scored failure event."""

    context: str
    salience: float
    uncertainty_jump: float
    failure_severity: float
    recovery_gain: float
    note: str
    timestamp: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "context": self.context,
            "salience": self.salience,
            "uncertainty_jump": self.uncertainty_jump,
            "failure_severity": self.failure_severity,
            "recovery_gain": self.recovery_gain,
            "note": self.note,
            "timestamp": self.timestamp,
        }


class CoordinationService:
    """Small stateful service for uncertainty decisions and failure salience.

    The memory is intentionally in-process only for this first PR. It provides
    a stable API that can later be backed by a persistent store.
    """

    def __init__(self, max_events_per_context: int = 50) -> None:
        if max_events_per_context <= 0:
            raise ValueError("max_events_per_context must be > 0.")
        self._max_events = max_events_per_context
        self._events: dict[str, list[FailureEvent]] = {}

    def decide_replan(
        self,
        *,
        uncertainty_score: float,
        slow_threshold: float = 0.5,
        replan_threshold: float = 0.7,
    ) -> dict[str, Any]:
        """Return execution mode from uncertainty.

        Modes:
        - normal: keep current action chunk
        - slow_chunk: reduce chunk / increase refresh frequency
        - replan: trigger immediate re-planning
        """
        uncertainty = _as_unit_interval("uncertainty_score", uncertainty_score)
        slow = _as_unit_interval("slow_threshold", slow_threshold)
        replan = _as_unit_interval("replan_threshold", replan_threshold)
        if slow >= replan:
            raise ValueError("slow_threshold must be smaller than replan_threshold.")

        mode = "normal"
        if uncertainty >= replan:
            mode = "replan"
        elif uncertainty >= slow:
            mode = "slow_chunk"

        return {
            "mode": mode,
            "uncertainty_score": round(uncertainty, 4),
            "slow_threshold": round(slow, 4),
            "replan_threshold": round(replan, 4),
            "should_replan": mode == "replan",
            "should_slow_chunk": mode == "slow_chunk",
        }

    def score_failure(
        self,
        *,
        uncertainty_jump: float,
        failure_severity: float,
        recovery_gain: float,
        weights: tuple[float, float, float] = (0.5, 0.3, 0.2),
    ) -> float:
        """Compute salient failure score in [0, 1]."""
        u = _as_unit_interval("uncertainty_jump", uncertainty_jump)
        s = _as_unit_interval("failure_severity", failure_severity)
        g = _as_unit_interval("recovery_gain", recovery_gain)

        if len(weights) != 3:
            raise ValueError("weights must contain exactly 3 values.")
        wu, ws, wg = (float(weights[0]), float(weights[1]), float(weights[2]))
        if wu < 0 or ws < 0 or wg < 0:
            raise ValueError("weights must be non-negative.")
        total = wu + ws + wg
        if total <= 0:
            raise ValueError("weights sum must be > 0.")

        score = (wu * u + ws * s + wg * g) / total
        return round(score, 4)

    def record_failure(
        self,
        *,
        context: str,
        uncertainty_jump: float,
        failure_severity: float,
        recovery_gain: float,
        note: str = "",
    ) -> dict[str, Any]:
        """Record a scored failure event and keep context-local top events."""
        key = _normalize_context(context)
        score = self.score_failure(
            uncertainty_jump=uncertainty_jump,
            failure_severity=failure_severity,
            recovery_gain=recovery_gain,
        )
        event = FailureEvent(
            context=key,
            salience=score,
            uncertainty_jump=round(float(uncertainty_jump), 4),
            failure_severity=round(float(failure_severity), 4),
            recovery_gain=round(float(recovery_gain), 4),
            note=(note or "").strip(),
            timestamp=round(time(), 3),
        )
        events = self._events.setdefault(key, [])
        events.append(event)
        # Keep high-salience first; stable with most recent tie-breaker.
        events.sort(key=lambda item: (item.salience, item.timestamp), reverse=True)
        if len(events) > self._max_events:
            del events[self._max_events :]

        rank = next((idx + 1 for idx, item in enumerate(events) if item is event), len(events))
        return {
            "context": key,
            "salience": event.salience,
            "rank": rank,
            "stored_events": len(events),
        }

    def top_failures(self, *, context: str, limit: int = 3) -> list[dict[str, Any]]:
        """Return top-k salient failures for the given context."""
        if limit <= 0:
            raise ValueError("limit must be > 0.")
        key = _normalize_context(context)
        events = self._events.get(key, [])
        return [item.to_dict() for item in events[:limit]]

