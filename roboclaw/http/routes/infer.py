"""Inference routes — trained policy rollout."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException

from roboclaw.embodied.service import EmbodiedService
from roboclaw.embodied.workflow import InferWorkflowConfig


InferStartRequest = InferWorkflowConfig


def register_infer_routes(app: FastAPI, service: EmbodiedService) -> None:

    @app.post("/api/infer/start")
    async def infer_start(body: InferStartRequest) -> dict[str, Any]:
        try:
            await service.start_inference(
                checkpoint_path=body.checkpoint_path,
                source_dataset=body.source_dataset,
                dataset_name=body.dataset_name,
                task=body.task,
                num_episodes=body.num_episodes,
                episode_time_s=body.episode_time_s,
                use_cameras=body.use_cameras,
                arms=body.arms,
            )
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(400, str(exc)) from exc
        return {"status": "inferring"}

    @app.post("/api/infer/stop")
    async def infer_stop() -> dict[str, str]:
        await service.stop()
        return {"status": "idle"}
