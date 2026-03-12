"""Generic MCP server for robot control via dynamic drivers."""

import json
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from bridge_core.driver_loader import DriverLoader
from bridge_core.sandbox import exec_in_env
from bridge_core.task_manager import TaskManager

DEFAULT_WORKSPACE = Path.home() / ".nanobot" / "workspace"


def create_server(workspace: Path | None = None) -> FastMCP:
    """Create and configure the MCP server."""
    ws = workspace or DEFAULT_WORKSPACE
    drivers_dir = ws / "drivers"
    drivers_dir.mkdir(parents=True, exist_ok=True)

    mcp = FastMCP("nanobot-robot-bridge")
    loader = DriverLoader(drivers_dir)
    tasks = TaskManager()

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
        })

    @mcp.tool()
    async def exec_in_env(code: str, timeout: int = 30) -> str:
        """Execute Python code in the bridge's environment. For exploration and debugging."""
        from bridge_core.sandbox import exec_in_env as _exec
        result = await _exec(code, timeout=timeout)
        return json.dumps(result)

    @mcp.tool()
    async def load_driver(name: str, reload: bool = False) -> str:
        """Load a driver from workspace/drivers/{name}.py. Use reload=true to pick up changes."""
        try:
            driver = loader.load(name, reload=reload)
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
        """Call a method on a loaded driver.

        Instant methods return results directly.
        Streaming methods return a task_id for background execution.
        """
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

    return mcp


def main():
    """Entry point for CLI: nanobot-robot-bridge"""
    import argparse
    import os

    parser = argparse.ArgumentParser(description="nanobot robot bridge MCP server")
    parser.add_argument("--workspace", type=str, default=os.environ.get("NANOBOT_WORKSPACE", ""))
    args = parser.parse_args()

    ws = Path(args.workspace) if args.workspace else DEFAULT_WORKSPACE
    server = create_server(workspace=ws)
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
