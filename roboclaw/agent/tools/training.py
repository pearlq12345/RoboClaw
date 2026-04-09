"""Training pipeline tools for the agent: train, eval, serve, checkpoint management."""
from __future__ import annotations

import json
from typing import Any

from roboclaw.agent.tools.base import Tool
from roboclaw.embodied.learning.pipeline import Stage, TrainingPipeline


class TrainTool(Tool):
    """Start a policy training job."""

    name = "train_policy"
    description = (
        "Start training a robot policy on a recorded dataset. "
        "Supports ACT (imitation learning). "
        "Returns a job_id used to track progress."
    )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "dataset_name": {
                    "type": "string",
                    "description": "Dataset slug used during recording.",
                },
                "algorithm": {
                    "type": "string",
                    "default": "act",
                    "enum": ["act"],
                    "description": "Training algorithm. Currently only 'act' is supported.",
                },
                "steps": {
                    "type": "integer",
                    "default": 100000,
                    "description": "Number of training steps.",
                },
                "device": {
                    "type": "string",
                    "default": "cuda",
                    "description": "Device to train on (cuda or cpu).",
                },
            },
            "required": ["dataset_name"],
            "additionalProperties": False,
        }

    async def execute(self, **kwargs: Any) -> str:
        tp = TrainingPipeline()
        try:
            job_id = await tp.train(
                dataset_name=kwargs["dataset_name"],
                algorithm=kwargs.get("algorithm", "act"),
                steps=kwargs.get("steps", 100000),
                device=kwargs.get("device", "cuda"),
            )
        except NotImplementedError as e:
            return str(e)
        job = tp.get_job(job_id)
        return (
            f"Training started.\n"
            f"  job_id: {job_id}\n"
            f"  dataset: {kwargs['dataset_name']}\n"
            f"  algorithm: {kwargs.get('algorithm', 'act')}\n"
            f"  target steps: {kwargs.get('steps', 100000)}\n"
            f"  output_dir: {job.output_dir if job else 'unknown'}\n\n"
            f"Use job_status to monitor progress."
        )


class JobStatusTool(Tool):
    """Check the status of a training or eval job."""

    name = "job_status"
    description = "Poll a background training or serving job by job_id."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "job_id": {"type": "string", "description": "Job ID from train_policy or serve_policy."},
                "watch": {
                    "type": "boolean",
                    "default": False,
                    "description": "If true, poll until the job finishes (long-running).",
                },
                "poll_interval_s": {
                    "type": "number",
                    "default": 10.0,
                    "description": "Poll interval in seconds when watch=true.",
                },
            },
            "required": ["job_id"],
            "additionalProperties": False,
        }

    async def execute(self, **kwargs: Any) -> str:
        tp = TrainingPipeline()
        job = tp.get_job(kwargs["job_id"])
        if job is None:
            return f"No job found with id '{kwargs['job_id']}'."

        if kwargs.get("watch"):
            job = await tp.poll(kwargs["job_id"], interval_s=kwargs.get("poll_interval_s", 10.0))
            return _format_finished_job(job)

        return _format_job(job)


class EvalTool(Tool):
    """Run evaluation on a trained policy checkpoint."""

    name = "eval_policy"
    description = (
        "Evaluate a trained policy on a dataset. "
        "Parses success rate from lerobot-eval output."
    )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "job_id": {
                    "type": "string",
                    "description": "Job ID from train_policy whose checkpoint to evaluate.",
                },
                "eval_dataset": {
                    "type": "string",
                    "description": "Dataset to evaluate on. Defaults to the training dataset.",
                },
                "num_episodes": {
                    "type": "integer",
                    "default": 10,
                    "description": "Number of evaluation episodes.",
                },
                "device": {
                    "type": "string",
                    "default": "cuda",
                    "description": "Device (cuda or cpu).",
                },
            },
            "required": ["job_id"],
            "additionalProperties": False,
        }

    async def execute(self, **kwargs: Any) -> str:
        tp = TrainingPipeline()
        try:
            result = await tp.eval(
                job_id=kwargs["job_id"],
                eval_dataset=kwargs.get("eval_dataset"),
                num_episodes=kwargs.get("num_episodes", 10),
                device=kwargs.get("device", "cuda"),
            )
        except FileNotFoundError as e:
            return f"Checkpoint not found: {e}"
        except ValueError as e:
            return str(e)

        if not result.get("success"):
            return f"Eval failed.\nstderr: {result.get('stderr', 'unknown')}"

        sr = result.get("success_rate")
        sr_str = f"{sr:.1%}" if sr is not None else "not parsed from output"
        return (
            f"Eval complete for job {kwargs['job_id']}:\n"
            f"  checkpoint: {result.get('checkpoint')}\n"
            f"  success_rate: {sr_str}\n"
            f"  episodes: {kwargs.get('num_episodes', 10)}"
        )


