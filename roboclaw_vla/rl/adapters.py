"""Adapter utilities for RoboClaw RLinf workflows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class EnvLike(Protocol):
    def reset(self, *args: Any, **kwargs: Any) -> Any: ...

    def step(self, action: Any) -> Any: ...


def logprobs_from_logits(logits: Any, labels: Any) -> Any:
    """Gather token log-probabilities from logits for the selected labels."""

    try:
        import torch
    except Exception as exc:  # pragma: no cover - torch is training-image only
        raise RuntimeError("logprobs_from_logits requires torch.") from exc

    tensor_logits = torch.as_tensor(logits)
    tensor_labels = torch.as_tensor(labels, device=tensor_logits.device).long()
    log_probs = tensor_logits.log_softmax(dim=-1)
    return log_probs.gather(dim=-1, index=tensor_labels.unsqueeze(-1)).squeeze(-1)


def compute_grpo_outcome_advantage(
    rewards: Any,
    *,
    group_size: int,
    eps: float = 1e-8,
    normalize: bool = True,
) -> Any:
    """Compute outcome-level GRPO advantages within fixed-size groups."""

    if group_size <= 0:
        raise ValueError("group_size must be positive.")

    try:
        import torch
    except Exception as exc:  # pragma: no cover - torch is training-image only
        raise RuntimeError("compute_grpo_outcome_advantage requires torch.") from exc

    reward_tensor = torch.as_tensor(rewards, dtype=torch.float32)
    original_shape = reward_tensor.shape
    flat = reward_tensor.reshape(-1)
    if flat.numel() % group_size != 0:
        raise ValueError(f"reward count {flat.numel()} is not divisible by group_size {group_size}.")

    grouped = flat.reshape(-1, group_size)
    centered = grouped - grouped.mean(dim=1, keepdim=True)
    if normalize:
        denom = grouped.std(dim=1, unbiased=False, keepdim=True).clamp_min(eps)
        centered = centered / denom
    return centered.reshape(original_shape)


@dataclass
class RoboClawEnvAdapter:
    """Normalize simulator env APIs for RLinf EnvWorker-compatible use."""

    env: EnvLike
    last_obs: Any = None

    def reset(self, *args: Any, **kwargs: Any) -> Any:
        result = self.env.reset(*args, **kwargs)
        self.last_obs = result[0] if isinstance(result, tuple) else result
        return result

    def step(self, action: Any) -> dict[str, Any]:
        result = self.env.step(action)
        if not isinstance(result, tuple):
            raise TypeError("env.step(action) must return a tuple.")

        if len(result) == 5:
            obs, reward, terminated, truncated, info = result
            done = bool(terminated or truncated)
        elif len(result) == 4:
            obs, reward, done, info = result
            terminated = bool(done)
            truncated = False
        else:
            raise ValueError("env.step(action) must return 4 or 5 values.")

        self.last_obs = obs
        return {
            "obs": obs,
            "reward": reward,
            "done": bool(done),
            "terminated": bool(terminated),
            "truncated": bool(truncated),
            "info": info or {},
        }

    def get_obs(self) -> Any:
        return self.last_obs
