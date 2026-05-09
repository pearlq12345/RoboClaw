"""Unified workflow configuration models for embodied data/train/infer flows."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class WorkflowConfig(BaseModel):
    """Base config model shared by dashboard forms and service interfaces."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="ignore",
    )


class RecordWorkflowConfig(WorkflowConfig):
    task: str = ""
    num_episodes: int = 10
    fps: int = 30
    episode_time_s: int = 300
    reset_time_s: int = 10
    dataset_name: str = ""
    use_cameras: bool = True
    arms: str = ""

    def command_kwargs(self) -> dict[str, Any]:
        return {
            "task": self.task,
            "num_episodes": self.num_episodes,
            "fps": self.fps,
            "episode_time_s": self.episode_time_s,
            "reset_time_s": self.reset_time_s,
            "arms": self.arms,
            "use_cameras": self.use_cameras,
        }


class TrainWorkflowConfig(WorkflowConfig):
    dataset_name: str = ""
    policy_type: str = "act"
    steps: int = 100_000
    device: str = "cuda"

    def command_kwargs(self) -> dict[str, Any]:
        return {
            "dataset_name": self.dataset_name,
            "policy_type": self.policy_type,
            "steps": self.steps,
            "device": self.device,
        }


class InferWorkflowConfig(WorkflowConfig):
    checkpoint_path: str = ""
    source_dataset: str = ""
    dataset_name: str = ""
    task: str = "eval"
    num_episodes: int = 1
    episode_time_s: int = 60
    use_cameras: bool = True
    arms: str = ""

    def command_kwargs(self) -> dict[str, Any]:
        return {
            "checkpoint_path": self.checkpoint_path,
            "task": self.task,
            "num_episodes": self.num_episodes,
            "episode_time_s": self.episode_time_s,
            "arms": self.arms,
            "use_cameras": self.use_cameras,
        }
