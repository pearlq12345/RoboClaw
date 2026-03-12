"""SO-100 real hardware driver via lerobot FeetechMotorsBus.

Requires: lerobot conda environment with scservo-sdk installed.
Hardware: SO-ARM100 6-DOF robot arm with Feetech STS3215 servos.
"""

from lerobot.robots.so100_follower import SO100Follower, SO100FollowerConfig


class Driver:
    name = "so100_real"
    description = "SO-100 6-DOF robot arm (real hardware via lerobot/feetech)"

    methods = {
        "connect": {
            "type": "instant",
            "description": "Connect to the robot arm via serial port",
            "params": {"port": "str, serial port (default /dev/ttyACM0)"},
        },
        "get_joints": {
            "type": "instant",
            "description": "Read current joint positions (degrees or normalized)",
            "params": {},
        },
        "send_action": {
            "type": "instant",
            "description": "Send target joint positions",
            "params": {"positions": "dict, joint_name.pos -> float"},
        },
        "get_state": {
            "type": "instant",
            "description": "Get full robot state (connected, calibrated, joints)",
            "params": {},
        },
        "disconnect": {
            "type": "instant",
            "description": "Disconnect from the robot",
            "params": {},
        },
    }

    JOINT_NAMES = [
        "shoulder_pan", "shoulder_lift", "elbow_flex",
        "wrist_flex", "wrist_roll", "gripper",
    ]

    def __init__(self):
        self._robot: SO100Follower | None = None

    async def connect(self, port="/dev/ttyACM0"):
        if self._robot and self._robot.is_connected:
            return {"status": "already_connected", "port": port}
        config = SO100FollowerConfig(port=port, use_degrees=True)
        self._robot = SO100Follower(config)
        self._robot.connect(calibrate=True)
        return {
            "status": "connected",
            "port": port,
            "calibrated": self._robot.is_calibrated,
            "joints": list(self._robot.bus.motors.keys()),
        }

    async def get_joints(self):
        if not self._robot or not self._robot.is_connected:
            return {"error": "Not connected"}
        obs = self._robot.get_observation()
        return {k: round(v, 2) for k, v in obs.items() if isinstance(v, (int, float))}

    async def send_action(self, positions):
        if not self._robot or not self._robot.is_connected:
            return {"error": "Not connected"}
        sent = self._robot.send_action(positions)
        return {"status": "ok", "sent": {k: round(v, 2) for k, v in sent.items()}}

    async def get_state(self):
        if not self._robot:
            return {"connected": False}
        return {
            "connected": self._robot.is_connected,
            "calibrated": self._robot.is_calibrated,
            "joints": await self.get_joints() if self._robot.is_connected else {},
        }

    async def disconnect(self):
        if self._robot and self._robot.is_connected:
            self._robot.disconnect()
        self._robot = None
        return {"status": "disconnected"}
