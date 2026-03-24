"""Hardware scanning — detect serial ports and cameras."""

from __future__ import annotations

import asyncio
import glob
import os
from pathlib import Path


def scan_serial_ports() -> list[dict[str, str]]:
    """Scan /dev/serial/by-id/ for connected serial devices. Returns list of {id, path, target}."""
    by_id_dir = Path("/dev/serial/by-id")
    if not by_id_dir.exists():
        return []
    ports = []
    for entry in sorted(by_id_dir.iterdir()):
        if entry.is_symlink():
            target = os.path.realpath(str(entry))
            ports.append({"id": entry.name, "path": str(entry), "target": target})
    return ports


async def scan_cameras(output_dir: str | None = None, timeout: int = 15) -> list[dict[str, str]]:
    """Run lerobot-find-cameras and parse output. Returns list of {id, name, type}."""
    cmd = ["lerobot-find-cameras", "opencv"]
    if output_dir:
        cmd += ["--output-dir", output_dir, "--record-time-s", "2"]

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except (asyncio.TimeoutError, FileNotFoundError):
        return []

    cameras = []
    current_id = None
    for line in stdout.decode("utf-8", errors="replace").splitlines():
        line = line.strip()
        if line.startswith("Id:"):
            current_id = line.split(":", 1)[1].strip()
        if line.startswith("Name:") and current_id:
            cameras.append({"id": current_id, "name": line.split(":", 1)[1].strip(), "type": "opencv"})
            current_id = None
    return cameras
