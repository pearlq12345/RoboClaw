"""Training pipeline: train → eval → checkpoint tracking → serve."""
from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from roboclaw.embodied.learning.act import ACTPipeline


class Stage(Enum):
    IDLE = "idle"
    TRAINING = "training"
    EVALUATING = "evaluating"
    SERVING = "serving"


@dataclass
class TrainingMetrics:
    """Extracted metrics from a training log line."""
    step: int | None = None
    loss: float | None = None
    lr: float | None = None
    grad_norm: float | None = None
    episode_len_mean: float | None = None
    episode_reward: float | None = None
    raw: str = ""


@dataclass
class JobInfo:
    """Persistent state for a training or eval job."""
    job_id: str
    stage: Stage
    repo_id: str
    output_dir: Path
    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    best_step: int | None = None
    best_metric: float | None = None
    best_is_final: bool = False
    total_steps: int | None = None
    metrics_history: list[TrainingMetrics] = field(default_factory=list)

    @property
    def elapsed_s(self) -> float:
        return (self.finished_at or time.time()) - self.started_at

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "stage": self.stage.value,
            "repo_id": self.repo_id,
            "output_dir": str(self.output_dir),
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "best_step": self.best_step,
            "best_metric": self.best_metric,
            "best_is_final": self.best_is_final,
            "total_steps": self.total_steps,
            "elapsed_s": round(self.elapsed_s, 1),
        }


