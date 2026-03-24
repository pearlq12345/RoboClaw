"""Hardware scanning — detect serial ports and cameras."""

from __future__ import annotations

import glob
import os
from pathlib import Path


def scan_serial_ports() -> list[dict[str, str]]:
    """Scan /dev/serial/by-id/ for connected serial devices."""
    by_id_dir = Path("/dev/serial/by-id")
    if not by_id_dir.exists():
        return []
    ports = []
    for entry in sorted(by_id_dir.iterdir()):
        if entry.is_symlink():
            target = os.path.realpath(str(entry))
            ports.append({"id": entry.name, "path": str(entry), "target": target})
    return ports


def scan_cameras() -> list[dict[str, str | int]]:
    """Scan /dev/video* and probe with OpenCV to find real cameras."""
    try:
        import cv2
    except ImportError:
        return []

    prev_level = os.environ.get("OPENCV_LOG_LEVEL", "")
    os.environ["OPENCV_LOG_LEVEL"] = "SILENT"
    try:
        devices = sorted(glob.glob("/dev/video*"))
        cameras = []
        for dev in devices:
            idx = int(dev.replace("/dev/video", ""))
            cap = cv2.VideoCapture(idx)
            if not cap.isOpened():
                continue
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            cap.release()
            cameras.append({"id": dev, "width": w, "height": h})
        return cameras
    finally:
        if prev_level:
            os.environ["OPENCV_LOG_LEVEL"] = prev_level
        else:
            os.environ.pop("OPENCV_LOG_LEVEL", None)
