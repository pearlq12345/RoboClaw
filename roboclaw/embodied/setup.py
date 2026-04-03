"""Setup management — shim layer delegating to Manifest.

CRUD functions are kept as free functions for backward compatibility
during migration.  Each one delegates to a lazily-created Manifest
singleton.  ``load_setup`` / ``save_setup`` remain as-is for the
identify subprocess and tests that need path-based I/O.

Pure helpers (``find_arm``, ``arm_display_name``, ``load_calibration``,
``get_roboclaw_home``, ``ensure_bimanual_cal_dir``, etc.) are re-exported
from ``manifest.helpers`` so existing callers keep working.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from roboclaw.embodied.manifest.helpers import (
    _default_manifest as _default_setup,
    _refresh_calibration_state,
    _validate_setup,
    arm_display_name,
    ensure_bimanual_cal_dir,
    find_arm,
    find_camera,
    find_hand,
    get_calibration_root,
    get_roboclaw_home,
    get_setup_path,
    load_calibration,
    refresh_bimanual_cal_dirs,
)

# ── Manifest shim ────────────────────────────────────────────────────

_manifest_shim: "Manifest | None" = None


def _get_shim(path: Path | None = None) -> "Manifest":
    """Return the global Manifest or a path-specific one for tests."""
    global _manifest_shim
    if path is not None:
        from roboclaw.embodied.manifest import Manifest
        return Manifest(path=path)
    if _manifest_shim is None:
        from roboclaw.embodied.manifest import Manifest
        _manifest_shim = Manifest()
    return _manifest_shim


# ── Raw I/O (kept for identify subprocess + tests) ───────────────────


def load_setup(path: Path | None = None) -> dict[str, Any]:
    """Load setup.json, return defaults if not found. Refreshes calibration state from disk."""
    path = path or get_setup_path()
    if not path.exists():
        return _default_setup()
    setup = json.loads(path.read_text(encoding="utf-8"))
    setup.pop("scanned_ports", None)
    setup.pop("scanned_cameras", None)
    if isinstance(setup.get("cameras"), dict):
        setup["cameras"] = []
        save_setup(setup, path)
    if _refresh_calibration_state(setup):
        save_setup(setup, path)
    return setup


def save_setup(setup: dict[str, Any], path: Path | None = None) -> None:
    """Write setup.json, creating parent dirs if needed."""
    path = path or get_setup_path()
    _validate_setup(setup)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(setup, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# ── CRUD shims (delegate to Manifest) ────────────────────────────────


def create_setup(path: Path | None = None) -> dict[str, Any]:
    """Create a fresh setup. Called during onboard."""
    return _get_shim(path).ensure()


def ensure_setup(path: Path | None = None) -> dict[str, Any]:
    """Ensure setup exists, return snapshot."""
    return _get_shim(path).ensure()


def set_arm(alias: str, arm_type: str, port: str, *, path: Path | None = None) -> dict[str, Any]:
    m = _get_shim(path)
    m.set_arm(alias, arm_type, port)
    return m.snapshot


def remove_arm(alias: str, path: Path | None = None) -> dict[str, Any]:
    return _get_shim(path).remove_arm(alias)


def rename_arm(old_alias: str, new_alias: str, *, path: Path | None = None) -> dict[str, Any]:
    return _get_shim(path).rename_arm(old_alias, new_alias)


def mark_arm_calibrated(alias: str, path: Path | None = None) -> dict[str, Any]:
    return _get_shim(path).mark_arm_calibrated(alias)


def set_camera(name: str, camera_index: int, path: Path | None = None) -> dict[str, Any]:
    m = _get_shim(path)
    m.set_camera(name, camera_index)
    return m.snapshot


def remove_camera(name: str, path: Path | None = None) -> dict[str, Any]:
    return _get_shim(path).remove_camera(name)


def set_hand(alias: str, hand_type: str, port: str, *, path: Path | None = None) -> dict[str, Any]:
    m = _get_shim(path)
    m.set_hand(alias, hand_type, port)
    return m.snapshot


def remove_hand(alias: str, path: Path | None = None) -> dict[str, Any]:
    return _get_shim(path).remove_hand(alias)
