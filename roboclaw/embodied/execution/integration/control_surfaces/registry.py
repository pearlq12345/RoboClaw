"""Control-surface profile registry."""

from __future__ import annotations

from roboclaw.embodied.definition.foundation.schema import CapabilityFamily, RobotType
from roboclaw.embodied.execution.integration.control_surfaces.model import EmbodimentDomain, ControlSurfaceProfile


class ControlSurfaceProfileRegistry:
    """Register reusable control-surface profiles."""

    def __init__(self) -> None:
        self._entries: dict[str, ControlSurfaceProfile] = {}

    def register(self, profile: ControlSurfaceProfile) -> None:
        if profile.id in self._entries:
            raise ValueError(f"Control-surface profile '{profile.id}' is already registered.")
        self._entries[profile.id] = profile

    def get(self, control_surface_profile_id: str) -> ControlSurfaceProfile:
        try:
            return self._entries[control_surface_profile_id]
        except KeyError as exc:
            raise KeyError(
                f"Unknown control-surface profile '{control_surface_profile_id}'."
            ) from exc

    def list(self) -> tuple[ControlSurfaceProfile, ...]:
        return tuple(self._entries.values())

    def for_domain(self, domain: EmbodimentDomain) -> tuple[ControlSurfaceProfile, ...]:
        return tuple(entry for entry in self._entries.values() if entry.domain == domain)

    def for_robot_type(self, robot_type: RobotType) -> tuple[ControlSurfaceProfile, ...]:
        return tuple(
            entry for entry in self._entries.values() if entry.supports_robot_type(robot_type)
        )

    def for_capability(self, capability: CapabilityFamily) -> tuple[ControlSurfaceProfile, ...]:
        return tuple(
            entry for entry in self._entries.values() if entry.supports_capability(capability)
        )
