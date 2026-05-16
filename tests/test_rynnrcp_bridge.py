from __future__ import annotations

import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from roboclaw.embodied.deploy.rynnrcp import K_GO_HOME_REQUEST, RynnRCPBridge, RynnRCPSettings
from roboclaw.http.routes import deploy_rcp
from roboclaw.http.routes.deploy_rcp import register_deploy_rcp_routes


class FakeLCM:
    def __init__(self) -> None:
        self.published: list[tuple[str, bytes]] = []

    def publish(self, channel: str, payload: bytes) -> None:
        self.published.append((channel, payload))


@pytest.fixture(autouse=True)
def reset_route_bridge():
    deploy_rcp.reset_bridge()
    yield
    deploy_rcp.reset_bridge()


def test_settings_from_env(monkeypatch) -> None:
    monkeypatch.setenv("ROBOCLAW_RYNNRCP_CHANNEL", "custom_motion")
    monkeypatch.setenv("ROBOCLAW_RYNNRCP_ROBOT_TYPE", "franka")
    monkeypatch.setenv("ROBOCLAW_RYNNRCP_ARM_DOF", "7")
    monkeypatch.setenv("ROBOCLAW_RYNNRCP_HAND_DOF", "6")
    monkeypatch.setenv("ROBOCLAW_RYNNRCP_HAND_CONTROL_MODE", "hybrid")
    monkeypatch.setenv("ROBOCLAW_RYNNRCP_ACTION_CHUNK_SIZE", "12")
    monkeypatch.setenv("ROBOCLAW_RYNNRCP_INFERENCE_RATE", "50")
    monkeypatch.setenv("ROBOCLAW_RYNNRCP_TIMEOUT_SECONDS", "5")
    monkeypatch.setenv("ROBOCLAW_RYNNRCP_INTERPOLATION", "linear")

    settings = RynnRCPSettings.from_env()

    assert settings.lcm_channel == "custom_motion"
    assert settings.robot_type == "franka"
    assert settings.arm_dof == 7
    assert settings.hand_dof == 6
    assert settings.hand_control_mode == "hybrid"
    assert settings.action_dim == 13
    assert settings.action_chunk_size == 12
    assert settings.inference_rate == 50
    assert settings.timeout_seconds == 5
    assert settings.interpolation == "linear"


def test_bridge_disabled_without_lcm(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "lcm", None)

    bridge = RynnRCPBridge(RynnRCPSettings())

    assert bridge.enabled is False


def test_dexhand_action_dim_property() -> None:
    settings = RynnRCPSettings(arm_dof=6, hand_dof=6)

    assert settings.action_dim == 12


def test_dexhand_action_chunk_is_segmented() -> None:
    bridge = RynnRCPBridge(
        RynnRCPSettings(action_chunk_size=2, arm_dof=2, hand_dof=3, hand_control_mode="force"),
        lcm_client=FakeLCM(),
        clock_ns=lambda: 123,
    )

    bridge.send_action_chunk([[1, 2, 3, 4, 5], [6, 7, 8, 9, 10]])

    assert bridge.last_command is not None
    assert bridge.last_command.actions == [[1.0, 2.0, 3.0, 4.0, 5.0], [6.0, 7.0, 8.0, 9.0, 10.0]]
    assert bridge.last_command.arm_actions == [[1.0, 2.0], [6.0, 7.0]]
    assert bridge.last_command.hand_actions == [[3.0, 4.0, 5.0], [8.0, 9.0, 10.0]]
    assert bridge.last_command.hand_control_mode == "force"


def test_send_action_chunk_shape_validation() -> None:
    bridge = RynnRCPBridge(RynnRCPSettings(action_chunk_size=2, arm_dof=3), lcm_client=FakeLCM())

    with pytest.raises(ValueError, match="actions\\[0\\]"):
        bridge.send_action_chunk([[1.0, 2.0], [3.0, 4.0, 5.0]])


def test_go_home_payload() -> None:
    bridge = RynnRCPBridge(RynnRCPSettings(lcm_channel="rcp_robotmotion"), lcm_client=FakeLCM(), clock_ns=lambda: 123)

    bridge.go_home()

    assert bridge.last_request is not None
    assert bridge.last_request.request_type == K_GO_HOME_REQUEST
    assert bridge.last_request.robot_type == "so101"
    assert bridge.last_request.timestamp_ns == 123


def test_deploy_rynnrcp_send_route_validates_shape() -> None:
    app = FastAPI()
    register_deploy_rcp_routes(app)
    client = TestClient(app, raise_server_exceptions=False)

    response = client.post(
        "/deploy/rynnrcp/send",
        json={"actions": [[1.0, 2.0] for _ in range(20)]},
    )

    assert response.status_code == 400
    assert "actions[0]" in response.json()["detail"]


def test_deploy_rynnrcp_state_uses_singleton_bridge(monkeypatch) -> None:
    class FakeBridge:
        enabled = True
        settings = RynnRCPSettings(timeout_seconds=0.01)

        def __init__(self) -> None:
            self.calls = 0

        def request_state(self) -> dict[str, object]:
            self.calls += 1
            return {"ok": True, "calls": self.calls}

    fake_bridge = FakeBridge()
    monkeypatch.setattr(deploy_rcp, "_bridge", fake_bridge)
    app = FastAPI()
    register_deploy_rcp_routes(app)
    client = TestClient(app, raise_server_exceptions=False)

    first = client.get("/deploy/rynnrcp/state")
    second = client.get("/deploy/rynnrcp/state")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["state"]["calls"] == 1
    assert second.json()["state"]["calls"] == 2


def test_deploy_rynnrcp_go_home_uses_singleton_bridge(monkeypatch) -> None:
    class FakeBridge:
        enabled = True
        settings = RynnRCPSettings(robot_type="so101", lcm_channel="rcp_robotmotion")

        def __init__(self) -> None:
            self.calls = 0

        def go_home(self) -> None:
            self.calls += 1

    fake_bridge = FakeBridge()
    monkeypatch.setattr(deploy_rcp, "_bridge", fake_bridge)
    app = FastAPI()
    register_deploy_rcp_routes(app)
    client = TestClient(app, raise_server_exceptions=False)

    response = client.post("/deploy/rynnrcp/go_home")

    assert response.status_code == 200
    assert response.json()["message"] == "rynnrcp go-home request sent"
    assert fake_bridge.calls == 1
