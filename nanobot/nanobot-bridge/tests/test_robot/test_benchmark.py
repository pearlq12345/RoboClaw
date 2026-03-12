"""Benchmark: driver call vs exec_in_env vs raw subprocess.

Metrics:
  - M2: Tool call latency (ms) for instant operations
  - M3: Streaming task startup latency (ms)
"""

import asyncio
import json
import time
import pytest
from robot_bridge.server import create_server


class TestBenchmarkInstant:
    """Measure instant call latency with driver vs exec_in_env."""

    @pytest.fixture
    def server(self, tmp_workspace, sample_driver_code):
        (tmp_workspace / "drivers" / "test_arm.py").write_text(sample_driver_code)
        srv = create_server(workspace=tmp_workspace)
        return srv

    async def test_m2_driver_call_latency(self, server):
        """M2: Time a driver call (load + connect + get_joints)."""
        await server.call_tool("load_driver", {"name": "test_arm"})
        await server.call_tool("call", {"driver": "test_arm", "method": "connect"})

        times = []
        for _ in range(100):
            t0 = time.perf_counter()
            await server.call_tool("call", {"driver": "test_arm", "method": "get_joints"})
            times.append((time.perf_counter() - t0) * 1000)

        avg = sum(times) / len(times)
        p99 = sorted(times)[98]
        print(f"\n[M2] driver call latency: avg={avg:.2f}ms, p99={p99:.2f}ms")
        assert avg < 10, f"Driver call too slow: {avg:.2f}ms avg"

    async def test_m2_exec_in_env_latency(self, server):
        """M2: Time exec_in_env (for comparison — this is what agent uses without a driver)."""
        code = "print({'j1': 0.0, 'j2': 0.0, 'j3': 0.0})"

        times = []
        for _ in range(10):  # Fewer iterations — subprocess is slower
            t0 = time.perf_counter()
            await server.call_tool("exec_in_env", {"code": code})
            times.append((time.perf_counter() - t0) * 1000)

        avg = sum(times) / len(times)
        print(f"\n[M2] exec_in_env latency: avg={avg:.2f}ms")
        # exec_in_env spawns a subprocess, expect ~50-200ms
        assert avg < 500, f"exec_in_env too slow: {avg:.2f}ms avg"


class TestBenchmarkStreaming:
    """Measure streaming task lifecycle."""

    async def test_m3_streaming_startup_latency(self, tmp_workspace, sample_streaming_driver_code):
        (tmp_workspace / "drivers" / "test_stream.py").write_text(sample_streaming_driver_code)
        server = create_server(workspace=tmp_workspace)
        await server.call_tool("load_driver", {"name": "test_stream"})
        await server.call_tool("call", {"driver": "test_stream", "method": "connect"})

        t0 = time.perf_counter()
        result = await server.call_tool("call", {
            "driver": "test_stream",
            "method": "run_policy",
            "params": {"episodes": 3},
        })
        startup_ms = (time.perf_counter() - t0) * 1000
        content_list, _is_error = result
        data = json.loads(content_list[0].text)

        print(f"\n[M3] streaming startup: {startup_ms:.2f}ms")
        assert "task_id" in data
        assert startup_ms < 50, f"Streaming startup too slow: {startup_ms:.2f}ms"

        # Wait for completion and check
        await asyncio.sleep(0.2)
        status_result = await server.call_tool("task_status", {"task_id": data["task_id"]})
        status_content, _ = status_result
        status = json.loads(status_content[0].text)
        assert status["state"] == "completed"
