import os
import pytest


SO100_URDF = os.environ.get("SO100_URDF_PATH", "")

requires_urdf = pytest.mark.skipif(
    not SO100_URDF, reason="SO100_URDF_PATH env var not set"
)


@pytest.fixture
def tmp_workspace(tmp_path):
    """Create a temporary workspace with drivers/ directory."""
    drivers_dir = tmp_path / "drivers"
    drivers_dir.mkdir()
    return tmp_path


@pytest.fixture
def sample_driver_code():
    """Return valid driver Python source code for testing."""
    return '''
class Driver:
    name = "test_arm"
    description = "Test robot arm"
    methods = {
        "connect": {"type": "instant", "description": "Connect", "params": {"port": "str"}},
        "get_joints": {"type": "instant", "description": "Read joints", "params": {}},
        "disconnect": {"type": "instant", "description": "Disconnect", "params": {}},
    }

    def __init__(self):
        self._connected = False
        self._joints = {"j1": 0.0, "j2": 0.0, "j3": 0.0}

    async def connect(self, port="/dev/ttyACM0"):
        self._connected = True
        return {"status": "connected", "port": port}

    async def get_joints(self):
        return dict(self._joints)

    async def disconnect(self):
        self._connected = False
        return {"status": "disconnected"}
'''


@pytest.fixture
def sample_streaming_driver_code():
    """Return driver code with a streaming method."""
    return '''
import asyncio

class Driver:
    name = "test_stream"
    description = "Test streaming driver"
    methods = {
        "connect": {"type": "instant", "description": "Connect", "params": {}},
        "run_policy": {
            "type": "streaming",
            "description": "Run policy inference",
            "params": {"episodes": "int"},
        },
    }

    def __init__(self):
        self._connected = False

    async def connect(self):
        self._connected = True
        return {"status": "connected"}

    async def run_policy(self, episodes=1, *, _report_status=None):
        for ep in range(episodes):
            await asyncio.sleep(0.01)  # Simulate work
            if _report_status:
                _report_status({"episode": ep + 1, "total": episodes})
        return {"status": "completed", "episodes": episodes}
'''


