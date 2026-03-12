"""Integration tests — call MCP tools through the robot-bridge server."""
import asyncio
import json
import pytest
from robot_bridge.server import create_server


def _parse(result) -> dict:
    """Extract JSON dict from FastMCP call_tool result tuple."""
    content_list, _is_error = result
    return json.loads(content_list[0].text)


class TestMCPTools:
    @pytest.fixture
    def server(self, tmp_workspace):
        return create_server(workspace=tmp_workspace)

    async def test_probe_env(self, server):
        result = await server.call_tool("probe_env", {})
        data = _parse(result)
        assert "python_version" in data
        assert "packages" in data
        assert "loaded_drivers" in data
        assert isinstance(data["available_drivers"], list)

    async def test_exec_in_env(self, server):
        result = await server.call_tool("exec_in_env", {"code": "print(1+1)"})
        data = _parse(result)
        assert data["success"] is True
        assert "2" in data["stdout"]

    async def test_exec_in_env_error(self, server):
        result = await server.call_tool("exec_in_env", {"code": "raise RuntimeError('boom')"})
        data = _parse(result)
        assert data["success"] is False
        assert "RuntimeError" in data["stderr"]

    async def test_load_driver(self, server, tmp_workspace, sample_driver_code):
        (tmp_workspace / "drivers" / "test_arm.py").write_text(sample_driver_code)
        result = await server.call_tool("load_driver", {"name": "test_arm"})
        data = _parse(result)
        assert data["status"] == "loaded"
        assert "get_joints" in data["methods"]
        assert "connect" in data["methods"]

    async def test_load_driver_not_found(self, server):
        result = await server.call_tool("load_driver", {"name": "nonexistent"})
        data = _parse(result)
        assert "error" in data
        assert "FileNotFoundError" in data["error"]

    async def test_call_connect_and_get_joints(self, server, tmp_workspace, sample_driver_code):
        (tmp_workspace / "drivers" / "test_arm.py").write_text(sample_driver_code)
        await server.call_tool("load_driver", {"name": "test_arm"})

        # Connect
        result = await server.call_tool("call", {
            "driver": "test_arm",
            "method": "connect",
            "params": {"port": "/dev/ttyUSB0"},
        })
        data = _parse(result)
        assert data["status"] == "connected"
        assert data["port"] == "/dev/ttyUSB0"

        # Get joints
        result = await server.call_tool("call", {
            "driver": "test_arm",
            "method": "get_joints",
        })
        data = _parse(result)
        assert "j1" in data
        assert "j2" in data
        assert "j3" in data

    async def test_call_unloaded_driver_errors(self, server):
        result = await server.call_tool("call", {
            "driver": "nonexistent",
            "method": "connect",
        })
        data = _parse(result)
        assert "error" in data
        assert "not loaded" in data["error"]

    async def test_call_unknown_method_errors(self, server, tmp_workspace, sample_driver_code):
        (tmp_workspace / "drivers" / "test_arm.py").write_text(sample_driver_code)
        await server.call_tool("load_driver", {"name": "test_arm"})

        result = await server.call_tool("call", {
            "driver": "test_arm",
            "method": "fly_to_moon",
        })
        data = _parse(result)
        assert "error" in data
        assert "Unknown method" in data["error"]

    async def test_streaming_task_lifecycle(self, server, tmp_workspace, sample_streaming_driver_code):
        (tmp_workspace / "drivers" / "test_stream.py").write_text(sample_streaming_driver_code)
        await server.call_tool("load_driver", {"name": "test_stream"})
        await server.call_tool("call", {"driver": "test_stream", "method": "connect"})

        # Start streaming task
        result = await server.call_tool("call", {
            "driver": "test_stream",
            "method": "run_policy",
            "params": {"episodes": 3},
        })
        data = _parse(result)
        assert "task_id" in data
        assert data["status"] == "started"
        task_id = data["task_id"]

        # Wait for completion
        await asyncio.sleep(0.15)

        # Check status
        result = await server.call_tool("task_status", {"task_id": task_id})
        status = _parse(result)
        assert status["state"] == "completed"
        assert status["result"]["episodes"] == 3

    async def test_stop_streaming_task(self, server, tmp_workspace, sample_streaming_driver_code):
        # Make a slow driver
        slow_code = sample_streaming_driver_code.replace("0.01", "1.0")
        (tmp_workspace / "drivers" / "test_stream.py").write_text(slow_code)
        await server.call_tool("load_driver", {"name": "test_stream"})
        await server.call_tool("call", {"driver": "test_stream", "method": "connect"})

        # Start
        result = await server.call_tool("call", {
            "driver": "test_stream",
            "method": "run_policy",
            "params": {"episodes": 100},
        })
        task_id = _parse(result)["task_id"]

        # Give it a moment to start
        await asyncio.sleep(0.05)

        # Stop
        result = await server.call_tool("stop_task", {"task_id": task_id})
        status = _parse(result)
        assert status["state"] == "cancelled"

    async def test_reload_driver_picks_up_changes(self, server, tmp_workspace, sample_driver_code):
        path = tmp_workspace / "drivers" / "test_arm.py"
        path.write_text(sample_driver_code)
        await server.call_tool("load_driver", {"name": "test_arm"})

        # Modify driver: change description
        path.write_text(sample_driver_code.replace("Test robot arm", "Modified arm"))
        result = await server.call_tool("load_driver", {"name": "test_arm", "reload": True})
        data = _parse(result)
        assert data["description"] == "Modified arm"
