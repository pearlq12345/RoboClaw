"""CLI adapter for interactive hardware setup (identify flow)."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from roboclaw.embodied.service import EmbodiedService


async def run_cli_setup(
    service: EmbodiedService,
    manifest: Any,
    kwargs: dict[str, Any],
    tty_handoff: Any,
) -> str:
    """Drive the setup identify flow from the terminal."""
    await tty_handoff(start=True, label="setup-identify")
    try:
        return await asyncio.to_thread(_interactive_setup, service, kwargs)
    except Exception:
        service.setup.reset()
        raise
    finally:
        await tty_handoff(start=False, label="setup-identify")


def _interactive_setup(service: EmbodiedService, kwargs: dict[str, Any]) -> str:
    """Synchronous interactive setup — runs in a thread."""
    model = kwargs.get("model", "")
    if not model:
        model = _prompt_model()

    # Scan
    print(f"\nScanning for {model} hardware...")
    result = service.setup.run_full_scan(model)
    ports = result["ports"]
    cameras = result["cameras"]
    print(f"Found {len(ports)} serial port(s) and {len(cameras)} camera(s).")

    if not ports and not cameras:
        return "No hardware detected."

    # Show ports
    for i, port in enumerate(ports):
        port_id = port.by_id or port.dev or "?"
        print(f"  [{i}] {port_id}  ({len(port.motor_ids)} motors)")

    # Identify arms via motion detection
    if ports:
        _identify_arms(service, model, ports)

    # Name cameras
    if cameras:
        _name_cameras(service, cameras)

    # Show assignments and commit
    session = service.setup.to_dict()
    assignments = session["assignments"]
    if not assignments:
        return "No assignments made."

    print(f"\n{len(assignments)} assignment(s):")
    for a in assignments:
        print(f"  {a['alias']} -> {a['spec_name']} ({a['interface_stable_id'][:30]}...)")

    confirm = input("\nCommit these assignments? (y/n): ").strip().lower()
    if confirm != "y":
        service.setup.reset()
        return "Setup cancelled."

    count = service.setup.commit()
    return f"Setup complete. {count} binding(s) committed to manifest."


def _prompt_model() -> str:
    """Ask user which robot model they have."""
    print("\nWhich robot model?")
    print("  [1] SO-101")
    print("  [2] Koch")
    while True:
        choice = input("Select (1/2): ").strip()
        if choice == "1":
            return "so101"
        if choice == "2":
            return "koch"
        print("Invalid choice. Enter 1 or 2.")


def _identify_arms(service: EmbodiedService, model: str, ports: list) -> None:
    """Motion detection loop to identify which arm is which."""
    from roboclaw.embodied.interface import SerialInterface

    serial_ports = [p for p in ports if isinstance(p, SerialInterface)]
    if not serial_ports:
        return

    print("\n--- Arm Identification ---")
    print("Move one arm at a time. The system will detect which port moved.")

    service.setup.start_motion_detection()
    try:
        while _assign_next_arm(service, model):
            pass
    finally:
        service.setup.stop_motion_detection()


def _assign_next_arm(service: EmbodiedService, model: str) -> bool:
    """Detect and assign one arm. Returns True to continue, False to stop."""
    from roboclaw.embodied.interface import SerialInterface

    unassigned = [u for u in service.setup.unassigned if isinstance(u, SerialInterface)]
    if not unassigned:
        print("All serial ports assigned.")
        return False

    print(f"\n{len(unassigned)} unassigned port(s). Move an arm...")
    moved_id = _wait_for_motion(service)
    if moved_id is None:
        return False

    print(f"\nDetected motion on: {moved_id[:40]}")
    alias = input("  Alias (e.g. left_follower, right_leader): ").strip()
    if not alias:
        print("  Skipped.")
        return True

    spec_name = _derive_spec(model, alias)
    try:
        service.setup.assign(moved_id, alias, spec_name)
    except ValueError as exc:
        print(f"  Error: {exc}")
        return True
    print(f"  Assigned: {alias} -> {spec_name}")
    return input("  Assign more arms? (y/n): ").strip().lower() == "y"


def _derive_spec(model: str, alias: str) -> str:
    """Derive spec_name from model + alias role hint."""
    if "leader" in alias:
        return f"{model}_leader"
    if "follower" in alias:
        return f"{model}_follower"
    print(f"  (defaulting to {model}_follower)")
    return f"{model}_follower"


def _wait_for_motion(service: EmbodiedService, timeout_s: float = 30.0) -> str | None:
    """Poll motion until one port moves. Returns stable_id or None on timeout."""
    import time

    start = time.monotonic()
    while time.monotonic() - start < timeout_s:
        results = service.setup.poll_motion()
        for r in results:
            if r["moved"]:
                return r["stable_id"]
        time.sleep(0.1)

    print("  Timeout -- no motion detected.")
    return None


def _name_cameras(service: EmbodiedService, cameras: list) -> None:
    """Prompt user to name each detected camera."""
    from roboclaw.embodied.interface import VideoInterface

    video_cameras = [c for c in cameras if isinstance(c, VideoInterface)]
    if not video_cameras:
        return

    print("\n--- Camera Naming ---")
    for i, cam in enumerate(video_cameras):
        dev = cam.dev or "?"
        res = f"{cam.width}x{cam.height}" if cam.width else "?"
        print(f"  [{i}] {dev} ({res} @ {cam.fps}fps)")
        name = input(f"  Name for camera {i} (or Enter to skip): ").strip()
        if name:
            try:
                service.setup.assign(cam.stable_id, name, "opencv")
                print(f"  Assigned: {name}")
            except ValueError as exc:
                print(f"  Error: {exc}")
