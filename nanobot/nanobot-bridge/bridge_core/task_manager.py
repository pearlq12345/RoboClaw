"""Background task manager for streaming robot operations."""

import asyncio
import time
from typing import Any, Callable, Coroutine
from uuid import uuid4


class TaskManager:
    """Manage background asyncio tasks with status tracking."""

    def __init__(self):
        self._tasks: dict[str, dict[str, Any]] = {}

    def start(self, coro_func: Callable[..., Coroutine], **kwargs) -> str:
        """Start a background task. Returns task_id.

        The coro_func receives a _report_status callback for progress updates.
        """
        task_id = f"task_{uuid4().hex[:8]}"
        progress: dict[str, Any] = {}

        def report_status(status: dict):
            progress.update(status)

        async def _run():
            try:
                result = await coro_func(_report_status=report_status, **kwargs)
                self._tasks[task_id]["state"] = "completed"
                self._tasks[task_id]["result"] = result
            except asyncio.CancelledError:
                self._tasks[task_id]["state"] = "cancelled"
            except Exception as e:
                self._tasks[task_id]["state"] = "error"
                self._tasks[task_id]["error"] = str(e)

        asyncio_task = asyncio.get_event_loop().create_task(_run())

        self._tasks[task_id] = {
            "task_id": task_id,
            "state": "running",
            "started_at": time.time(),
            "progress": progress,
            "result": None,
            "error": None,
            "_asyncio_task": asyncio_task,
        }
        return task_id

    def get_status(self, task_id: str) -> dict[str, Any]:
        """Get current status of a task."""
        entry = self._tasks.get(task_id)
        if not entry:
            return {"task_id": task_id, "state": "unknown"}
        return {
            "task_id": task_id,
            "state": entry["state"],
            "progress": entry["progress"],
            "result": entry["result"],
            "error": entry["error"],
            "elapsed_s": round(time.time() - entry["started_at"], 1),
        }

    def stop(self, task_id: str) -> dict[str, Any]:
        """Cancel a running task."""
        entry = self._tasks.get(task_id)
        if not entry:
            return {"task_id": task_id, "state": "unknown"}
        if entry["state"] == "running":
            entry["_asyncio_task"].cancel()
            entry["state"] = "cancelled"
        return self.get_status(task_id)

    def list_tasks(self) -> list[dict[str, Any]]:
        """List all tasks with their status."""
        return [self.get_status(tid) for tid in self._tasks]

    def cleanup_completed(self, max_age_s: float = 3600) -> int:
        """Remove completed/cancelled/error tasks older than max_age_s."""
        now = time.time()
        to_remove = [
            tid for tid, entry in self._tasks.items()
            if entry["state"] in ("completed", "cancelled", "error")
            and (now - entry["started_at"]) > max_age_s
        ]
        for tid in to_remove:
            del self._tasks[tid]
        return len(to_remove)
