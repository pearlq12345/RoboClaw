"""ReplaySession - dataset replay on follower arms."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from roboclaw.embodied.engine.command_builder import builder_for_arms
from roboclaw.embodied.engine.helpers import (
    _BIMANUAL_ID,
    _DEFAULT_REPLAY_ROOT,
    _NO_TTY_MSG,
    _arm_id,
    _format_tty_failure,
    _is_interrupted,
    _resolve_action_arms,
    _run_tty,
    _validate_dataset_name,
    dataset_path,
    group_arms,
)
from roboclaw.embodied.manifest.binding import Binding

if TYPE_CHECKING:
    from roboclaw.embodied.manifest import Manifest
    from roboclaw.embodied.service import EmbodiedService


class ReplaySession:
    def __init__(self, parent: EmbodiedService):
        self._parent = parent

    async def replay(
        self,
        manifest: Manifest,
        kwargs: dict[str, Any],
        tty_handoff: Any,
    ) -> str:
        self._parent.acquire_embodiment("replaying")
        try:
            if not tty_handoff:
                return _NO_TTY_MSG
            selected = _resolve_action_arms(manifest, kwargs)
            grouped = group_arms(selected)
            if kwargs.get("arms", "") and grouped["leaders"]:
                return "Replay only supports follower arms. Remove leader arm ports from arms."
            followers = grouped["followers"]
            if not followers:
                return "No follower arm configured."
            if len(followers) not in {1, 2}:
                return f"Unsupported follower arm count: {len(followers)}. Use 1 (single) or 2 (bimanual)."

            dataset_name = kwargs.get("dataset_name", "default")
            error = _validate_dataset_name(dataset_name)
            if error:
                return error
            ds_root = dataset_path(manifest, dataset_name, fallback=_DEFAULT_REPLAY_ROOT)
            episode = kwargs.get("episode", 0)
            fps = kwargs.get("fps", 30)
            controller = builder_for_arms(followers)
            if len(followers) == 1:
                return await self._replay_single(
                    controller,
                    followers[0],
                    dataset_name,
                    ds_root,
                    episode,
                    fps,
                    tty_handoff,
                )
            return await self._replay_bimanual(
                controller,
                followers,
                dataset_name,
                ds_root,
                episode,
                fps,
                tty_handoff,
            )
        finally:
            self._parent.release_embodiment()

    async def _replay_single(
        self,
        controller: Any,
        follower: Binding,
        dataset_name: str,
        dataset_root: Path,
        episode: int,
        fps: int,
        tty_handoff: Any,
    ) -> str:
        from roboclaw.embodied.runner import LocalLeRobotRunner

        argv = controller.replay(
            robot_type=follower.type_name,
            robot_port=follower.port,
            robot_cal_dir=follower.calibration_dir,
            robot_id=_arm_id(follower),
            repo_id=f"local/{dataset_name}",
            dataset_root=str(dataset_root),
            episode=episode,
            fps=fps,
        )
        rc, stderr_text = await _run_tty(tty_handoff, LocalLeRobotRunner(), argv, "lerobot-replay")
        if _is_interrupted(rc):
            return "interrupted"
        if rc == 0:
            return "Replay finished."
        return _format_tty_failure("Replay failed", rc, stderr_text)

    async def _replay_bimanual(
        self,
        controller: Any,
        followers: list[Binding],
        dataset_name: str,
        dataset_root: Path,
        episode: int,
        fps: int,
        tty_handoff: Any,
    ) -> str:
        from roboclaw.embodied.manifest.helpers import ensure_bimanual_cal_dir
        from roboclaw.embodied.runner import LocalLeRobotRunner

        robot_dir = ensure_bimanual_cal_dir(followers[0], followers[1], "followers")
        argv = controller.replay_bimanual(
            robot_id=_BIMANUAL_ID,
            robot_cal_dir=robot_dir,
            left_robot=followers[0],
            right_robot=followers[1],
            repo_id=f"local/{dataset_name}",
            dataset_root=str(dataset_root),
            episode=episode,
            fps=fps,
        )
        rc, stderr_text = await _run_tty(
            tty_handoff,
            LocalLeRobotRunner(),
            argv,
            "lerobot-replay (bimanual)",
        )
        if _is_interrupted(rc):
            return "interrupted"
        if rc == 0:
            return "Replay finished."
        return _format_tty_failure("Replay failed", rc, stderr_text)
