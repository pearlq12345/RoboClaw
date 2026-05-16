"""RynnVLA-001 policy training config."""

from __future__ import annotations

from dataclasses import dataclass, field

from roboclaw.embodied.policy.base import BasePolicyConfig
from roboclaw.embodied.policy.registry import policy_registry


@policy_registry.register
@dataclass(frozen=True)
class RynnVLAPolicyConfig(BasePolicyConfig):
    policy_type: str = field(init=False, default="rynnvla")
    model_path: str = ""
    actionvae_path: str = ""
    action_chunk_size: int = 20
    action_dim: int = 6
    num_cameras: int = 2
    use_depth: bool = False
    img_size: int = 384
    condition_frame_num: int = 1
    precision: str = "bfloat16"

    def extra_train_args(self) -> list[str]:
        args = [
            f"--action_chunk_size={self.action_chunk_size}",
            f"--action_dim={self.action_dim}",
            f"--num_cameras={self.num_cameras}",
            f"--img_size={self.img_size}",
            f"--condition_frame_num={self.condition_frame_num}",
            f"--precision={self.precision}",
        ]
        if self.use_depth:
            args.append("--use_depth")
        if self.model_path:
            args.append(f"--model_path={self.model_path}")
        if self.actionvae_path:
            args.append(f"--actionvae_path={self.actionvae_path}")
        return args
