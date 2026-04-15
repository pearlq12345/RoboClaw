"""Unit tests for uncertainty-driven coordination service."""

from __future__ import annotations

import pytest

from roboclaw.embodied.service.coordination import CoordinationService


def test_decide_replan_modes() -> None:
    svc = CoordinationService()

    normal = svc.decide_replan(uncertainty_score=0.2)
    slow = svc.decide_replan(uncertainty_score=0.55)
    replan = svc.decide_replan(uncertainty_score=0.85)

    assert normal["mode"] == "normal"
    assert slow["mode"] == "slow_chunk"
    assert replan["mode"] == "replan"


def test_decide_replan_rejects_bad_threshold_order() -> None:
    svc = CoordinationService()
    with pytest.raises(ValueError, match="slow_threshold must be smaller"):
        svc.decide_replan(uncertainty_score=0.5, slow_threshold=0.8, replan_threshold=0.7)


def test_score_failure_returns_weighted_value() -> None:
    svc = CoordinationService()
    score = svc.score_failure(
        uncertainty_jump=0.8,
        failure_severity=0.6,
        recovery_gain=0.4,
        weights=(0.5, 0.3, 0.2),
    )
    assert score == 0.66


def test_record_failure_keeps_high_salience_ranked_and_trimmed() -> None:
    svc = CoordinationService(max_events_per_context=2)
    svc.record_failure(context="pick", uncertainty_jump=0.2, failure_severity=0.2, recovery_gain=0.2)
    svc.record_failure(context="pick", uncertainty_jump=0.8, failure_severity=0.9, recovery_gain=0.7)
    svc.record_failure(context="pick", uncertainty_jump=0.4, failure_severity=0.4, recovery_gain=0.4)

    top = svc.top_failures(context="pick", limit=5)
    assert len(top) == 2
    assert top[0]["salience"] >= top[1]["salience"]


def test_top_failures_rejects_non_positive_limit() -> None:
    svc = CoordinationService()
    with pytest.raises(ValueError, match="limit must be > 0"):
        svc.top_failures(context="any", limit=0)

