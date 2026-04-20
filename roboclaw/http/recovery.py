"""Recovery guide data for active dashboard faults."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class RecoveryGuide:
    can_recheck: bool
    step_count: int


RECOVERY_GUIDES: dict[str, RecoveryGuide] = {
    "arm_disconnected": RecoveryGuide(can_recheck=True, step_count=6),
    "arm_timeout": RecoveryGuide(can_recheck=True, step_count=4),
    "arm_not_calibrated": RecoveryGuide(can_recheck=False, step_count=1),
    "camera_disconnected": RecoveryGuide(can_recheck=True, step_count=4),
    "camera_frame_drop": RecoveryGuide(can_recheck=True, step_count=3),
    "record_crashed": RecoveryGuide(can_recheck=False, step_count=2),
}


def get_recovery_guides_json() -> dict[str, dict[str, Any]]:
    """Return the recovery guides as a JSON-serializable mapping."""
    return {key: asdict(entry) for key, entry in RECOVERY_GUIDES.items()}
