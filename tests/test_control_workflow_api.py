"""Tests for persisted embodied workflow configuration APIs."""

from __future__ import annotations

from types import SimpleNamespace
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

from roboclaw.config.loader import load_config, save_config, set_config_path
from roboclaw.config.schema import Config
from roboclaw.http.server import _register_system_routes


def test_control_workflow_config_roundtrip(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    save_config(Config(), config_path)
    set_config_path(config_path)

    app = FastAPI()
    _register_system_routes(app, runtime=SimpleNamespace())
    client = TestClient(app)

    record_resp = client.post(
        "/api/system/control-record-config",
        json={
            "task": "pick_cube",
            "num_episodes": 12,
            "episode_time_s": 45,
            "reset_time_s": 8,
            "dataset_name": "pick_cube_v1",
            "fps": 25,
            "use_cameras": False,
        },
    )
    assert record_resp.status_code == 200
    assert record_resp.json()["status"] == "ok"
    assert record_resp.json()["dataset_name"] == "pick_cube_v1"
    assert record_resp.json()["use_cameras"] is False

    train_resp = client.post(
        "/api/system/control-train-config",
        json={
            "dataset_name": "pick_cube_v1",
            "policy_type": "pi0",
            "steps": 200000,
            "device": "cpu",
        },
    )
    assert train_resp.status_code == 200
    assert train_resp.json()["status"] == "ok"
    assert train_resp.json()["policy_type"] == "pi0"

    infer_resp = client.post(
        "/api/system/control-infer-config",
        json={
            "checkpoint_path": "/models/pi0/checkpoints/last/pretrained_model",
            "source_dataset": "pick_cube_v1",
            "dataset_name": "eval_pick_cube_v1",
            "task": "eval_pick_cube",
            "num_episodes": 3,
            "episode_time_s": 90,
            "use_cameras": False,
        },
    )
    assert infer_resp.status_code == 200
    assert infer_resp.json()["status"] == "ok"
    assert infer_resp.json()["checkpoint_path"].endswith("pretrained_model")
    assert infer_resp.json()["use_cameras"] is False

    record_get = client.get("/api/system/control-record-config")
    train_get = client.get("/api/system/control-train-config")
    infer_get = client.get("/api/system/control-infer-config")

    assert record_get.status_code == 200
    assert train_get.status_code == 200
    assert infer_get.status_code == 200
    assert record_get.json()["task"] == "pick_cube"
    assert train_get.json()["steps"] == 200000
    assert infer_get.json()["source_dataset"] == "pick_cube_v1"

    config = load_config(config_path)
    assert config.control_center.record.dataset_name == "pick_cube_v1"
    assert config.control_center.train.policy_type == "pi0"
    assert config.control_center.infer.dataset_name == "eval_pick_cube_v1"
    assert config.control_center.infer.use_cameras is False
