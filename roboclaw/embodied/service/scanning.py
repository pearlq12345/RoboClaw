"""Scanning sub-service: port/camera scanning and motion detection."""

from __future__ import annotations

from typing import TYPE_CHECKING

from roboclaw.embodied.engine import HardwareScanner

if TYPE_CHECKING:
    from roboclaw.embodied.service import EmbodiedService


class ScanningService:
    """Delegates port/camera scanning and motion detection to HardwareScanner."""

    def __init__(self, parent: EmbodiedService) -> None:
        self._parent = parent
        self._scanner = HardwareScanner()

    def scan_ports(self) -> list[dict]:
        return self._scanner.scan_ports()

    def scan_cameras(self) -> list[dict]:
        return self._scanner.scan_cameras_list()

    def capture_camera_previews(self, output_dir: str) -> list[dict]:
        return self._scanner.capture_camera_previews(output_dir)

    def start_motion_detection(self) -> int:
        return self._scanner.start_motion_detection()

    def poll_motion(self) -> list[dict]:
        return self._scanner.poll_motion()

    def stop_motion_detection(self) -> None:
        self._scanner.stop_motion_detection()
