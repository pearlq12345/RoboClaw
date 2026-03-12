"""Sim MCP server — same driver pattern as robot-bridge, plus physics tools."""

import json
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from bridge_core.driver_loader import DriverLoader
from bridge_core.sandbox import exec_in_env as _exec_in_env
from bridge_core.task_manager import TaskManager
from sim_bridge.physics import PhysicsEngine

DEFAULT_WORKSPACE = Path.home() / ".nanobot" / "workspace"


class _LazyEngine:
    """Lazy wrapper: creates PhysicsEngine on first access."""

    def __init__(self, headless: bool = True):
        self._headless = headless
        self._engine: PhysicsEngine | None = None

    def _ensure(self) -> PhysicsEngine:
        if self._engine is None:
            self._engine = PhysicsEngine(headless=self._headless)
            self._engine.load_plane()
        return self._engine

    @property
    def initialized(self) -> bool:
        return self._engine is not None

    def __getattr__(self, name: str):
        return getattr(self._ensure(), name)


def create_server(workspace: Path | None = None, headless: bool = True) -> FastMCP:
    ws = workspace or DEFAULT_WORKSPACE
    drivers_dir = ws / "drivers"
    drivers_dir.mkdir(parents=True, exist_ok=True)

    mcp = FastMCP("nanobot-sim-bridge")
    loader = DriverLoader(drivers_dir)
    tasks = TaskManager()
    engine = _LazyEngine(headless=headless)

    # === Base tools (same as robot-bridge) ===

    @mcp.tool()
    async def probe_env() -> str:
        """List Python environment info, installed packages, and loaded drivers."""
        try:
            pip_out = subprocess.check_output(
                [sys.executable, "-m", "pip", "list", "--format=columns"],
                timeout=10, stderr=subprocess.DEVNULL,
            ).decode().strip()
        except Exception:
            pip_out = "(unavailable)"

        return json.dumps({
            "python_version": platform.python_version(),
            "python_path": sys.executable,
            "platform": platform.platform(),
            "packages": pip_out,
            "drivers_dir": str(drivers_dir),
            "available_drivers": loader.list_available(),
            "loaded_drivers": list(loader.loaded.keys()),
            "sim_backend": "pybullet",
            "sim_initialized": engine.initialized,
            "robots_loaded": list(engine._engine._robots.keys()) if engine.initialized else [],
        })

    @mcp.tool()
    async def exec_in_env(code: str, timeout: int = 30) -> str:
        """Execute Python code in the bridge's environment. For exploration and debugging."""
        result = await _exec_in_env(code, timeout=timeout)
        return json.dumps(result)

    @mcp.tool()
    async def load_driver(name: str, reload: bool = False) -> str:
        """Load a driver from workspace/drivers/{name}.py. Use reload=true to pick up changes."""
        try:
            driver = loader.load(name, reload=reload)
            # Inject physics engine into driver if it has a _physics attribute
            if hasattr(driver, "_physics"):
                driver._physics = engine._ensure()
            return json.dumps({
                "status": "loaded",
                "name": driver.name,
                "description": getattr(driver, "description", ""),
                "methods": list(driver.methods.keys()),
                "method_details": driver.methods,
            })
        except Exception as e:
            return json.dumps({"error": f"{type(e).__name__}: {e}"})

    @mcp.tool()
    async def call(driver: str, method: str, params: dict[str, Any] | None = None) -> str:
        """Call a method on a loaded driver."""
        instance = loader.loaded.get(driver)
        if not instance:
            return json.dumps({"error": f"Driver '{driver}' not loaded. Use load_driver first."})

        method_info = instance.methods.get(method)
        if not method_info:
            available = list(instance.methods.keys())
            return json.dumps({"error": f"Unknown method '{method}'. Available: {available}"})

        fn = getattr(instance, method, None)
        if fn is None:
            return json.dumps({"error": f"Driver has no implementation for '{method}'"})

        call_params = params or {}

        try:
            if method_info.get("type") == "streaming":
                async def _run(*, _report_status=None):
                    return await fn(**call_params, _report_status=_report_status)
                task_id = tasks.start(_run)
                return json.dumps({"task_id": task_id, "status": "started"})
            else:
                result = await fn(**call_params)
                return json.dumps(result)
        except Exception as e:
            return json.dumps({"error": f"{type(e).__name__}: {e}"})

    @mcp.tool()
    async def task_status(task_id: str) -> str:
        """Check the status of a background streaming task."""
        return json.dumps(tasks.get_status(task_id))

    @mcp.tool()
    async def stop_task(task_id: str) -> str:
        """Stop a running background task."""
        return json.dumps(tasks.stop(task_id))

    # === Sim-specific tools ===

    @mcp.tool()
    async def sim_load_robot(urdf_path: str, position: list[float] | None = None) -> str:
        """Load a robot URDF into the simulation. Initializes the physics engine on first call."""
        try:
            robot_id = engine.load_urdf(urdf_path, base_position=position)
            info = engine.get_robot_info(robot_id)
            return json.dumps({"status": "loaded", **info})
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def sim_get_joints(robot_id: int = 0) -> str:
        """Get current joint positions from simulation."""
        try:
            joints = engine.get_joint_positions(robot_id)
            return json.dumps(joints)
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def sim_set_joints(robot_id: int, positions: dict[str, float]) -> str:
        """Set joint target positions and step sim to apply."""
        try:
            engine.set_joint_positions(robot_id, positions)
            engine.step(steps=10)
            joints = engine.get_joint_positions(robot_id)
            return json.dumps({"status": "ok", "joints": joints})
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def sim_step(steps: int = 240) -> str:
        """Step the physics simulation forward."""
        engine.step(steps=steps)
        return json.dumps({"status": "ok", "steps": steps})

    @mcp.tool()
    async def sim_reset() -> str:
        """Reset the entire simulation (removes all robots)."""
        engine.reset()
        engine.load_plane()
        return json.dumps({"status": "reset"})

    @mcp.tool()
    async def sim_log(tail: int = 50) -> str:
        """Read recent sim-bridge log (PyBullet output, errors, etc.)."""
        from sim_bridge.physics import _ensure_log_file
        log_path = _ensure_log_file()
        if not log_path.exists():
            return json.dumps({"log": "(no log yet)", "path": str(log_path)})
        lines = log_path.read_text().splitlines()
        return json.dumps({
            "path": str(log_path),
            "total_lines": len(lines),
            "tail": lines[-tail:],
        })

    return mcp


