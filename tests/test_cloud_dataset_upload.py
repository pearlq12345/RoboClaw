from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from roboclaw.cloud.oss import AliyunOSSClient, AliyunOSSSettings
from roboclaw.data.datasets import DatasetCatalog
from roboclaw.embodied.service import EmbodiedService
from roboclaw.http.routes.datasets import register_dataset_routes


def test_aliyun_oss_upload_target_is_signed() -> None:
    client = AliyunOSSClient(
        AliyunOSSSettings(
            bucket="evo-bucket",
            endpoint="oss-cn-hangzhou.aliyuncs.com",
            access_key_id="ak",
            access_key_secret="secret",
            prefix="datasets",
            expires_seconds=60,
        ),
        now=lambda: 1000,
    )

    target = client.create_upload_target(
        dataset_id="pick-cube",
        object_name="dataset.tar.gz",
        content_type="application/gzip",
    )

    payload = target.to_dict()
    assert payload["provider"] == "aliyun_oss"
    assert payload["bucket"] == "evo-bucket"
    assert payload["objectKey"] == "datasets/pick-cube/dataset.tar.gz"
    assert payload["cloudUri"] == "oss://evo-bucket/datasets/pick-cube/dataset.tar.gz"
    assert "OSSAccessKeyId=ak" in payload["uploadUrl"]
    assert "Signature=" in payload["uploadUrl"]
    assert payload["headers"] == {"Content-Type": "application/gzip"}


def test_dataset_catalog_records_cloud_dataset(tmp_path) -> None:
    catalog = DatasetCatalog(root_resolver=lambda: tmp_path)

    ref = catalog.record_cloud_dataset(
        dataset_id="pick-cube",
        provider="aliyun_oss",
        cloud_uri="oss://bucket/datasets/pick-cube/dataset.tar.gz",
        bucket="bucket",
        object_key="datasets/pick-cube/dataset.tar.gz",
        manifest={
            "dataset_id": "pick-cube",
            "robot_type": "so101",
            "episodes": 2,
            "modalities": {"exteroceptive": ["rgb"], "proprioceptive": ["joint_pos"]},
        },
    )

    payload = ref.to_dict()
    assert payload["id"] == "cloud/pick-cube"
    assert payload["kind"] == "cloud"
    assert payload["stats"]["total_episodes"] == 2
    assert payload["stats"]["robot_type"] == "so101"
    assert payload["cloud"]["uploadStatus"] == "uploaded"
    assert catalog.require_cloud_dataset("cloud/pick-cube").cloud is not None
    assert [item.id for item in catalog.list_datasets()] == ["cloud/pick-cube"]


def test_dataset_upload_routes_register_cloud_dataset(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ALIYUN_OSS_BUCKET", "bucket")
    monkeypatch.setenv("ALIYUN_OSS_ENDPOINT", "oss-cn-hangzhou.aliyuncs.com")
    monkeypatch.setenv("ALIYUN_OSS_ACCESS_KEY_ID", "ak")
    monkeypatch.setenv("ALIYUN_OSS_ACCESS_KEY_SECRET", "secret")

    app = FastAPI()
    service = EmbodiedService()
    service.datasets = DatasetCatalog(root_resolver=lambda: tmp_path)
    register_dataset_routes(app, service)
    client = TestClient(app)

    upload = client.post(
        "/api/datasets/upload-url",
        json={
            "dataset_id": "pick-cube",
            "robot_type": "so101",
            "modalities": {"exteroceptive": ["rgb"], "proprioceptive": ["joint_pos"]},
        },
    )

    assert upload.status_code == 200
    upload_payload = upload.json()
    assert upload_payload["upload"]["cloudUri"] == "oss://bucket/datasets/pick-cube/dataset.tar.gz"
    assert upload_payload["manifest"]["storage"]["provider"] == "aliyun_oss"

    complete = client.post(
        "/api/datasets/complete-upload",
        json={
            "dataset_id": "pick-cube",
            "cloud_uri": upload_payload["upload"]["cloudUri"],
            "bucket": upload_payload["upload"]["bucket"],
            "object_key": upload_payload["upload"]["objectKey"],
            "manifest": upload_payload["manifest"],
        },
    )

    assert complete.status_code == 200
    completed = complete.json()
    assert completed["id"] == "cloud/pick-cube"
    assert completed["cloud"]["uri"] == "oss://bucket/datasets/pick-cube/dataset.tar.gz"
    assert client.get("/api/datasets/cloud/pick-cube").json()["kind"] == "cloud"
    assert client.get("/api/datasets").json()[0]["id"] == "cloud/pick-cube"
