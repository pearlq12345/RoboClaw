"""SO-100 simulation driver using PyBullet via sim-bridge built-in physics.

This driver calls the sim-bridge's physics engine directly (not subprocess).
It is loaded by the sim-bridge server, which injects `_physics` at load time.

NOTE: Update URDF_PATH to your local SO-ARM100 URDF location.
"""

import asyncio


class Driver:
    name = "so100_sim"
    description = "SO-100 6-DOF arm in PyBullet simulation"

    # TODO: Make this configurable or use asset registry
    URDF_PATH = "/path/to/SO-ARM100/Simulation/SO100/so100.urdf"

    methods = {
        "connect": {
            "type": "instant",
            "description": "Load SO-100 URDF into PyBullet sim",
            "params": {"urdf_path": "str, optional URDF override"},
        },
        "get_joints": {
            "type": "instant",
            "description": "Read simulated joint positions",
            "params": {},
        },
        "send_action": {
            "type": "instant",
            "description": "Set target joint positions and step sim",
            "params": {"positions": "dict, joint_name -> float (radians)"},
        },
        "reset": {
            "type": "instant",
            "description": "Reset robot to home position",
            "params": {},
        },
        "step": {
            "type": "instant",
            "description": "Step simulation N times",
            "params": {"steps": "int, number of physics steps (default 240 = 1s at 240Hz)"},
        },
        "run_trajectory": {
            "type": "streaming",
            "description": "Execute a joint trajectory (list of waypoints)",
            "params": {"waypoints": "list[dict], each dict maps joint_name -> float", "hz": "int, control rate"},
        },
    }

    def __init__(self):
        self._physics = None  # Injected by sim-bridge if available
        self._robot_id = None

    async def connect(self, urdf_path=None):
        if self._physics is None:
            return {"error": "No physics engine. Load this driver in sim-bridge."}

        path = urdf_path or self.URDF_PATH
        self._robot_id = self._physics.load_urdf(path)
        info = self._physics.get_robot_info(self._robot_id)
        return {"status": "connected", "sim": True, **info}

    async def get_joints(self):
        if self._robot_id is None:
            return {"error": "Not connected"}
        return self._physics.get_joint_positions(self._robot_id)

    async def send_action(self, positions):
        if self._robot_id is None:
            return {"error": "Not connected"}
        self._physics.set_joint_positions(self._robot_id, positions)
        self._physics.step(steps=10)
        return {"status": "ok", "joints": self._physics.get_joint_positions(self._robot_id)}

    async def reset(self):
        if self._robot_id is None:
            return {"error": "Not connected"}
        joints = self._physics.get_joint_positions(self._robot_id)
        zeros = {name: 0.0 for name in joints}
        self._physics.set_joint_positions(self._robot_id, zeros)
        self._physics.step(steps=100)
        return {"status": "reset", "joints": self._physics.get_joint_positions(self._robot_id)}

    async def step(self, steps=240):
        if self._physics is None:
            return {"error": "No physics engine"}
        self._physics.step(steps=steps)
        return {"status": "ok", "steps": steps}

    async def run_trajectory(self, waypoints, hz=50, *, _report_status=None):
        if self._robot_id is None:
            return {"error": "Not connected"}

        dt = 1.0 / hz
        steps_per_tick = max(1, int(240 / hz))

        for i, wp in enumerate(waypoints):
            self._physics.set_joint_positions(self._robot_id, wp)
            self._physics.step(steps=steps_per_tick)
            if _report_status:
                _report_status({"waypoint": i + 1, "total": len(waypoints)})
            await asyncio.sleep(dt)

        return {
            "status": "completed",
            "waypoints_executed": len(waypoints),
            "final_joints": self._physics.get_joint_positions(self._robot_id),
        }
