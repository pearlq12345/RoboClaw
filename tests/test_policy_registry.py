from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from roboclaw.embodied.policy import BasePolicyConfig, PolicyRegistry, policy_registry


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
    assert registry.supported_types() == {"example"}


def test_policy_registry_returns_registered_builtin_policy() -> None:
    config = policy_registry.get("act")

    assert config.policy_type == "act"
    assert config.extra_train_args() == []
    assert "groot" in policy_registry.supported_types()


def test_rynnvla_policy_registered() -> None:
    config = policy_registry.get("rynnvla")

    assert config.policy_type == "rynnvla"
    args = config.extra_train_args()
    assert "--action_chunk_size=20" in args
    assert "--action_dim=6" in args
    assert "--num_cameras=2" in args
    assert "--img_size=384" in args
    assert "--condition_frame_num=1" in args
    assert "--precision=bfloat16" in args
    assert "--use_depth" not in args
    assert not any(arg.startswith("--model_path=") for arg in args)
    assert not any(arg.startswith("--actionvae_path=") for arg in args)


def test_rynnvla_policy_passes_optional_paths() -> None:
    config_cls = type(policy_registry.get("rynnvla"))
    config = config_cls(
        model_path="/models/rynnvla",
        actionvae_path="/models/actionvae.pth",
        num_cameras=3,
        use_depth=True,
        img_size=512,
    )

    args = config.extra_train_args()

    assert "--model_path=/models/rynnvla" in args
    assert "--actionvae_path=/models/actionvae.pth" in args
    assert "--num_cameras=3" in args
    assert "--img_size=512" in args
    assert "--use_depth" in args


def test_policy_registry_raises_for_unknown_policy() -> None:
    with pytest.raises(ValueError, match="Unsupported policy_type 'unknown'"):
        policy_registry.get("unknown")
