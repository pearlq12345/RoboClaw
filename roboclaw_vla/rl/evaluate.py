"""Evaluation entrypoint for RoboClaw VLA artifacts."""

from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path
from typing import Any

from roboclaw_vla.rl.adapters import RoboClawEnvAdapter


def _load_callable(spec: str) -> Any:
    if ":" not in spec:
        raise ValueError(f"Callable spec must be module:function, got {spec!r}.")
    module_name, attr = spec.split(":", 1)
    module = importlib.import_module(module_name)
    return getattr(module, attr)


def _load_policy(checkpoint_path: str, policy_loader: str) -> Any:
    loader = _load_callable(policy_loader)
    return loader(checkpoint_path=checkpoint_path)


def _make_env(env_factory: str, suite: str) -> Any:
    factory = _load_callable(env_factory)
    return factory(suite=suite, is_eval=True)


def _predict(policy: Any, obs: Any) -> Any:
    for name in ("predict", "act", "select_action", "get_action"):
        method = getattr(policy, name, None)
        if callable(method):
            return method(obs)
    if callable(policy):
        return policy(obs)
    raise TypeError("Loaded policy must expose predict/act/select_action/get_action or be callable.")


def run_eval(
    *,
    checkpoint_path: str,
    artifact_path: str,
    suite: str,
    episodes: int,
    max_steps: int,
    env_factory: str,
    policy_loader: str,
) -> dict[str, Any]:
    policy = _load_policy(checkpoint_path, policy_loader)
    env = RoboClawEnvAdapter(_make_env(env_factory, suite))

    successes = 0
    episode_steps: list[int] = []
    episode_rewards: list[float] = []
    for _episode in range(episodes):
        reset_result = env.reset()
        obs = reset_result[0] if isinstance(reset_result, tuple) else reset_result
        total_reward = 0.0
        success = False
        steps = 0
        for step in range(max_steps):
            action = _predict(policy, obs)
            transition = env.step(action)
            obs = transition["obs"]
            info = transition["info"]
            total_reward += float(transition["reward"])
            success = bool(info.get("success", success))
            steps = step + 1
            if transition["done"]:
                break
        successes += int(success)
        episode_steps.append(steps)
        episode_rewards.append(total_reward)

    success_rate = successes / episodes if episodes else 0.0
    result = {
        "checkpointPath": checkpoint_path,
        "suite": suite,
        "episodes": episodes,
        "maxSteps": max_steps,
        "successes": successes,
        "success_rate": success_rate,
        "episode_steps": episode_steps,
        "episode_rewards": episode_rewards,
        "implemented": True,
    }
    output_dir = Path(artifact_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "eval_info.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint_path", required=True)
    parser.add_argument("--artifact_path", required=True)
    parser.add_argument("--suite", default="libero_10")
    parser.add_argument("--episodes", type=int, default=10)
    parser.add_argument("--max_steps", type=int, default=600)
    parser.add_argument("--env_factory", default="roboclaw_vla_envs:create_libero_env")
    parser.add_argument("--policy_loader", default="roboclaw_vla_policy:load_policy")
    args = parser.parse_args()
    run_eval(
        checkpoint_path=args.checkpoint_path,
        artifact_path=args.artifact_path,
        suite=args.suite,
        episodes=args.episodes,
        max_steps=args.max_steps,
        env_factory=args.env_factory,
        policy_loader=args.policy_loader,
    )


if __name__ == "__main__":
    main()
