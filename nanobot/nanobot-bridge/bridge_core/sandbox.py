"""Sandboxed Python execution within the bridge's conda environment."""

import asyncio
import sys


async def exec_in_env(code: str, timeout: int = 30) -> dict:
    """Execute Python code in the current environment.

    Runs code as a subprocess using the same Python interpreter.
    Captures stdout, stderr, and exit code.

    Args:
        code: Python source code to execute.
        timeout: Max execution time in seconds.

    Returns:
        Dict with keys: success, stdout, stderr, error, exit_code
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-c", code,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            try:
                await asyncio.wait_for(proc.wait(), timeout=5)
            except asyncio.TimeoutError:
                pass
            return {
                "success": False,
                "stdout": "",
                "stderr": "",
                "error": f"Timeout after {timeout}s",
                "exit_code": -1,
            }

        stdout_str = stdout.decode("utf-8", errors="replace").strip()
        stderr_str = stderr.decode("utf-8", errors="replace").strip()

        return {
            "success": proc.returncode == 0,
            "stdout": stdout_str,
            "stderr": stderr_str,
            "error": "" if proc.returncode == 0 else stderr_str,
            "exit_code": proc.returncode,
        }
    except Exception as e:
        return {
            "success": False,
            "stdout": "",
            "stderr": "",
            "error": str(e),
            "exit_code": -1,
        }
