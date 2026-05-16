"""RLinf registry injection point for RoboClaw VLA models."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class RoboClawPi0Policy:
    """Thin adapter descriptor for RoboClaw Pi0-family RLinf registration.

    The real model object is loaded by the RLinf worker from the configured
    checkpoint path. Keeping this adapter lightweight makes import-time
    preflight safe while still registering a concrete model name.
    """

    model_path: str
    processor_path: str | None = None
    model_type: str = "pi0"
    num_action_chunks: int = 5
    action_dim: int = 7
    add_value_head: bool = True
    precision: str | None = "bfloat16"
    trust_remote_code: bool = True

    @classmethod
    def from_config(cls, cfg: Any) -> "RoboClawPi0Policy":
        model_cfg = getattr(getattr(cfg, "actor", cfg), "model", cfg)
        return cls(
            model_path=str(getattr(model_cfg, "model_path", "")),
            processor_path=getattr(model_cfg, "processor_path", None),
            model_type=str(getattr(model_cfg, "model_type", "pi0")),
            num_action_chunks=int(getattr(model_cfg, "num_action_chunks", 5)),
            action_dim=int(getattr(model_cfg, "action_dim", 7)),
            add_value_head=bool(getattr(model_cfg, "add_value_head", True)),
            precision=getattr(model_cfg, "precision", "bfloat16"),
            trust_remote_code=bool(getattr(model_cfg, "trust_remote_code", True)),
        )

    def get_model(self) -> Any:
        """Load a RoboClaw-compatible Pi0 model object when available.

        This is intentionally dependency-light: if the remote image provides a
        project-specific loader at ``roboclaw_vla_policy.load_pi0_policy`` it is
        used; otherwise the adapter returns itself so RLinf can still receive a
        structured model descriptor during early integration tests.
        """

        if not self.model_path:
            raise ValueError("actor.model.model_path is required for roboclaw_pi0 registration.")
        if self.model_path.startswith("path/to/"):
            raise ValueError(f"Replace placeholder model_path before launch: {self.model_path}")

        try:
            from roboclaw_vla_policy import load_pi0_policy  # type: ignore
        except Exception:
            return self
        return load_pi0_policy(
            model_path=Path(self.model_path),
            processor_path=Path(self.processor_path or self.model_path),
            model_type=self.model_type,
            num_action_chunks=self.num_action_chunks,
            action_dim=self.action_dim,
            add_value_head=self.add_value_head,
            precision=self.precision,
            trust_remote_code=self.trust_remote_code,
        )


def _get_roboclaw_pi0_model(cfg: Any, *_args: Any, **_kwargs: Any) -> Any:
    return RoboClawPi0Policy.from_config(cfg).get_model()


def register() -> bool:
    """Register RoboClaw model adapters with RLinf when the API is present."""

    try:
        from rlinf.models import register_model  # type: ignore
    except Exception:
        return False

    register_model("roboclaw_pi0", _get_roboclaw_pi0_model)
    return True


def register_all() -> bool:
    return register()
