"""Control-surface profile exports."""

from roboclaw.embodied.execution.integration.control_surfaces.library import (
    ARM_HAND_CONTROL_SURFACE_PROFILE,
    DEFAULT_CONTROL_SURFACE_PROFILES,
    DRONE_CONTROL_SURFACE_PROFILE,
    HUMANOID_WHOLE_BODY_CONTROL_SURFACE_PROFILE,
    MOBILE_BASE_FLEET_CONTROL_SURFACE_PROFILE,
    SIMULATOR_CONTROL_SURFACE_PROFILE,
)
from roboclaw.embodied.execution.integration.control_surfaces.model import (
    EmbodimentDomain,
    ControlSurfaceKind,
    ControlSurfaceSpec,
    ControlSurfaceProfile,
    ObservationSurfaceSpec,
)
from roboclaw.embodied.execution.integration.control_surfaces.registry import ControlSurfaceProfileRegistry

__all__ = [
    "ARM_HAND_CONTROL_SURFACE_PROFILE",
    "EmbodimentDomain",
    "ControlSurfaceKind",
    "ControlSurfaceProfileRegistry",
    "ControlSurfaceSpec",
    "DEFAULT_CONTROL_SURFACE_PROFILES",
    "DRONE_CONTROL_SURFACE_PROFILE",
    "ControlSurfaceProfile",
    "HUMANOID_WHOLE_BODY_CONTROL_SURFACE_PROFILE",
    "MOBILE_BASE_FLEET_CONTROL_SURFACE_PROFILE",
    "ObservationSurfaceSpec",
    "SIMULATOR_CONTROL_SURFACE_PROFILE",
]
