"""Dataset list / detail / delete routes."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from roboclaw.cloud.oss import AliyunOSSClient, build_dataset_manifest
from roboclaw.embodied.service import EmbodiedService


class DatasetUploadUrlRequest(BaseModel):
    dataset_id: str
    object_name: str = "dataset.tar.gz"
    content_type: str = "application/gzip"
    robot_type: str = ""
    modalities: dict[str, Any] = Field(default_factory=dict)


class DatasetCompleteUploadRequest(BaseModel):
    dataset_id: str
    provider: str = "aliyun_oss"
    cloud_uri: str
    bucket: str = ""
    object_key: str = ""
    robot_type: str = ""
    modalities: dict[str, Any] = Field(default_factory=dict)
    manifest: dict[str, Any] = Field(default_factory=dict)


def register_dataset_routes(app: FastAPI, service: EmbodiedService) -> None:

    @app.get("/api/datasets")
    async def datasets_list_route() -> list[dict]:
        refs = await asyncio.to_thread(service.datasets.list_datasets)
        return [ref.to_dict() for ref in refs]

    @app.post("/api/datasets/upload-url")
    async def dataset_upload_url(body: DatasetUploadUrlRequest) -> dict[str, Any]:
        try:
            target = await asyncio.to_thread(
                AliyunOSSClient().create_upload_target,
                dataset_id=body.dataset_id,
                object_name=body.object_name,
                content_type=body.content_type,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        manifest = build_dataset_manifest(
            dataset_id=body.dataset_id,
            robot_type=body.robot_type,
            modalities=body.modalities,
            storage={
                "provider": target.provider,
                "uri": target.cloud_uri,
                "bucket": target.bucket,
                "object_key": target.object_key,
            },
        )
        return {
            "upload": target.to_dict(),
            "manifest": manifest,
        }

    @app.post("/api/datasets/complete-upload")
    async def dataset_complete_upload(body: DatasetCompleteUploadRequest) -> dict[str, Any]:
        manifest = dict(body.manifest or {})
        if not manifest:
            manifest = build_dataset_manifest(
                dataset_id=body.dataset_id,
                robot_type=body.robot_type,
                modalities=body.modalities,
                storage={
                    "provider": body.provider,
                    "uri": body.cloud_uri,
                    "bucket": body.bucket,
                    "object_key": body.object_key,
                },
            )
        try:
            ref = await asyncio.to_thread(
                service.datasets.record_cloud_dataset,
                dataset_id=body.dataset_id,
                provider=body.provider,
                cloud_uri=body.cloud_uri,
                bucket=body.bucket,
                object_key=body.object_key,
                manifest=manifest,
                upload_status="uploaded",
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return ref.to_dict()

    @app.get("/api/datasets/{dataset_id:path}")
    async def dataset_detail(dataset_id: str) -> dict:
        ref = await asyncio.to_thread(service.datasets.get_local_dataset, dataset_id)
        if ref is None:
            ref = await asyncio.to_thread(service.datasets.get_cloud_dataset, dataset_id)
        if ref is None:
            raise HTTPException(status_code=404, detail=f"Dataset '{dataset_id}' not found")
        return ref.to_dict()

    @app.delete("/api/datasets/{dataset_id:path}")
    async def dataset_delete(dataset_id: str) -> dict[str, str]:
        try:
            await asyncio.to_thread(service.datasets.delete_dataset, dataset_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"status": "deleted", "id": dataset_id}
