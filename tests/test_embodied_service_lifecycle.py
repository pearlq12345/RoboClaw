from __future__ import annotations

import asyncio
import json
import sys
import types
from pathlib import Path
from unittest.mock import patch

import pytest

if "roboclaw.embodied.service.hub" not in sys.modules:
    hub_mod = types.ModuleType("roboclaw.embodied.service.hub")

    class HubService:
        def __init__(self, parent) -> None:
            self.parent = parent

    hub_mod.HubService = HubService
    sys.modules["roboclaw.embodied.service.hub"] = hub_mod

if "roboclaw.embodied.embodiment.doctor" not in sys.modules:
    doctor_mod = types.ModuleType("roboclaw.embodied.embodiment.doctor")

    class DoctorService:
        def __init__(self, parent) -> None:
            self.parent = parent

        async def check(self, manifest, kwargs, tty_handoff) -> str:
            return json.dumps({
                "environment": {},
                "manifest": manifest.snapshot,
                "hardware_status": self.parent.get_hardware_status(manifest),
            })

    doctor_mod.DoctorService = DoctorService
    sys.modules["roboclaw.embodied.embodiment.doctor"] = doctor_mod

from roboclaw.embodied.embodiment.lock import EmbodimentFileLock
from roboclaw.embodied.embodiment.manifest import Manifest
from roboclaw.embodied.service import EmbodiedService


_MANIFEST_DATA = {
    "version": 2,
    "arms": [],
    "hands": [],
    "cameras": [],
    "datasets": {"root": "/tmp/datasets"},
    "policies": {"root": "/tmp/policies"},
}


class ControlledSession:
    def __init__(self, board, result_text: str) -> None:
        self.board = board
        self._result_text = result_text
        self._busy = False
        self._wait_task: asyncio.Task | None = None
        self._exit_callback = None
        self.started = asyncio.Event()
        self.finish = asyncio.Event()
        self.argv: list[str] | None = None

    async def start(self, argv: list[str]) -> None:
        self.argv = argv
        self._busy = True
        self.started.set()

        async def _runner() -> None:
            await self.finish.wait()
            self._busy = False

        self._wait_task = asyncio.create_task(_runner())

    async def stop(self) -> None:
        self.finish.set()
        if self._wait_task is not None:
            await self._wait_task

    async def wait(self) -> None:
        if self._wait_task is not None:
            await self._wait_task

    @property
    def busy(self) -> bool:
        return self._busy

    def result(self) -> str:
        return self._result_text


class FailingSession:
    def __init__(self) -> None:
        self._exit_callback = None

    async def start(self, argv: list[str]) -> None:
        raise RuntimeError("boom")

    @property
    def busy(self) -> bool:
        return False


def _make_service(tmp_path: Path) -> EmbodiedService:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(_MANIFEST_DATA), encoding="utf-8")
    manifest = Manifest(path=manifest_path)
    service = EmbodiedService(manifest=manifest)
    service._file_lock = EmbodimentFileLock(path=tmp_path / ".embodiment.lock")
    return service


@pytest.mark.asyncio
async def test_run_replay_waits_for_process_completion_without_tty(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    service.replay = ControlledSession(service.board, "Replay finished.")
    run_replay = getattr(service, "run_replay")

    with patch("roboclaw.embodied.service.CommandBuilder.replay", return_value=["replay-cmd"]):
        task = asyncio.create_task(run_replay(dataset_name="demo", episode=2, fps=15))
        await asyncio.wait_for(service.replay.started.wait(), timeout=1)

        assert service.busy
        assert service.embodiment_busy
        assert not task.done()

        service.replay.finish.set()
        result = await asyncio.wait_for(task, timeout=1)

    assert result == "Replay finished."
    assert service.replay.argv == ["replay-cmd"]
    assert not service.busy
    assert not service.embodiment_busy
    assert service._active_session is None


@pytest.mark.asyncio
async def test_run_inference_waits_for_process_completion_without_tty(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    service.infer = ControlledSession(service.board, "Inference finished.")
    run_inference = getattr(service, "run_inference")

    with patch("roboclaw.embodied.service.CommandBuilder.infer", return_value=["infer-cmd"]):
        task = asyncio.create_task(run_inference(checkpoint_path="/models/act", num_episodes=3))
        await asyncio.wait_for(service.infer.started.wait(), timeout=1)

        assert service.busy
        assert service.embodiment_busy
        assert not task.done()

        service.infer.finish.set()
        result = await asyncio.wait_for(task, timeout=1)

    assert result == "Inference finished."
    assert service.infer.argv == ["infer-cmd"]
    assert not service.busy
    assert not service.embodiment_busy
    assert service._active_session is None


@pytest.mark.asyncio
async def test_start_teleop_releases_lock_on_session_start_failure(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    service.teleop = FailingSession()

    with patch("roboclaw.embodied.service.CommandBuilder.teleop", return_value=["teleop-cmd"]):
        with pytest.raises(RuntimeError, match="boom"):
            await service.start_teleop(fps=20)

    assert not service.busy
    assert not service.embodiment_busy
    assert service._active_session is None


@pytest.mark.asyncio
async def test_start_recording_releases_lock_on_session_start_failure(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    service.record = FailingSession()

    with patch(
        "roboclaw.embodied.service.CommandBuilder.record",
        return_value=(["record-cmd"], "demo"),
    ):
        with pytest.raises(RuntimeError, match="boom"):
            await service.start_recording(task="pick", dataset_name="demo")

    assert not service.busy
    assert not service.embodiment_busy
    assert service._active_session is None


@pytest.mark.asyncio
async def test_start_replay_releases_lock_on_session_start_failure(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    service.replay = FailingSession()

    with patch("roboclaw.embodied.service.CommandBuilder.replay", return_value=["replay-cmd"]):
        with pytest.raises(RuntimeError, match="boom"):
            await service.start_replay(dataset_name="demo")

    assert not service.busy
    assert not service.embodiment_busy
    assert service._active_session is None


@pytest.mark.asyncio
async def test_start_inference_releases_lock_on_session_start_failure(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    service.infer = FailingSession()

    with patch("roboclaw.embodied.service.CommandBuilder.infer", return_value=["infer-cmd"]):
        with pytest.raises(RuntimeError, match="boom"):
            await service.start_inference(checkpoint_path="/models/act")

    assert not service.busy
    assert not service.embodiment_busy
    assert service._active_session is None