class ServeTool(Tool):
    """Start an HTTP inference server for a trained policy."""

    name = "serve_policy"
    description = (
        "Start an HTTP inference server (lerobot-serve) for a trained policy checkpoint. "
        "Returns the server URL. "
        "Use record with checkpoint_path to run policy inference from the web UI."
    )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "job_id": {
                    "type": "string",
                    "description": "Job ID from train_policy whose checkpoint to serve.",
                },
                "device": {
                    "type": "string",
                    "default": "cuda",
                    "description": "Device (cuda or cpu).",
                },
                "host": {
                    "type": "string",
                    "default": "0.0.0.0",
                    "description": "Host to bind the server to.",
                },
                "port": {
                    "type": "integer",
                    "default": 8000,
                    "description": "Port to serve on.",
                },
            },
            "required": ["job_id"],
            "additionalProperties": False,
        }

    async def execute(self, **kwargs: Any) -> str:
        tp = TrainingPipeline()
        try:
            url = await tp.serve(
                job_id=kwargs["job_id"],
                device=kwargs.get("device", "cuda"),
                host=kwargs.get("host", "0.0.0.0"),
                port=kwargs.get("port", 8000),
            )
        except FileNotFoundError as e:
            return f"Checkpoint not found: {e}"
        except ValueError as e:
            return str(e)

        return (
            f"Policy server started.\n"
            f"  URL: {url}\n"
            f"  job_id: {kwargs['job_id']}\n"
            f"Use record with checkpoint_path=<checkpoint> to run inference."
        )


class ListCheckpointsTool(Tool):
    """List all available policy checkpoints."""

    name = "list_checkpoints"
    description = "List all checkpoints from a trained policy output directory."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "output_dir": {
                    "type": "string",
                    "description": "Policy output directory (from train_policy output_dir field).",
                },
            },
            "required": ["output_dir"],
            "additionalProperties": False,
        }

    async def execute(self, **kwargs: Any) -> str:
        tp = TrainingPipeline()
        checkpoints = tp.list_checkpoints(kwargs["output_dir"])
        if not checkpoints:
            return f"No checkpoints found in {kwargs['output_dir']}."
        lines = [f"Checkpoints in {kwargs['output_dir']}:"]
        for cp in checkpoints:
            tag = " (best)" if cp["is_best"] else ""
            lines.append(f"  step {cp['step']}{tag}: {cp['path']}")
        return "\n".join(lines)


def _format_job(job) -> str:
    elapsed = job.elapsed_s
    mins, secs = divmod(int(elapsed), 60)
    lines = [
        f"job_id: {job.job_id}",
        f"stage: {job.stage.value}",
        f"elapsed: {mins}m {secs}s",
        f"repo_id: {job.repo_id}",
    ]
    if job.metrics_history:
        last = job.metrics_history[-1]
        if last.step is not None:
            pct = (last.step / max(job.total_steps or 1, 1)) * 100
            lines.append(f"step: {last.step}/{job.total_steps} ({pct:.1f}%)")
        if last.loss is not None:
            lines.append(f"loss: {last.loss:.4f}")
        if last.lr is not None:
            lines.append(f"lr: {last.lr:.2e}")
    return "\n".join(lines)


def _format_finished_job(job) -> str:
    elapsed = job.elapsed_s
    mins, secs = divmod(int(elapsed), 60)
    lines = [
        f"job_id: {job.job_id}",
        f"stage: {job.stage.value} (finished)",
        f"total time: {mins}m {secs}s",
        f"repo_id: {job.repo_id}",
    ]
    if job.metrics_history:
        last = job.metrics_history[-1]
        if last.step is not None:
            lines.append(f"final_step: {last.step}")
        if last.loss is not None:
            lines.append(f"final_loss: {last.loss:.4f}")
    return "\n".join(lines)
