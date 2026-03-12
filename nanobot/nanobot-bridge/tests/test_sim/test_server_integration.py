"""Integration tests for sim-bridge MCP server."""
import json
import pytest
from sim_bridge.server import create_server
from tests.conftest import SO100_URDF, requires_urdf


def _parse(result) -> dict:
    """Extract JSON dict from FastMCP call_tool result tuple."""
    content_list, _is_error = result
    return json.loads(content_list[0].text)


class TestSimMCPTools:
    @pytest.fixture
    def server(self, tmp_workspace):
        return create_server(workspace=tmp_workspace, headless=True)

    async def test_probe_env(self, server):
        data = _parse(await server.call_tool("probe_env", {}))
        assert "python_version" in data
        assert data["sim_backend"] == "pybullet"

    @requires_urdf
    async def test_sim_load_robot(self, server):
        data = _parse(await server.call_tool("sim_load_robot", {"urdf_path": SO100_URDF}))
        assert data["status"] == "loaded"
        assert data["num_joints"] > 0
        assert len(data["joint_names"]) > 0

    @requires_urdf
    async def test_sim_get_joints(self, server):
        await server.call_tool("sim_load_robot", {"urdf_path": SO100_URDF})
        data = _parse(await server.call_tool("sim_get_joints", {"robot_id": 1}))
        # robot_id=1 because plane is 0
        assert isinstance(data, dict)
        assert len(data) > 0

    @requires_urdf
    async def test_sim_set_joints(self, server):
        load_result = _parse(await server.call_tool("sim_load_robot", {"urdf_path": SO100_URDF}))
        robot_id = load_result["robot_id"]
        first_joint = load_result["joint_names"][0]

        data = _parse(await server.call_tool("sim_set_joints", {
            "robot_id": robot_id,
            "positions": {first_joint: 0.3},
        }))
        assert data["status"] == "ok"
        assert "joints" in data

    async def test_sim_step(self, server):
        data = _parse(await server.call_tool("sim_step", {"steps": 100}))
        assert data["status"] == "ok"
        assert data["steps"] == 100

    @requires_urdf
    async def test_sim_reset(self, server):
        await server.call_tool("sim_load_robot", {"urdf_path": SO100_URDF})
        data = _parse(await server.call_tool("sim_reset", {}))
        assert data["status"] == "reset"

        # After reset, probe should show no loaded robots
        probe = _parse(await server.call_tool("probe_env", {}))
        assert probe["robots_loaded"] == []

    @requires_urdf
    async def test_driver_with_physics_injection(self, server, tmp_workspace):
        """Test that a driver loaded in sim-bridge gets _physics injected."""
        driver_code = '''
class Driver:
    name = "sim_test"
    description = "Test sim driver"
    methods = {
        "connect": {"type": "instant", "description": "Load into sim", "params": {}},
        "get_joints": {"type": "instant", "description": "Read sim joints", "params": {}},
    }

    def __init__(self):
        self._physics = None  # Injected by sim-bridge
        self._robot_id = None

    async def connect(self):
        if self._physics is None:
            return {"error": "No physics engine"}
        self._robot_id = self._physics.load_urdf("''' + SO100_URDF + '''")
        info = self._physics.get_robot_info(self._robot_id)
        return {"status": "connected", "joints": info["joint_names"]}

    async def get_joints(self):
        if self._robot_id is None:
            return {"error": "Not connected"}
        return self._physics.get_joint_positions(self._robot_id)
'''
        (tmp_workspace / "drivers" / "sim_test.py").write_text(driver_code)

        # Load driver — sim-bridge should inject _physics
        load_data = _parse(await server.call_tool("load_driver", {"name": "sim_test"}))
        assert load_data["status"] == "loaded"

        # Connect — should use injected physics engine
        connect_data = _parse(await server.call_tool("call", {
            "driver": "sim_test", "method": "connect",
        }))
        assert connect_data["status"] == "connected"
        assert len(connect_data["joints"]) > 0

        # Get joints
        joints_data = _parse(await server.call_tool("call", {
            "driver": "sim_test", "method": "get_joints",
        }))
        assert isinstance(joints_data, dict)
        assert len(joints_data) > 0
