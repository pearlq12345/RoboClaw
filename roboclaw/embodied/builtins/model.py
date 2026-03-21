"""Built-in embodiment declarations."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

from roboclaw.embodied.definition.components.robots.model import RobotManifest

if TYPE_CHECKING:
    from roboclaw.embodied.execution.integration.adapters.ros2.profiles import Ros2EmbodimentProfile


@dataclass(frozen=True)
class BuiltinEmbodiment:
    """One framework-owned built-in embodiment declaration."""

    id: str
    robot: RobotManifest
    ros2_profile: "Ros2EmbodimentProfile | None" = None
    calibration_driver_id: str | None = None
    probe_provider_id: str | None = None
    onboarding_aliases: tuple[str, ...] = field(default_factory=tuple)
    control_surface_runtime_factory: Callable[..., Any] | None = None


__all__ = ["BuiltinEmbodiment"]
