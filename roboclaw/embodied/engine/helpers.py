"""Shared helpers for embodied tool operations."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from roboclaw.embodied.manifest import Manifest
from roboclaw.embodied.manifest.binding import Binding
from roboclaw.embodied.manifest.helpers import ensure_bimanual_cal_dir, get_roboclaw_home

_NO_TTY_MSG = "This action requires a local terminal. Run: roboclaw agent"
_BIMANUAL_ID = "bimanual"
_DEFAULT_REPLAY_ROOT = Path("~/.cache/huggingface/lerobot").expanduser()
_DATASET_SLUG_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$")


class ActionError(Exception):
    """User-facing embodied action error."""


def _resolve_action_arms(manifest: Manifest, kwargs: dict[str, Any]) -> list[Binding]:
    try:
        return _resolve_arms(manifest, kwargs.get("arms", ""))
    except ValueError as exc:
        raise ActionError(str(exc)) from exc


def _resolve_arms(manifest: Manifest, arms_str: str) -> list[Binding]:
    configured = manifest.arms
    if not configured:
        return []
    ports = _split_arm_tokens(arms_str)
    if not ports:
        return list(configured)
    resolved: list[Binding] = []
    seen: set[str] = set()
    for port in ports:
        if port in seen:
            raise ValueError(f"Duplicate arm port '{port}' in arms.")
        seen.add(port)
        arm = next((item for item in configured if item.port == port), None)
        if arm is None:
            raise ValueError(f"No arm with port '{port}' found in manifest.")
        resolved.append(arm)
    return resolved


def _split_arm_tokens(arms_str: str) -> list[str]:
    if not arms_str:
        return []
    return [token.strip() for token in arms_str.split(",") if token.strip()]


def group_arms(arms: list[Binding]) -> dict[str, list[Binding]]:
    grouped: dict[str, list[Binding]] = {"followers": [], "leaders": []}
    for arm in arms:
        if arm.is_follower:
            grouped["followers"].append(arm)
            continue
        if arm.is_leader:
            grouped["leaders"].append(arm)
    # Sort by alias so that "left_*" comes before "right_*".
    # Bimanual callers rely on [0]=left, [1]=right; without sorting,
    # the order depends on manifest array position which is fragile.
    for role in ("followers", "leaders"):
        if len(grouped[role]) == 2:
            grouped[role].sort(key=lambda a: (0 if "left" in a.alias else 1))
    return grouped


def _validate_pairing(followers: list[Binding], leaders: list[Binding]) -> str | None:
    if not followers:
        return "No follower arms configured."
    if not leaders:
        return "No leader arms configured."
    if len(followers) != len(leaders):
        return f"Follower/leader count mismatch: {len(followers)} followers, {len(leaders)} leaders."
    if len(followers) not in {1, 2}:
        return f"Unsupported arm count: {len(followers)}. Use 1 (single) or 2 (bimanual)."
    return None


async def _run_tty(
    tty_handoff: Any, runner: Any, argv: list[str], label: str,
) -> tuple[int, str]:
    await tty_handoff(start=True, label=label)
    try:
        return await runner.run_interactive(argv)
    finally:
        await tty_handoff(start=False, label=label)


async def _run(runner: Any, argv: list[str]) -> str:
    returncode, stdout, stderr = await runner.run(argv)
    if returncode != 0:
        return f"Command failed (exit {returncode}).\nstdout: {stdout}\nstderr: {stderr}"
    return stdout or "Done."


def _is_interrupted(returncode: int) -> bool:
    return returncode in {130, -2}


def _format_tty_failure(prefix: str, returncode: int, stderr_text: str) -> str:
    message = f"{prefix} (exit {returncode})."
    stderr_text = stderr_text.strip()
    if not stderr_text:
        return message
    return f"{message}\nstderr: {stderr_text}"


def dataset_root(manifest: Manifest, fallback: Path | None = None) -> Path:
    root = manifest.snapshot.get("datasets", {}).get("root", "")
    if root:
        return Path(root).expanduser()
    if fallback is not None:
        return fallback.expanduser()
    return get_roboclaw_home() / "workspace" / "embodied" / "datasets"


def dataset_path(
    manifest: Manifest, dataset_name: str, fallback: Path | None = None,
) -> Path:
    return dataset_root(manifest, fallback) / "local" / dataset_name


def _validate_dataset_name(dataset_name: str) -> str | None:
    if not dataset_name or not _DATASET_SLUG_RE.match(dataset_name):
        return "dataset_name must be a non-empty ASCII slug (letters, numbers, underscores, hyphens)."
    return None


def _arm_id(arm: Binding) -> str:
    arm_id = arm.arm_id
    if not arm_id:
        raise ValueError(f"Arm '{arm.alias}' has no serial-based calibration_dir.")
    return arm_id


def _camera_previews_dir() -> Path:
    return get_roboclaw_home() / "workspace" / "embodied" / "camera_previews"


def _logs_dir() -> Path:
    """Return the embodied jobs log directory under ROBOCLAW_HOME."""
    return get_roboclaw_home() / "workspace" / "embodied" / "jobs"


# ---------------------------------------------------------------------------
# Shared argv builders (used by CLI execute.py and EmbodiedService)
# ---------------------------------------------------------------------------


@dataclass
class _PreparedContext:
    controller: "ArmCommandBuilder"  # noqa: F821
    followers: list[Binding]
    leaders: list[Binding]
    cameras: dict[str, Any]
    display_kwargs: dict[str, Any]


def _prepare_common(
    manifest: Manifest,
    kwargs: dict[str, Any] | None = None,
    *,
    display_data: bool = False,
    display_ip: str = "",
    display_port: int = 0,
    skip_cameras: bool = False,
) -> _PreparedContext:
    """Shared preparation for teleop/record: resolve arms, cameras, display."""
    from roboclaw.embodied.engine.command_builder import builder_for_arms
    from roboclaw.embodied.sensor.camera import resolve_cameras

    kwargs = kwargs or {}
    grouped = group_arms(_resolve_action_arms(manifest, kwargs))
    error = _validate_pairing(grouped["followers"], grouped["leaders"])
    if error:
        raise ActionError(error)
    all_arms = grouped["followers"] + grouped["leaders"]
    controller = builder_for_arms(all_arms)
    cameras = {} if skip_cameras else resolve_cameras(manifest.cameras)
    return _PreparedContext(
        controller=controller,
        followers=grouped["followers"],
        leaders=grouped["leaders"],
        cameras=cameras,
        display_kwargs=_display_kwargs(display_data, display_ip, display_port),
    )


def prepare_teleop(
    manifest: Manifest,
    kwargs: dict[str, Any] | None = None,
    *,
    display_data: bool = False,
    display_ip: str = "",
    display_port: int = 0,
) -> list[str]:
    """Build teleop argv from manifest. Returns argv.

    Raises ActionError on validation failure.
    """
    ctx = _prepare_common(
        manifest, kwargs,
        display_data=display_data, display_ip=display_ip, display_port=display_port,
    )

    if len(ctx.followers) == 1:
        return ctx.controller.teleoperate(
            robot_type=ctx.followers[0].type_name,
            robot_port=ctx.followers[0].port,
            robot_cal_dir=ctx.followers[0].calibration_dir,
            robot_id=_arm_id(ctx.followers[0]),
            teleop_type=ctx.leaders[0].type_name,
            teleop_port=ctx.leaders[0].port,
            teleop_cal_dir=ctx.leaders[0].calibration_dir,
            teleop_id=_arm_id(ctx.leaders[0]),
            cameras=ctx.cameras,
            **ctx.display_kwargs,
        )

    robot_dir = ensure_bimanual_cal_dir(ctx.followers[0], ctx.followers[1], "followers")
    teleop_dir = ensure_bimanual_cal_dir(ctx.leaders[0], ctx.leaders[1], "leaders")
    return ctx.controller.teleoperate_bimanual(
        robot_id=_BIMANUAL_ID,
        robot_cal_dir=robot_dir,
        left_robot=ctx.followers[0],
        right_robot=ctx.followers[1],
        teleop_id=_BIMANUAL_ID,
        teleop_cal_dir=teleop_dir,
        left_teleop=ctx.leaders[0],
        right_teleop=ctx.leaders[1],
        cameras=ctx.cameras,
        **ctx.display_kwargs,
    )


def prepare_record(
    manifest: Manifest,
    kwargs: dict[str, Any],
    *,
    display_data: bool = False,
    display_ip: str = "",
    display_port: int = 0,
) -> tuple[list[str], str, str]:
    """Build record argv from manifest. Returns (argv, dataset_name, dataset_root).

    Raises ActionError on validation failure.
    """
    from datetime import datetime

    ctx = _prepare_common(
        manifest, kwargs,
        display_data=display_data, display_ip=display_ip, display_port=display_port,
        skip_cameras=kwargs.get("use_cameras") is False,
    )

    # Resolve dataset name
    user_specified = "dataset_name" in kwargs
    if user_specified:
        dataset_name = kwargs["dataset_name"]
    else:
        dataset_name = f"rec_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    name_error = _validate_dataset_name(dataset_name)
    if name_error:
        raise ActionError(name_error)

    ds_path = dataset_path(manifest, dataset_name)
    resume = user_specified and ds_path.exists()

    record_kwargs: dict[str, Any] = {
        "cameras": ctx.cameras,
        "repo_id": f"local/{dataset_name}",
        "task": kwargs.get("task", "default_task"),
        "dataset_root": str(ds_path),
        "push_to_hub": False,
        "fps": kwargs.get("fps", 30),
        "num_episodes": kwargs.get("num_episodes", 10),
    }
    episode_time_s = kwargs.get("episode_time_s")
    if episode_time_s is not None:
        if episode_time_s <= 0:
            raise ActionError("episode_time_s must be positive.")
        record_kwargs["episode_time_s"] = episode_time_s
    reset_time_s = kwargs.get("reset_time_s")
    if reset_time_s is not None:
        if reset_time_s < 0:
            raise ActionError("reset_time_s must be non-negative.")
        record_kwargs["reset_time_s"] = reset_time_s
    if resume:
        record_kwargs["resume"] = True

    if len(ctx.followers) == 1:
        argv = ctx.controller.record(
            robot_type=ctx.followers[0].type_name,
            robot_port=ctx.followers[0].port,
            robot_cal_dir=ctx.followers[0].calibration_dir,
            robot_id=_arm_id(ctx.followers[0]),
            teleop_type=ctx.leaders[0].type_name,
            teleop_port=ctx.leaders[0].port,
            teleop_cal_dir=ctx.leaders[0].calibration_dir,
            teleop_id=_arm_id(ctx.leaders[0]),
            **record_kwargs,
            **ctx.display_kwargs,
        )
        return argv, dataset_name, str(ds_path)

    robot_dir = ensure_bimanual_cal_dir(ctx.followers[0], ctx.followers[1], "followers")
    teleop_dir = ensure_bimanual_cal_dir(ctx.leaders[0], ctx.leaders[1], "leaders")
    argv = ctx.controller.record_bimanual(
        robot_id=_BIMANUAL_ID,
        robot_cal_dir=robot_dir,
        left_robot=ctx.followers[0],
        right_robot=ctx.followers[1],
        teleop_id=_BIMANUAL_ID,
        teleop_cal_dir=teleop_dir,
        left_teleop=ctx.leaders[0],
        right_teleop=ctx.leaders[1],
        **record_kwargs,
        **ctx.display_kwargs,
    )
    return argv, dataset_name, str(ds_path)


def prepare_replay(
    manifest: Manifest,
    kwargs: dict[str, Any],
) -> list[str]:
    """Build replay argv from manifest. Returns argv.

    Raises ActionError on validation failure.
    """
    from roboclaw.embodied.engine.command_builder import builder_for_arms

    grouped = group_arms(_resolve_action_arms(manifest, kwargs))
    followers = grouped["followers"]
    if not followers:
        raise ActionError("No follower arms configured.")
    if len(followers) not in {1, 2}:
        raise ActionError(f"Unsupported follower arm count: {len(followers)}.")

    dataset_name = kwargs.get("dataset_name", "default")
    error = _validate_dataset_name(dataset_name)
    if error:
        raise ActionError(error)
    ds_root = dataset_path(manifest, dataset_name, fallback=_DEFAULT_REPLAY_ROOT)
    episode = kwargs.get("episode", 0)
    fps = kwargs.get("fps", 30)
    controller = builder_for_arms(followers)

    if len(followers) == 1:
        return controller.replay(
            robot_type=followers[0].type_name,
            robot_port=followers[0].port,
            robot_cal_dir=followers[0].calibration_dir,
            robot_id=_arm_id(followers[0]),
            repo_id=f"local/{dataset_name}",
            dataset_root=str(ds_root),
            episode=episode,
            fps=fps,
        )
    robot_dir = ensure_bimanual_cal_dir(followers[0], followers[1], "followers")
    return controller.replay_bimanual(
        robot_id=_BIMANUAL_ID,
        robot_cal_dir=robot_dir,
        left_robot=followers[0],
        right_robot=followers[1],
        repo_id=f"local/{dataset_name}",
        dataset_root=str(ds_root),
        episode=episode,
        fps=fps,
    )


def prepare_infer(
    manifest: Manifest,
    kwargs: dict[str, Any],
) -> list[str]:
    """Build policy inference argv from manifest. Returns argv.

    Raises ActionError on validation failure.
    """
    from datetime import datetime

    from roboclaw.embodied.engine.command_builder import builder_for_arms
    from roboclaw.embodied.learning.act import ACTPipeline
    from roboclaw.embodied.sensor.camera import resolve_cameras

    grouped = group_arms(_resolve_action_arms(manifest, kwargs))
    followers = grouped["followers"]
    if not followers:
        raise ActionError("No follower arms configured.")
    if len(followers) not in {1, 2}:
        raise ActionError(f"Unsupported follower arm count: {len(followers)}.")

    cameras = {} if kwargs.get("use_cameras") is False else resolve_cameras(manifest.cameras)
    policies_root = manifest.snapshot.get("policies", {}).get("root", "")
    checkpoint = kwargs.get("checkpoint_path")
    if not checkpoint:
        source_dataset = kwargs.get("source_dataset", kwargs.get("dataset_name", ""))
        if source_dataset:
            checkpoint = ACTPipeline().checkpoint_path(str(Path(policies_root) / source_dataset))
        else:
            checkpoint = ACTPipeline().checkpoint_path(policies_root)

    dataset_name = kwargs.get("dataset_name")
    if not dataset_name:
        dataset_name = f"eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    if not dataset_name.startswith("eval_"):
        dataset_name = f"eval_{dataset_name}"
    name_error = _validate_dataset_name(dataset_name)
    if name_error:
        raise ActionError(name_error)

    ds_path = dataset_path(manifest, dataset_name)
    resume = ds_path.exists()
    controller = builder_for_arms(followers)
    policy_kwargs = {
        "cameras": cameras,
        "policy_path": checkpoint,
        "repo_id": f"local/{dataset_name}",
        "dataset_root": str(ds_path),
        "task": kwargs.get("task", "eval"),
        "num_episodes": kwargs.get("num_episodes", 1),
        "resume": resume,
    }

    if len(followers) == 1:
        return controller.run_policy(
            robot_type=followers[0].type_name,
            robot_port=followers[0].port,
            robot_cal_dir=followers[0].calibration_dir,
            robot_id=_arm_id(followers[0]),
            **policy_kwargs,
        )
    robot_dir = ensure_bimanual_cal_dir(followers[0], followers[1], "followers")
    return controller.run_policy_bimanual(
        robot_id=_BIMANUAL_ID,
        robot_cal_dir=robot_dir,
        left_robot=followers[0],
        right_robot=followers[1],
        **policy_kwargs,
    )


def _display_kwargs(
    display_data: bool, display_ip: str, display_port: int,
) -> dict[str, Any]:
    """Build display keyword args for ArmCommandBuilder methods."""
    if not display_data:
        return {}
    result: dict[str, Any] = {"display_data": True}
    if display_ip:
        result["display_ip"] = display_ip
    if display_port:
        result["display_port"] = display_port
    return result
