import asyncio
import pytest
from bridge_core.task_manager import TaskManager


class TestTaskManager:
    @pytest.fixture
    def manager(self):
        return TaskManager()

    async def test_start_and_complete_task(self, manager):
        async def work(*, _report_status=None):
            for i in range(3):
                await asyncio.sleep(0.01)
                if _report_status:
                    _report_status({"step": i + 1})
            return {"result": "done"}

        task_id = manager.start(work)
        assert task_id.startswith("task_")

        # Wait for completion
        await asyncio.sleep(0.15)
        status = manager.get_status(task_id)
        assert status["state"] == "completed"
        assert status["result"] == {"result": "done"}

    async def test_stop_running_task(self, manager):
        async def slow_work(*, _report_status=None):
            for i in range(1000):
                await asyncio.sleep(0.01)
                if _report_status:
                    _report_status({"step": i})
            return {"result": "done"}

        task_id = manager.start(slow_work)
        await asyncio.sleep(0.05)

        result = manager.stop(task_id)
        assert result["state"] == "cancelled"

    async def test_get_status_with_progress(self, manager):
        async def work(*, _report_status=None):
            _report_status({"episode": 1})
            await asyncio.sleep(0.5)
            return {"done": True}

        task_id = manager.start(work)
        await asyncio.sleep(0.02)

        status = manager.get_status(task_id)
        assert status["state"] == "running"
        assert status["progress"] == {"episode": 1}

        # Cleanup
        manager.stop(task_id)

    async def test_get_status_unknown_task(self, manager):
        status = manager.get_status("task_nonexistent")
        assert status["state"] == "unknown"

    async def test_list_tasks(self, manager):
        async def work(*, _report_status=None):
            await asyncio.sleep(1)

        t1 = manager.start(work)
        t2 = manager.start(work)
        tasks = manager.list_tasks()
        assert len(tasks) >= 2
        assert t1 in [t["task_id"] for t in tasks]
        assert t2 in [t["task_id"] for t in tasks]

        # Cleanup
        manager.stop(t1)
        manager.stop(t2)
