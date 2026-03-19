from pathlib import Path

from roboclaw.config.loader import CONFIG_PATH_ENV, get_config_path
from roboclaw.config.paths import (
    WORKSPACE_PATH_ENV,
    get_calibration_dir,
    get_robot_calibration_file,
    get_calibration_root,
    get_bridge_install_dir,
    get_cli_history_path,
    get_cron_dir,
    get_data_dir,
    get_legacy_sessions_dir,
    get_logs_dir,
    get_media_dir,
    get_runtime_subdir,
    get_workspace_path,
    resolve_active_serial_device_path,
    resolve_serial_by_id_path,
)
from roboclaw.config.schema import Config


def test_runtime_dirs_follow_config_path(monkeypatch, tmp_path: Path) -> None:
    config_file = tmp_path / "instance-a" / "config.json"
    monkeypatch.setattr("roboclaw.config.paths.get_config_path", lambda: config_file)

    assert get_data_dir() == config_file.parent
    assert get_runtime_subdir("cron") == config_file.parent / "cron"
    assert get_cron_dir() == config_file.parent / "cron"
    assert get_logs_dir() == config_file.parent / "logs"


def test_media_dir_supports_channel_namespace(monkeypatch, tmp_path: Path) -> None:
    config_file = tmp_path / "instance-b" / "config.json"
    monkeypatch.setattr("roboclaw.config.paths.get_config_path", lambda: config_file)

    assert get_media_dir() == config_file.parent / "media"
    assert get_media_dir("telegram") == config_file.parent / "media" / "telegram"


def test_calibration_dirs_follow_active_config_root(monkeypatch, tmp_path: Path) -> None:
    config_file = tmp_path / "instance-c" / "config.json"
    monkeypatch.setattr("roboclaw.config.paths.get_config_path", lambda: config_file)

    assert get_calibration_root() == config_file.parent / "calibration"
    assert get_calibration_dir("so101") == config_file.parent / "calibration" / "so101"
    assert get_robot_calibration_file("so101", "so101_real") == config_file.parent / "calibration" / "so101" / "so101_real.json"


def test_shared_and_legacy_paths_remain_global() -> None:
    assert get_cli_history_path() == Path.home() / ".roboclaw" / "history" / "cli_history"
    assert get_bridge_install_dir() == Path.home() / ".roboclaw" / "bridge"
    assert get_legacy_sessions_dir() == Path.home() / ".roboclaw" / "sessions"


def test_workspace_path_is_explicitly_resolved() -> None:
    assert get_workspace_path() == Path.home() / ".roboclaw" / "workspace"
    assert get_workspace_path("~/custom-workspace") == Path.home() / "custom-workspace"


def test_config_path_prefers_environment_override(monkeypatch, tmp_path: Path) -> None:
    env_path = tmp_path / "instance" / "config.json"
    monkeypatch.delenv(CONFIG_PATH_ENV, raising=False)
    assert get_config_path() == Path.home() / ".roboclaw" / "config.json"

    monkeypatch.setenv(CONFIG_PATH_ENV, str(env_path))
    assert get_config_path() == env_path.resolve()


def test_workspace_path_prefers_environment_override(monkeypatch, tmp_path: Path) -> None:
    env_path = tmp_path / "instance-workspace"
    monkeypatch.delenv(WORKSPACE_PATH_ENV, raising=False)
    assert get_workspace_path() == Path.home() / ".roboclaw" / "workspace"

    monkeypatch.setenv(WORKSPACE_PATH_ENV, str(env_path))
    assert get_workspace_path() == env_path
    assert get_workspace_path("~/custom-workspace") == env_path


def test_config_workspace_path_uses_environment_override(monkeypatch, tmp_path: Path) -> None:
    env_path = tmp_path / "env-workspace"
    config = Config()
    config.agents.defaults.workspace = str(tmp_path / "config-workspace")

    monkeypatch.setenv(WORKSPACE_PATH_ENV, str(env_path))

    assert config.workspace_path == env_path


def test_resolve_serial_by_id_path_uses_host_dev_root_for_tty_candidate(
    monkeypatch, tmp_path: Path
) -> None:
    host_dev = tmp_path / "host-dev"
    (host_dev / "serial" / "by-id").mkdir(parents=True)
    target = host_dev / "ttyACM0"
    target.write_text("", encoding="utf-8")
    (host_dev / "serial" / "by-id" / "usb-so101").symlink_to("../../ttyACM0")
    monkeypatch.setenv("ROBOCLAW_HOST_DEV_ROOT", str(host_dev))

    assert resolve_serial_by_id_path("/dev/ttyACM0") == Path("/dev/serial/by-id/usb-so101")


def test_resolve_active_serial_device_path_uses_host_dev_root(monkeypatch, tmp_path: Path) -> None:
    host_dev = tmp_path / "host-dev"
    (host_dev / "serial" / "by-id").mkdir(parents=True)
    target = host_dev / "ttyACM0"
    target.write_text("", encoding="utf-8")
    (host_dev / "serial" / "by-id" / "usb-so101").symlink_to("../../ttyACM0")
    monkeypatch.setenv("ROBOCLAW_HOST_DEV_ROOT", str(host_dev))

    assert resolve_active_serial_device_path("/dev/serial/by-id/usb-so101") == target
