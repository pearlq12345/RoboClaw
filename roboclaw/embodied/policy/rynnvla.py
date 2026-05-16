"""RynnVLA-001 policy training config."""

from __future__ import annotations

from dataclasses import dataclass, field

from roboclaw.embodied.policy.base import BasePolicyConfig
from roboclaw.embodied.policy.registry import policy_registry


@policy_registry.register
@dataclass(frozen=True)
class RynnVLAPolicyConfig(BasePolicyConfig):
    policy_type: str = field(init=False, default="rynnvla")
    config_file: str = ""
    exp_dir: str = ""
    actionvae_path: str = ""
    action_chunk_size: int = 20
    action_dim: int = 6
    num_cameras: int = 2
    use_depth: bool = False
    img_size: int = 384
    use_proprio: bool = True
    proprio_dim: int = 6
    use_ft_sensor: bool = False
    use_imu: bool = False
    condition_frame_num: int = 1
    precision: str = "bfloat16"

    def extra_train_args(self) -> list[str]:
        """Return the launcher args accepted by RynnVLA-001 train.py."""

        args = []
        if self.config_file:
            args.append(f"--config_file={self.config_file}")
        if self.exp_dir:
            args.append(f"--exp_dir={self.exp_dir}")
        return args

    def config_overrides(self) -> dict[str, object]:
        """Return fields to inject into the RynnVLA-001 yaml config at runtime."""

        overrides: dict[str, object] = {
            "action_chunk_size": self.action_chunk_size,
            "action_dim": self.action_dim,
            "condition_frame_num": self.condition_frame_num,
            "precision": self.precision,
            "num_cameras": self.num_cameras,
            "use_depth": self.use_depth,
            "img_size": self.img_size,
            "use_proprio": self.use_proprio,
            "proprio_dim": self.proprio_dim,
            "use_ft_sensor": self.use_ft_sensor,
            "use_imu": self.use_imu,
        }
        if self.actionvae_path:
            overrides["actionvae_path"] = self.actionvae_path
        return overrides
