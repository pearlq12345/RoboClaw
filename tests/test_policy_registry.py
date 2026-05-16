from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from roboclaw.embodied.policy import BasePolicyConfig, PolicyRegistry, policy_registry
from roboclaw.embodied.policy.rynnvla import RynnVLAPolicyConfig


def test_policy_registry_registers_custom_config() -> None:
    registry = PolicyRegistry()

    @registry.register
    @dataclass(frozen=True)
    class ExamplePolicyConfig(BasePolicyConfig):
        policy_type: str = field(init=False, default="example")

        def extra_train_args(self) -> list[str]:
            return ["--policy.example=true"]

    config = registry.get("example")

    assert isinstance(config, ExamplePolicyConfig)
    assert config.extra_train_args() == ["--policy.example=true"]
    assert config.config_overrides() == {}
    assert registry.supported_types() == {"example"}


def test_policy_registry_returns_registered_builtin_policy() -> None:
    config = policy_registry.get("act")

    assert config.policy_type == "act"
    assert config.extra_train_args() == []
    assert "groot" in policy_registry.supported_types()


def test_rynnvla_policy_registered() -> None:
    config = policy_registry.get("rynnvla")

    assert config.policy_type == "rynnvla"
    assert config.extra_train_args() == []
    overrides = config.config_overrides()
    assert overrides["action_chunk_size"] == 20
    assert overrides["action_dim"] == 6
    assert overrides["num_cameras"] == 2
    assert overrides["img_size"] == 384
    assert overrides["condition_frame_num"] == 1
    assert overrides["precision"] == "bfloat16"
    assert overrides["use_depth"] is False
    assert overrides["use_proprio"] is True
    assert overrides["proprio_dim"] == 6
    assert overrides["use_ft_sensor"] is False
    assert overrides["use_imu"] is False
    assert "actionvae_path" not in overrides


def test_rynnvla_policy_passes_optional_paths() -> None:
    config = RynnVLAPolicyConfig(
        config_file="/tmp/cfg.yaml",
        exp_dir="/tmp/exp",
        actionvae_path="/models/actionvae.pth",
        num_cameras=3,
        use_depth=True,
        img_size=512,
        use_ft_sensor=True,
        use_imu=True,
    )

    args = config.extra_train_args()
    overrides = config.config_overrides()

    assert "--config_file=/tmp/cfg.yaml" in args
    assert "--exp_dir=/tmp/exp" in args
    assert len(args) == 2
    assert overrides["actionvae_path"] == "/models/actionvae.pth"
    assert overrides["num_cameras"] == 3
    assert overrides["img_size"] == 512
    assert overrides["use_depth"] is True
    assert overrides["use_ft_sensor"] is True
    assert overrides["use_imu"] is True


def test_policy_registry_raises_for_unknown_policy() -> None:
    with pytest.raises(ValueError, match="Unsupported policy_type 'unknown'"):
        policy_registry.get("unknown")
