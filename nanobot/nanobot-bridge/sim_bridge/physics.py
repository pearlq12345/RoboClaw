"""PyBullet physics engine wrapper."""

import os
import sys
from contextlib import contextmanager
from pathlib import Path

import pybullet as p
import pybullet_data

# Log file for PyBullet C-level output (would otherwise corrupt MCP stdio)
_LOG_DIR = Path.home() / ".nanobot" / "workspace" / "logs"
_LOG_FILE: Path | None = None


def _ensure_log_file() -> Path:
    """Lazily create log dir and return log file path."""
    global _LOG_FILE
    if _LOG_FILE is None:
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        _LOG_FILE = _LOG_DIR / "sim_bridge.log"
    return _LOG_FILE


@contextmanager
def _redirect_stdout_to_log():
    """Redirect C-level stdout to log file during PyBullet calls.

    PyBullet prints debug messages (thread info, X11 status, etc.) directly
    to fd 1 from C code.  MCP uses stdio for JSON-RPC, so we must keep fd 1
    clean.  Instead of discarding, we append to a log file that the agent
    can read via ``exec_in_env`` or ``read_file``.
    """
    log_path = _ensure_log_file()
    old_fd = os.dup(1)
    log_fd = os.open(str(log_path), os.O_WRONLY | os.O_CREAT | os.O_APPEND)
    os.dup2(log_fd, 1)
    os.close(log_fd)
    try:
        yield
    finally:
        os.dup2(old_fd, 1)
        os.close(old_fd)


class PhysicsEngine:
    """Thin wrapper around PyBullet for sim bridge."""

    def __init__(self, headless: bool = True, gravity: float = -9.81):
        # GUI mode requires a display; fall back to DIRECT if unavailable
        if not headless and not os.environ.get("DISPLAY"):
            headless = True
        mode = p.DIRECT if headless else p.GUI
        with _redirect_stdout_to_log():
            self.physics_client = p.connect(mode)
            p.setAdditionalSearchPath(pybullet_data.getDataPath())
            p.setGravity(0, 0, gravity, physicsClientId=self.physics_client)
        self.headless = headless
        self._robots: dict[int, dict] = {}

    def load_plane(self) -> int:
        with _redirect_stdout_to_log():
            return p.loadURDF("plane.urdf", physicsClientId=self.physics_client)

    def load_urdf(
        self,
        urdf_path: str,
        base_position: list[float] | None = None,
        base_orientation: list[float] | None = None,
        use_fixed_base: bool = True,
    ) -> int:
        pos = base_position or [0, 0, 0]
        orn = base_orientation or list(p.getQuaternionFromEuler([0, 0, 0]))
        urdf = Path(urdf_path).resolve()
        with _redirect_stdout_to_log():
            robot_id = p.loadURDF(
                str(urdf),
                basePosition=pos,
                baseOrientation=orn,
                useFixedBase=use_fixed_base,
                physicsClientId=self.physics_client,
            )
        num_joints = p.getNumJoints(robot_id, physicsClientId=self.physics_client)
        joint_map = {}
        for i in range(num_joints):
            info = p.getJointInfo(robot_id, i, physicsClientId=self.physics_client)
            name = info[1].decode("utf-8")
            joint_type = info[2]
            if joint_type != p.JOINT_FIXED:
                joint_map[name] = i
        self._robots[robot_id] = {"joint_map": joint_map, "urdf": str(urdf)}
        return robot_id

    def get_robot_info(self, robot_id: int) -> dict:
        info = self._robots.get(robot_id, {})
        return {
            "robot_id": robot_id,
            "num_joints": len(info.get("joint_map", {})),
            "joint_names": list(info.get("joint_map", {}).keys()),
            "urdf": info.get("urdf", ""),
        }

    def get_joint_positions(self, robot_id: int) -> dict[str, float]:
        joint_map = self._robots[robot_id]["joint_map"]
        states = p.getJointStates(
            robot_id, list(joint_map.values()), physicsClientId=self.physics_client
        )
        return {name: round(float(states[i][0]), 6) for i, name in enumerate(joint_map.keys())}

    def set_joint_positions(self, robot_id: int, positions: dict[str, float]) -> None:
        joint_map = self._robots[robot_id]["joint_map"]
        for name, pos in positions.items():
            if name in joint_map:
                p.setJointMotorControl2(
                    robot_id, joint_map[name],
                    p.POSITION_CONTROL, targetPosition=pos,
                    physicsClientId=self.physics_client,
                )

    def step(self, steps: int = 1) -> None:
        for _ in range(steps):
            p.stepSimulation(physicsClientId=self.physics_client)

    def reset(self) -> None:
        """Reset the simulation world."""
        p.resetSimulation(physicsClientId=self.physics_client)
        p.setGravity(0, 0, -9.81, physicsClientId=self.physics_client)
        p.setAdditionalSearchPath(pybullet_data.getDataPath())
        self._robots.clear()

    def close(self) -> None:
        if self.physics_client is not None:
            try:
                p.disconnect(self.physics_client)
            except Exception:
                pass
            self.physics_client = None