class TrainingPipeline:
    """
    Unified training pipeline wrapping LeRobot training + eval + inference.

    Usage:
        tp = TrainingPipeline()
        job_id = await tp.train(dataset_name="my_data", steps=50000)
        await tp.poll(job_id)           # wait for completion
        result = await tp.eval(job_id)  # run eval
        await tp.serve(job_id)          # start inference server
    """

    _state_file_name = "training_jobs.json"

    def __init__(self, policies_root: str | None = None):
        if policies_root is None:
            from roboclaw.embodied.manifest.helpers import load_manifest
            manifest = load_manifest()
            policies_root = manifest.get("policies", {}).get("root", "~/.roboclaw/workspace/embodied/policies")
        self._policies_root = Path(policies_root).expanduser()
        self._policies_root.mkdir(parents=True, exist_ok=True)
        self._act = ACTPipeline()
        self._jobs: dict[str, JobInfo] = {}
        self._load_state()

    # ── Training ──────────────────────────────────────────────────────────────

    async def train(
        self,
        dataset_name: str,
        dataset_root: str | None = None,
        steps: int = 100_000,
        device: str = "cuda",
        algorithm: str = "act",
        env: dict | None = None,
    ) -> str:
        """
        Start a training job and return a job_id.

        Currently only algorithm='act' is supported.
        Others (xvl, diffusion, pi0) are stubs that raise NotImplementedError.
        """
        if algorithm != "act":
            raise NotImplementedError(f"Algorithm '{algorithm}' not yet implemented. Only 'act' is supported.")

        if dataset_root is None:
            from roboclaw.embodied.manifest.helpers import load_manifest
            manifest = load_manifest()
            ds_root = manifest.get("datasets", {}).get("root", "~/.roboclaw/workspace/embodied/datasets")
        else:
            ds_root = dataset_root

        from roboclaw.embodied.runner import LocalLeRobotRunner
        from roboclaw.embodied.engine.helpers import _logs_dir

        output_dir = self._policies_root / dataset_name
        resume = output_dir.is_dir()
        argv = self._act.train(
            repo_id=f"local/{dataset_name}",
            dataset_root=str(Path(ds_root).expanduser()),
            output_dir=str(output_dir),
            steps=steps,
            device=device,
            resume=resume,
        )

        runner = LocalLeRobotRunner()
        job_id = await runner.run_detached(argv=argv, log_dir=_logs_dir())

        job = JobInfo(
            job_id=job_id,
            stage=Stage.TRAINING,
            repo_id=f"local/{dataset_name}",
            output_dir=output_dir,
            total_steps=steps,
        )
        self._jobs[job_id] = job
        self._save_state()
        return job_id

    async def poll(self, job_id: str, interval_s: float = 10.0) -> JobInfo:
        """
        Poll until the training job finishes, then return final JobInfo.

        Polls the runner's job status and parses log lines for metrics.
        """
        from roboclaw.embodied.runner import LocalLeRobotRunner
        from roboclaw.embodied.engine.helpers import _logs_dir

        runner = LocalLeRobotRunner()
        while True:
            status = await runner.job_status(job_id=job_id, log_dir=_logs_dir())
            if not status["running"]:
                job = self._jobs.get(job_id)
                if job is not None:
                    job.stage = Stage.IDLE
                    job.finished_at = time.time()
                    self._save_state()
                break

            # Parse metrics from log tail
            job = self._jobs.get(job_id)
            if job is not None:
                tail = status.get("log_tail", "")
                for line in tail.splitlines():
                    m = self._parse_metrics(line)
                    if m is not None:
                        job.metrics_history.append(m)

            await asyncio.sleep(interval_s)

        return self._jobs.get(job_id, JobInfo(job_id=job_id, stage=Stage.IDLE, repo_id="", output_dir=Path()))

    # ── Evaluation ───────────────────────────────────────────────────────────

    async def eval(
        self,
        job_id: str,
        eval_dataset: str | None = None,
        num_episodes: int = 10,
        device: str = "cuda",
    ) -> dict:
        """
        Run lerobot-eval on the best checkpoint from a training job.

        Returns a dict with eval metrics.
        """
        from roboclaw.embodied.embodiment.arm.command_builder import ArmCommandBuilder
        from roboclaw.embodied.runner import LocalLeRobotRunner
        from roboclaw.embodied.engine.helpers import _logs_dir
        from roboclaw.embodied.manifest.helpers import ensure_manifest

        job = self._jobs.get(job_id)
        if job is None:
            raise ValueError(f"Unknown job_id: {job_id}")

        checkpoint = self.checkpoint_path(str(job.output_dir))
        if not Path(checkpoint).exists():
            raise FileNotFoundError(f"No checkpoint found at {checkpoint}")

        manifest = ensure_manifest()
        manifest_snapshot = manifest.snapshot
        cameras_root = manifest_snapshot.get("cameras", [])
        if cameras_root:
            cameras = {cam["alias"]: {"type": "opencv", "index_or_path": cam["port"]} for cam in cameras_root}
        else:
            cameras = {}

        # Run lerobot-eval via subprocess
        argv = [
            "lerobot-eval",
            f"--policy.repo_id={checkpoint}",
            f"--dataset.repo_id={eval_dataset or job.repo_id}",
            f"--policy.device={device}",
            f"--eval.n_episodes={num_episodes}",
        ]

        runner = LocalLeRobotRunner()
        rc, stdout, stderr = await runner.run(argv, timeout=600)
        if rc != 0:
            return {
                "job_id": job_id,
                "success": False,
                "stdout": stdout[-1000:],
                "stderr": stderr[-1000:],
            }

        # Parse success rate from output
        success_rate = self._parse_success_rate(stdout + stderr)
        return {
            "job_id": job_id,
            "success": True,
            "checkpoint": checkpoint,
            "success_rate": success_rate,
            "stdout": stdout[-2000:],
        }

    # ── Checkpoint management ─────────────────────────────────────────────────

    def checkpoint_path(self, output_dir: str) -> str:
        """Return the best or last checkpoint path."""
        p = Path(output_dir).expanduser() / "checkpoints"
        best = p / "best" / "pretrained_model"
        last = p / "last" / "pretrained_model"
        if best.exists():
            return str(best)
        return str(last)

    def list_checkpoints(self, output_dir: str) -> list[dict]:
        """List all checkpoints under output_dir with step numbers."""
        root = Path(output_dir).expanduser()
        checkpoints: list[dict] = []
        for cp_dir in root.rglob("pretrained_model"):
            step = self._parse_step_from_path(cp_dir)
            checkpoints.append({
                "path": str(cp_dir),
                "step": step,
                "is_best": "best" in str(cp_dir),
            })
        checkpoints.sort(key=lambda x: x["step"] or 0, reverse=True)
        return checkpoints

    # ── Serve (inference) ─────────────────────────────────────────────────────

    async def serve(
        self,
        job_id: str,
        device: str = "cuda",
        host: str = "0.0.0.0",
        port: int = 8000,
    ) -> str:
        """Start an inference server for a trained policy. Returns the server URL."""
        from roboclaw.embodied.runner import LocalLeRobotRunner
        from roboclaw.embodied.engine.helpers import _logs_dir

        job = self._jobs.get(job_id)
        if job is None:
            raise ValueError(f"Unknown job_id: {job_id}")

        checkpoint = self.checkpoint_path(str(job.output_dir))
        if not Path(checkpoint).exists():
            raise FileNotFoundError(f"No checkpoint found at {checkpoint}")

        argv = [
            "lerobot-serve",
            f"--policy.repo_id={checkpoint}",
            f"--policy.device={device}",
            f"--host={host}",
            f"--port={port}",
        ]

        runner = LocalLeRobotRunner()
        server_job_id = await runner.run_detached(argv=argv, log_dir=_logs_dir())
        job.stage = Stage.SERVING
        self._save_state()
        return f"http://{host}:{port}"

    # ── State persistence ──────────────────────────────────────────────────────

    def _state_path(self) -> Path:
        return self._policies_root / self._state_file_name

    def _load_state(self) -> None:
        path = self._state_path()
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text())
            for jid, info in data.items():
                info["stage"] = Stage(info["stage"])
                info["output_dir"] = Path(info["output_dir"])
                # Reconstruct TrainingMetrics objects from loaded dicts
                raw_history = info.get("metrics_history") or []
                info["metrics_history"] = [
                    TrainingMetrics(**m) if isinstance(m, dict) else m
                    for m in raw_history
                ]
                self._jobs[jid] = JobInfo(**info)
        except Exception:
            pass

    def _save_state(self) -> None:
        data = {jid: job.to_dict() for jid, job in self._jobs.items()}
        self._state_path().write_text(json.dumps(data, indent=2, ensure_ascii=False))

    def get_job(self, job_id: str) -> JobInfo | None:
        return self._jobs.get(job_id)

    def list_jobs(self) -> list[dict]:
        return [job.to_dict() for job in self._jobs.values()]

    # ── Log parsing helpers ──────────────────────────────────────────────────

    _METRIC_RE = re.compile(
        r"(?:step|Step|STEP)\s*[=:]\s*(\d+)|"
        r"(?:loss|Loss|LOSS)\s*[=:]\s*([0-9.]+)|"
        r"(?:lr|LR)\s*[=:]\s*([0-9.e-]+)|"
        r"(?:grad_norm|GradNorm)\s*[=:]\s*([0-9.]+)|"
        r"(?:episode_reward|EpisodeReward)\s*[=:]\s*(-?[0-9.]+)|"
        r"(?:success_rate|SuccessRate)\s*[=:]\s*([0-9.]+)"
    )

    def _parse_metrics(self, line: str) -> TrainingMetrics | None:
        m = self._METRIC_RE.findall(line)
        if not m:
            return None
        kw = {"raw": line}
        for group in m:
            if group[0]:
                kw["step"] = int(group[0])
            if group[1]:
                kw["loss"] = float(group[1])
            if group[2]:
                kw["lr"] = float(group[2])
            if group[3]:
                kw["grad_norm"] = float(group[3])
            if group[4]:
                kw["episode_reward"] = float(group[4])
            if group[5]:
                kw["episode_reward"] = float(group[5])  # success_rate aliased as reward
        return TrainingMetrics(**{k: v for k, v in kw.items() if v})

    def _parse_step_from_path(self, path: Path) -> int | None:
        m = re.search(r"step[_\s]*(\d+)", str(path))
        return int(m.group(1)) if m else None

    def _parse_success_rate(self, text: str) -> float | None:
        m = re.search(r"(?:success_rate|Success Rate|SUCCESS)\s*[:=]\s*([0-9.]+)", text, re.I)
        if m:
            return float(m.group(1))
        m = re.search(r"(\d+)/(\d+)\s+(?:episodes? )?(?:succeeded|success)", text, re.I)
        if m:
            return int(m.group(1)) / max(int(m.group(2)), 1)
        return None
