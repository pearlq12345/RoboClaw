"""Tests for the one-command web launcher."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

from roboclaw.web import launcher


def test_build_backend_command() -> None:
    assert launcher.build_backend_command("127.0.0.1", 8765) == [
        "uv",
        "run",
        "--extra",
        "web",
        "--locked",
        "roboclaw",
        "web",
        "start",
        "--host",
        "127.0.0.1",
        "--port",
        "8765",
    ]


def test_build_frontend_command() -> None:
    assert launcher.build_frontend_command("127.0.0.1", 5173) == [
        "npm",
        "--prefix",
        str(launcher.FRONTEND_DIR),
        "run",
        "dev",
        "--",
        "--host",
        "127.0.0.1",
        "--port",
        "5173",
    ]


def test_ensure_frontend_dependencies_skips_existing_node_modules(tmp_path: Path) -> None:
    frontend_dir = tmp_path / "roboclaw-web"
    node_modules = frontend_dir / "node_modules"
    node_modules.mkdir(parents=True)

    with (
        patch.object(launcher, "FRONTEND_DIR", frontend_dir),
        patch.object(launcher, "ensure_command") as mock_ensure,
        patch("subprocess.run") as mock_run,
    ):
        launcher.ensure_frontend_dependencies()

    mock_ensure.assert_called_once_with("npm")
    mock_run.assert_not_called()


def test_launch_stops_when_backend_never_becomes_ready() -> None:
    backend = Mock()
    backend.poll.return_value = 1
    backend.returncode = 1

    with (
        patch.object(launcher, "ensure_command"),
        patch.object(launcher, "ensure_frontend_dependencies"),
        patch.object(launcher, "backend_healthcheck", return_value=False),
        patch.object(launcher, "port_in_use", return_value=False),
        patch.object(launcher, "wait_for_backend_ready", return_value=False),
        patch("subprocess.Popen", return_value=backend) as mock_popen,
    ):
        result = launcher.launch()

    assert result == 1
    mock_popen.assert_called_once()
