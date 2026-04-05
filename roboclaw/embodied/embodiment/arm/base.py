"""Arm spec hierarchy — base classes for all robot arm types."""

from __future__ import annotations

from dataclasses import dataclass, field

from roboclaw.embodied.embodiment.base import EmbodimentSpec


@dataclass(frozen=True)
class ArmSpec(EmbodimentSpec):
    """Base class for all robot arm specifications."""

    roles: tuple[str, ...] = ("follower", "leader")
    motor_names: tuple[str, ...] = ()
    supports_bimanual: bool = False
    bimanual_follower_type: str = ""
    bimanual_leader_type: str = ""


@dataclass(frozen=True)
class ServoArmSpec(ArmSpec):
    """Servo motor arm — communicates via MotorsBus (Feetech/Dynamixel).

    SO101 and Koch are both instances of this class.
    """

    motor_bus_module: str = ""
    motor_bus_class: str = ""
    follower_motor_models: dict[str, str] = field(default_factory=dict)
    leader_motor_models: dict[str, str] = field(default_factory=dict)
    full_turn_motors: tuple[str, ...] = ()
    probe_protocol: str = "feetech"
    probe_motor_ids: tuple[int, ...] = (1, 2, 3, 4, 5, 6)
    probe_baudrate: int = 1_000_000

    def motor_models(self, role: str) -> dict[str, str]:
        """Return motor models for 'follower' or 'leader'."""
        if role == "leader":
            return dict(self.leader_motor_models)
        return dict(self.follower_motor_models)

    @property
    def follower_type(self) -> str:
        return f"{self.name}_follower"

    @property
    def leader_type(self) -> str:
        return f"{self.name}_leader"

    @property
    def arm_types(self) -> tuple[str, str]:
        return (self.follower_type, self.leader_type)


@dataclass(frozen=True)
class MotorArmSpec(ArmSpec):
    """Motor-driven arm (e.g. brushless motors with encoders) — reserved."""

    pass
