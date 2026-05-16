from __future__ import annotations

import subprocess
import sys
import types

import pytest

from roboclaw_vla.rl import registry
from roboclaw_vla.rl.adapters import RoboClawEnvAdapter, compute_grpo_outcome_advantage


def test_launcher_help_imports_without_rlinf() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "roboclaw_vla.rl.launcher", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "--config-name" in result.stdout


def test_registry_returns_false_without_rlinf(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "rlinf", None)
    monkeypatch.setitem(sys.modules, "rlinf.models", None)

    assert registry.register() is False


def test_registry_registers_roboclaw_pi0_when_rlinf_is_available(monkeypatch) -> None:
    calls: list[tuple[str, object]] = []
    fake_rlinf = types.ModuleType("rlinf")
    fake_models = types.ModuleType("rlinf.models")

    def register_model(name: str, factory: object) -> None:
        calls.append((name, factory))

    fake_models.register_model = register_model  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "rlinf", fake_rlinf)
    monkeypatch.setitem(sys.modules, "rlinf.models", fake_models)

    assert registry.register() is True
    assert calls
    assert calls[0][0] == "roboclaw_pi0"
    assert callable(calls[0][1])


def test_grpo_advantage_normalizes_within_groups() -> None:
    torch = pytest.importorskip("torch")

    advantages = compute_grpo_outcome_advantage([1.0, 3.0, 2.0, 4.0], group_size=2)

    assert torch.allclose(advantages, torch.tensor([-1.0, 1.0, -1.0, 1.0]))


def test_env_adapter_normalizes_gymnasium_step() -> None:
    class Env:
        def reset(self):
            return {"state": 0}, {}

        def step(self, action):
            return {"state": action}, 1.0, False, True, {"success": True}

    adapter = RoboClawEnvAdapter(Env())

    adapter.reset()
    transition = adapter.step(7)

    assert transition["obs"] == {"state": 7}
    assert transition["reward"] == 1.0
    assert transition["done"] is True
    assert transition["truncated"] is True
    assert transition["info"]["success"] is True
