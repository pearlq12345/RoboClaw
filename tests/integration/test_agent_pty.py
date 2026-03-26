"""PTY integration tests for ``roboclaw agent``.

These tests require pexpect (``pip install pexpect``).
Mark: ``@pytest.mark.pty`` so they can be selected / skipped via ``-m pty``.

**Lifecycle tests** (simulated_agent_child) validate terminal I/O behaviour
(startup banner, exit, interrupt handling, CJK output) without an LLM.

**Flow tests** (simulated_agent) exercise full agent → tool → stub pipelines
using a stub LLM provider that maps keywords to tool calls.
"""

from __future__ import annotations

import pytest

pexpect = pytest.importorskip("pexpect")

FOLLOWER_PORT = "/dev/serial/by-id/usb-SIM_Serial_SIM001-if00"
LEADER_PORT = "/dev/serial/by-id/usb-SIM_Serial_SIM002-if00"


def _paired_arms() -> list[dict[str, object]]:
    return [
        {
            "alias": "left_follower",
            "type": "so101_follower",
            "port": FOLLOWER_PORT,
            "calibration_dir": "/tmp/cal/follower",
            "calibrated": False,
        },
        {
            "alias": "right_leader",
            "type": "so101_leader",
            "port": LEADER_PORT,
            "calibration_dir": "/tmp/cal/leader",
            "calibrated": False,
        },
    ]


# ===================================================================
# Lifecycle tests — raw pexpect child, no stub provider
# ===================================================================


@pytest.mark.pty
def test_agent_startup_and_exit(simulated_agent_child) -> None:
    """Agent should print a startup banner, accept ``exit``, and quit."""
    child = simulated_agent_child
    idx = child.expect([r"You:", pexpect.TIMEOUT, pexpect.EOF], timeout=15)
    assert idx == 0, "Agent did not reach interactive prompt"

    child.sendline("exit")
    child.expect(pexpect.EOF, timeout=10)


@pytest.mark.pty
def test_agent_quit_command(simulated_agent_child) -> None:
    """``quit`` should also terminate the agent."""
    child = simulated_agent_child
    child.expect(r"You:", timeout=15)
    child.sendline("quit")
    child.expect(pexpect.EOF, timeout=10)


@pytest.mark.pty
def test_agent_ctrl_c(simulated_agent_child) -> None:
    """Ctrl-C at the prompt should not crash the agent."""
    child = simulated_agent_child
    child.expect(r"You:", timeout=15)
    child.sendintr()
    idx = child.expect([r"You:", pexpect.EOF], timeout=10)
    assert idx in (0, 1)


@pytest.mark.pty
def test_agent_cjk_input(simulated_agent_child) -> None:
    """CJK characters should not cause encoding crashes."""
    child = simulated_agent_child
    child.expect(r"You:", timeout=15)
    child.sendline("你好")
    idx = child.expect([r"You:", r"Error", pexpect.TIMEOUT, pexpect.EOF], timeout=15)
    assert idx in (0, 1), f"Agent crashed or timed out on CJK input (idx={idx})"


# ===================================================================
# Flow tests — SimulatedAgent with stub LLM provider
# ===================================================================


@pytest.mark.pty
def test_agent_identify_flow(simulated_agent) -> None:
    """Full identify flow: move arm → select type → name → confirm."""
    simulated_agent.write_setup(arms=[])
    simulated_agent.start()

    simulated_agent.sendline("identify the moved arm")
    simulated_agent.expect("Executing identify-arms", timeout=30)
    simulated_agent.expect("Move one arm, then press Enter.")
    simulated_agent.sendline("")
    simulated_agent.expect(FOLLOWER_PORT)
    simulated_agent.expect(r"Select \[1/2\]:")
    simulated_agent.sendline("2")
    simulated_agent.expect("Name for this arm:")
    simulated_agent.sendline("sim_follower")
    simulated_agent.expect(r"OK\? \(Y/n\):")
    simulated_agent.sendline("")
    simulated_agent.expect(r"Continue\? \(Y/n\):")
    simulated_agent.sendline("n")
    simulated_agent.expect("Arm identification complete.", timeout=30)
    simulated_agent.expect_prompt()

    arms = simulated_agent.read_setup()["arms"]
    assert len(arms) == 1
    assert arms[0]["alias"] == "sim_follower"
    assert arms[0]["type"] == "so101_follower"
    assert arms[0]["port"] == FOLLOWER_PORT


@pytest.mark.pty
def test_agent_calibrate_updates_setup(simulated_agent) -> None:
    """Calibrate should mark arms as calibrated in setup.json."""
    simulated_agent.write_setup(arms=_paired_arms())
    simulated_agent.start()

    simulated_agent.sendline("calibrate every arm")
    simulated_agent.expect("Executing Calibrating: left_follower", timeout=30)
    simulated_agent.expect("2 succeeded, 0 failed.", timeout=30)
    simulated_agent.expect_prompt()

    setup = simulated_agent.read_setup()
    assert all(arm["calibrated"] for arm in setup["arms"])


@pytest.mark.pty
def test_agent_teleoperate_finishes(simulated_agent) -> None:
    """Teleoperate should complete and return to prompt."""
    simulated_agent.write_setup(arms=_paired_arms())
    simulated_agent.start()

    simulated_agent.sendline("teleoperate the robot")
    simulated_agent.expect("Executing lerobot-teleoperate", timeout=30)
    simulated_agent.expect("Teleoperation finished.", timeout=30)
    simulated_agent.expect_prompt()


@pytest.mark.pty
def test_agent_replay_finishes(simulated_agent) -> None:
    """Replay should complete and return to prompt."""
    simulated_agent.write_setup(arms=_paired_arms())
    simulated_agent.start()

    simulated_agent.sendline("replay the demo dataset")
    simulated_agent.expect("Executing lerobot-replay", timeout=30)
    simulated_agent.expect("Replay finished.", timeout=30)
    simulated_agent.expect_prompt()
