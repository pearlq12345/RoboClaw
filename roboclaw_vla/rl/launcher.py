"""RLinf launcher for RoboClaw VLA training workflows."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from roboclaw_vla.rl import registry


CONFIG_DIR = Path(__file__).resolve().parents[1] / "config" / "rl"


@dataclass(frozen=True)
class RLinfComponents:
    validate_cfg: Any
    Cluster: Any
    HybridComponentPlacement: Any
    EmbodiedRunner: Any
    EmbodiedFSDPActor: Any
    MultiStepRolloutWorker: Any
    EnvWorker: Any
    OmegaConf: Any
    initialize_config_dir: Any
    compose: Any


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Launch RoboClaw VLA RL training through RLinf actor/rollout/env workers."
    )
    parser.add_argument("--config-name", required=True, help="Hydra config name under roboclaw_vla/config/rl.")
    parser.add_argument("--dataset_path", default=os.environ.get("RLINF_DATASET_PATH", ""))
    parser.add_argument("--checkpoint_path", default=os.environ.get("RLINF_CHECKPOINT_PATH", ""))
    parser.add_argument("--artifact_path", default=os.environ.get("RLINF_ARTIFACT_DIR", "outputs"))
    parser.add_argument(
        "overrides",
        nargs="*",
        help="Hydra overrides, for example actor.optim.lr=5e-7 runner.max_steps=100.",
    )
    return parser.parse_args(argv)


def load_rlinf_components() -> RLinfComponents:
    try:
        from hydra import compose, initialize_config_dir
        from omegaconf import OmegaConf
        from rlinf.config import validate_cfg
        from rlinf.runners.embodied_runner import EmbodiedRunner
        from rlinf.scheduler import Cluster
        from rlinf.utils.placement import HybridComponentPlacement
        from rlinf.workers.actor.fsdp_actor_worker import EmbodiedFSDPActor
        from rlinf.workers.env.env_worker import EnvWorker
        from rlinf.workers.rollout.hf.huggingface_worker import MultiStepRolloutWorker
    except Exception as exc:  # pragma: no cover - depends on remote training image
        raise RuntimeError(
            "RLinf launcher dependencies are not importable. Install hydra-core, "
            "omegaconf, and rlinf in the training image before launching."
        ) from exc

    return RLinfComponents(
        validate_cfg=validate_cfg,
        Cluster=Cluster,
        HybridComponentPlacement=HybridComponentPlacement,
        EmbodiedRunner=EmbodiedRunner,
        EmbodiedFSDPActor=EmbodiedFSDPActor,
        MultiStepRolloutWorker=MultiStepRolloutWorker,
        EnvWorker=EnvWorker,
        OmegaConf=OmegaConf,
        initialize_config_dir=initialize_config_dir,
        compose=compose,
    )


def build_cfg(args: argparse.Namespace, components: RLinfComponents) -> Any:
    config_name = args.config_name.removesuffix(".yaml")
    with components.initialize_config_dir(version_base="1.1", config_dir=str(CONFIG_DIR)):
        cfg = components.compose(config_name=config_name, overrides=list(args.overrides))

    if args.dataset_path:
        components.OmegaConf.update(cfg, "env.train.dataset_path", args.dataset_path, merge=False, force_add=True)
        components.OmegaConf.update(cfg, "env.eval.dataset_path", args.dataset_path, merge=False, force_add=True)
    if args.checkpoint_path:
        components.OmegaConf.update(cfg, "actor.model.model_path", args.checkpoint_path, merge=False, force_add=True)
        components.OmegaConf.update(cfg, "actor.model.processor_path", args.checkpoint_path, merge=False, force_add=True)
        components.OmegaConf.update(cfg, "rollout.model.model_path", args.checkpoint_path, merge=False, force_add=True)
    if args.artifact_path:
        components.OmegaConf.update(cfg, "artifacts.output_dir", args.artifact_path, merge=False, force_add=True)
        components.OmegaConf.update(cfg, "runner.logger.log_path", args.artifact_path, merge=False, force_add=True)

    return components.validate_cfg(cfg)


def _cfg_get(cfg: Any, path: str, default: Any = None) -> Any:
    current = cfg
    for key in path.split("."):
        if isinstance(current, dict):
            current = current.get(key, default)
        else:
            current = getattr(current, key, default)
        if current is default:
            return default
    return current


def select_actor_worker(cfg: Any, components: RLinfComponents) -> Any:
    loss_type = str(_cfg_get(cfg, "algorithm.loss_type", "")).lower()
    if loss_type == "sac":
        try:
            from rlinf.workers.actor.fsdp_sac_actor_worker import EmbodiedSACFSDPPolicy

            return EmbodiedSACFSDPPolicy
        except Exception as exc:  # pragma: no cover - optional RLinf backend
            raise RuntimeError("SAC training requested, but RLinf SAC FSDP worker is unavailable.") from exc
    return components.EmbodiedFSDPActor


def launch_worker(worker_cls: Any, cfg: Any, cluster: Any, placement: Any, group_name: str | None = None) -> Any:
    group = worker_cls.create_group(cfg)
    kwargs: dict[str, Any] = {"placement_strategy": placement}
    if group_name:
        kwargs["name"] = group_name
    return group.launch(cluster, **kwargs)


def run_rlinf(args: argparse.Namespace) -> int:
    registered = registry.register_all()
    if not registered:
        raise RuntimeError("RLinf model registry is unavailable; cannot launch RoboClaw RLinf training.")

    components = load_rlinf_components()
    cfg = build_cfg(args, components)

    cluster = components.Cluster(cluster_cfg=cfg.cluster)
    component_placement = components.HybridComponentPlacement(cfg, cluster)

    actor_group = launch_worker(
        select_actor_worker(cfg, components),
        cfg,
        cluster,
        component_placement.get_strategy("actor"),
        _cfg_get(cfg, "actor.group_name", None),
    )
    rollout_group = launch_worker(
        components.MultiStepRolloutWorker,
        cfg,
        cluster,
        component_placement.get_strategy("rollout"),
        _cfg_get(cfg, "rollout.group_name", None),
    )
    env_group = launch_worker(
        components.EnvWorker,
        cfg,
        cluster,
        component_placement.get_strategy("env"),
        _cfg_get(cfg, "env.group_name", None),
    )

    runner = components.EmbodiedRunner(cfg=cfg, actor=actor_group, rollout=rollout_group, env=env_group)
    runner.init_workers()
    runner.run()
    return 0


def _write_failure_contract(args: argparse.Namespace, exc: BaseException) -> None:
    artifact_path = Path(args.artifact_path)
    artifact_path.mkdir(parents=True, exist_ok=True)
    (artifact_path / "launcher_error.json").write_text(
        json.dumps(
            {
                "configName": args.config_name,
                "datasetPath": args.dataset_path,
                "checkpointPath": args.checkpoint_path,
                "runnerImplemented": True,
                "error": str(exc),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        return run_rlinf(args)
    except Exception as exc:
        _write_failure_contract(args, exc)
        raise


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
