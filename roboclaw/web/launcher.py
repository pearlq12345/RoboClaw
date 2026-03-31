"""One-command launcher for the RoboClaw web UI."""

from __future__ import annotations

import shutil
import socket
import subprocess
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIR = REPO_ROOT / "roboclaw-web"


def ensure_command(name: str) -> None:
    """Fail fast when a required command is missing."""
    if shutil.which(name):
        return
    raise SystemExit(f"Required command '{name}' is not available on PATH.")

def ensure_frontend_dependencies() -> None:
    """Install frontend deps on first run."""
    ensure_command("npm")
    if (FRONTEND_DIR / "node_modules").exists():
        return
    print("Installing frontend dependencies with npm...", flush=True)
    subprocess.run(
        ["npm", "--prefix", str(FRONTEND_DIR), "install"],
        cwd=REPO_ROOT,
        check=True,
    )


def build_backend_command(host: str, port: int) -> list[str]:
    """Return the web backend startup command."""
    return [
        "uv",
        "run",
        "--extra",
        "web",
        "--locked",
        "roboclaw",
        "web",
        "start",
        "--host",
        host,
        "--port",
        str(port),
    ]


def build_frontend_command(host: str, port: int) -> list[str]:
    """Return the Vite development server startup command."""
    return [
        "npm",
        "--prefix",
        str(FRONTEND_DIR),
        "run",
        "dev",
        "--",
        "--host",
        host,
        "--port",
        str(port),
    ]


def terminate_process(process: subprocess.Popen[bytes]) -> None:
    """Terminate a child process and fall back to kill if needed."""
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def backend_healthcheck(host: str, port: int) -> bool:
    """Return whether the backend health endpoint responds successfully."""
    try:
        with urlopen(f"http://{host}:{port}/api/health", timeout=1.0) as response:
            return response.status == 200
    except (OSError, URLError):
        return False


def wait_for_backend_ready(
    process: subprocess.Popen[bytes] | None,
    host: str,
    port: int,
    timeout_s: float = 20.0,
) -> bool:
    """Wait until the backend is healthy or the process exits."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if backend_healthcheck(host, port):
            return True
        if process is not None and process.poll() is not None:
            return False
        time.sleep(0.25)
    return backend_healthcheck(host, port)


def port_in_use(host: str, port: int) -> bool:
    """Return whether a TCP port is already occupied."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def launch(
    *,
    backend_host: str = "127.0.0.1",
    backend_port: int = 8765,
    frontend_host: str = "127.0.0.1",
    frontend_port: int = 5173,
) -> int:
    """Run backend + frontend together from one command."""
    ensure_command("uv")
    ensure_frontend_dependencies()

    backend: subprocess.Popen[bytes] | None = None
    if backend_healthcheck(backend_host, backend_port):
        print(f"Reusing existing RoboClaw backend at http://{backend_host}:{backend_port}", flush=True)
    else:
        if port_in_use(backend_host, backend_port):
            print(
                f"Port {backend_port} is occupied, but the RoboClaw backend healthcheck did not respond. "
                "Stop the stale process or change the port before retrying.",
                flush=True,
            )
            return 1

        print("Starting RoboClaw backend...", flush=True)
        backend = subprocess.Popen(
            build_backend_command(backend_host, backend_port),
            cwd=REPO_ROOT,
        )
        if not wait_for_backend_ready(backend, backend_host, backend_port):
            print("RoboClaw backend failed to become ready. Check the backend logs above.", flush=True)
            if backend.poll() is None:
                terminate_process(backend)
            return backend.returncode or 1

    print("Starting RoboClaw frontend...", flush=True)
    frontend = subprocess.Popen(
        build_frontend_command(frontend_host, frontend_port),
        cwd=REPO_ROOT,
    )

    print(f"RoboClaw backend:  http://{backend_host}:{backend_port}", flush=True)
    print(f"RoboClaw frontend: http://{frontend_host}:{frontend_port}", flush=True)

    try:
        while True:
            backend_rc = backend.poll() if backend is not None else None
            frontend_rc = frontend.poll()
            if backend_rc is not None:
                terminate_process(frontend)
                return backend_rc
            if frontend_rc is not None:
                if backend is not None:
                    terminate_process(backend)
                return frontend_rc
            time.sleep(0.5)
    except KeyboardInterrupt:
        terminate_process(frontend)
        if backend is not None:
            terminate_process(backend)
        return 130


def main() -> None:
    raise SystemExit(launch())
