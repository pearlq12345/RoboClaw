"""Hardware scanning, port probing, and motion detection.

Extracted from web/dashboard_setup.py so it can be used by any adapter
(CLI, Web, agent tool) without importing HTTP/FastAPI concerns.
"""

from __future__ import annotations

import os
import subprocess
from typing import Any

from loguru import logger

from roboclaw.embodied.identify import (
    MOTION_THRESHOLD,
    _filter_feetech_ports,
    _resolve_port_by_id,
    _resolve_port_path,
    detect_motion,
    read_positions,
)
from roboclaw.embodied.hardware.scan import (
    capture_camera_frames,
    list_serial_device_paths,
    scan_cameras,
    scan_serial_ports,
)


class HardwareScanner:
    """Stateful hardware scanner with port probing and motion detection."""

    def __init__(self) -> None:
        self.scanned_ports: list[dict] = []
        self.scanned_cameras: list[dict] = []
        self._baselines: dict[str, dict[int, int]] = {}
        self._motion_active = False

    @property
    def motion_active(self) -> bool:
        return self._motion_active

    def scan_ports(self) -> list[dict]:
        """Scan serial ports and probe for motors. Auto-fixes permissions if needed."""
        ports = scan_serial_ports()
        try:
            result = _filter_feetech_ports(ports)
        except Exception as exc:
            if "Permission denied" not in str(exc) and "Errno 13" not in str(exc):
                raise
            if fix_serial_permissions():
                result = _filter_feetech_ports(ports)
            else:
                raise PermissionError(
                    "Serial port permission denied. Run: bash scripts/setup-udev.sh"
                ) from exc
        self.scanned_ports = result
        return result

    def scan_cameras_list(self) -> list[dict]:
        """Scan connected cameras."""
        result = scan_cameras()
        self.scanned_cameras = result
        return result

    def capture_camera_previews(self, output_dir: str) -> list[dict]:
        """Capture one preview frame per camera."""
        if not self.scanned_cameras:
            raise RuntimeError("No cameras scanned. Run scan_cameras_list first.")
        return capture_camera_frames(self.scanned_cameras, output_dir)

    def start_motion_detection(self) -> int:
        """Read baselines for all scanned ports. Returns port count."""
        if not self.scanned_ports:
            raise RuntimeError("No scanned ports. Run scan_ports first.")
        self._baselines = {}
        for port in self.scanned_ports:
            path = _resolve_port_path(port)
            self._baselines[path] = read_positions(path, port["motor_ids"])
        self._motion_active = True
        return len(self._baselines)

    def poll_motion(self) -> list[dict[str, Any]]:
        """Read current positions and compute motion delta for each port."""
        if not self._motion_active or not self._baselines:
            raise RuntimeError("Motion detection not started.")
        results = []
        for port in self.scanned_ports:
            path = _resolve_port_path(port)
            current = read_positions(path, port["motor_ids"])
            baseline = self._baselines.get(path, {})
            delta = detect_motion(baseline, current)
            results.append({
                "port_id": _resolve_port_by_id(port),
                "dev": port.get("dev", ""),
                "by_id": port.get("by_id", ""),
                "motor_ids": port.get("motor_ids", []),
                "delta": delta,
                "moved": delta > MOTION_THRESHOLD,
            })
        return results

    def stop_motion_detection(self) -> None:
        """Clear baselines and stop motion detection."""
        self._motion_active = False
        self._baselines = {}


def fix_serial_permissions() -> bool:
    """Install udev rules for serial device access. Returns True on success."""
    udev_rule = (
        'KERNEL=="ttyACM[0-9]*", MODE="0666"\n'
        'KERNEL=="ttyUSB[0-9]*", MODE="0666"\n'
        'SUBSYSTEM=="tty", ATTRS{idVendor}=="1a86", MODE="0666"\n'
        'SUBSYSTEM=="video4linux", MODE="0666"\n'
    )
    try:
        result = subprocess.run(
            ["sudo", "-n", "tee", "/etc/udev/rules.d/99-roboclaw.rules"],
            input=udev_rule.encode(), capture_output=True, timeout=5,
        )
        if result.returncode != 0:
            logger.warning("Passwordless sudo not available for udev rules")
            return _try_chmod_devices()
        subprocess.run(
            ["sudo", "-n", "udevadm", "control", "--reload-rules"],
            capture_output=True, timeout=5,
        )
        subprocess.run(
            ["sudo", "-n", "udevadm", "trigger"],
            capture_output=True, timeout=5,
        )
        logger.info("Installed udev rules for serial device access")
        return True
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return _try_chmod_devices()


def _try_chmod_devices() -> bool:
    """Fallback: chmod individual device files."""
    devices = list_serial_device_paths()
    if not devices:
        return False
    for dev in devices:
        try:
            os.chmod(dev, 0o666)
        except PermissionError:
            result = subprocess.run(
                ["sudo", "-n", "chmod", "666", dev],
                capture_output=True, timeout=5,
            )
            if result.returncode != 0:
                logger.warning("Cannot chmod {}: no passwordless sudo", dev)
                return False
    logger.info("Fixed serial device permissions via chmod")
    return True
