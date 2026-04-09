"""Grab a single frame (or all frames) from configured cameras."""
from __future__ import annotations

import io
from pathlib import Path

import cv2
import numpy as np


def _default_camera_configs() -> dict[str, dict]:
    """Load camera configs from Manifest binding state."""
    try:
        from roboclaw.embodied.manifest import Manifest
        manifest = Manifest()
        configs = {}
        for binding in manifest.cameras:
            # Port may be /dev/videoN or rtsp:// URL
            configs[binding.alias] = {"port": binding.port}
        return configs
    except Exception:
        pass
    return {}


def grab_frame(camera_alias: str) -> np.ndarray | None:
    """Grab a single frame from a named camera. Returns HWC BGR numpy array or None."""
    configs = _default_camera_configs()
    if camera_alias not in configs:
        return None

    cam = configs[camera_alias]
    cap = cv2.VideoCapture(cam["port"])
    if not cap.isOpened():
        return None
    ret, frame = cap.read()
    cap.release()
    if not ret:
        return None
    return frame


def grab_all_frames() -> dict[str, np.ndarray]:
    """Grab one frame from every configured camera. Returns {alias: frame}."""
    configs = _default_camera_configs()
    results: dict[str, np.ndarray] = {}
    for alias in configs:
        frame = grab_frame(alias)
        if frame is not None:
            results[alias] = frame
    return results


def frame_to_bytes(frame: np.ndarray, fmt: str = ".jpg", quality: int = 85) -> bytes:
    """Encode a frame to bytes (JPEG by default)."""
    if fmt.lower() in (".jpg", ".jpeg"):
        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
    else:
        ok, buf = cv2.imencode(fmt, frame)
    if not ok:
        raise ValueError("Failed to encode frame")
    return buf.tobytes()


def frame_to_base64(frame: np.ndarray) -> str:
    """Encode a frame to base64 data URI (image/jpeg)."""
    import base64
    data = frame_to_bytes(frame, ".jpg")
    return base64.b64encode(data).decode("ascii")


def frame_to_pil(frame: np.ndarray):
    """Convert BGR numpy frame to PIL RGB Image."""
    from PIL import Image
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb)


def save_frame(frame: np.ndarray, path: str | Path) -> Path:
    """Save a frame to disk."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fmt = path.suffix.lower()
    ok = cv2.imwrite(str(path), frame)
    if not ok:
        raise IOError(f"cv2.imwrite failed for {path}")
    return path