def main():
    """Entry point for CLI: nanobot-sim-bridge"""
    import argparse
    import io
    import os

    parser = argparse.ArgumentParser(description="nanobot sim bridge MCP server")
    parser.add_argument("--workspace", type=str, default=os.environ.get("NANOBOT_WORKSPACE", ""))
    parser.add_argument("--gui", action="store_true", default=False)
    args = parser.parse_args()

    ws = Path(args.workspace) if args.workspace else DEFAULT_WORKSPACE

    if args.gui and os.environ.get("DISPLAY"):
        # PyBullet GUI mode: the C library prints debug text to fd 1,
        # which corrupts MCP's JSON-RPC on stdout.  Fix:
        #   1. Duplicate the real fd 1 so MCP can still write JSON-RPC.
        #   2. Redirect fd 1 to the log file (PyBullet C code writes here).
        #   3. Point sys.stdout at the saved fd so Python I/O (MCP) is clean.
        from sim_bridge.physics import _ensure_log_file
        log_path = _ensure_log_file()
        real_stdout_fd = os.dup(1)  # save original fd 1
        log_fd = os.open(str(log_path), os.O_WRONLY | os.O_CREAT | os.O_APPEND)
        os.dup2(log_fd, 1)  # fd 1 → log (PyBullet writes here)
        os.close(log_fd)
        sys.stdout = io.TextIOWrapper(
            io.FileIO(real_stdout_fd, "w", closefd=False),
            line_buffering=True,
        )

    server = create_server(workspace=ws, headless=not args.gui)
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
