# nanobot-bridge

MCP (Model Context Protocol) bridge connecting the [nanobot](https://github.com/wavecolab/nanobot) AI agent to real robots and simulations. A single package providing two bridge servers: one for real hardware, one for PyBullet simulation.

## Architecture

```
nanobot (LLM agent, nanobot-dev env)
    │ stdio JSON-RPC (MCP protocol)
    ├──────────────────────┐
    ▼                      ▼
robot-bridge             sim-bridge
(lerobot env)            (nanobot-dev env)
    │                      │
    ▼                      ├── built-in PhysicsEngine (lazy)
drivers/*.py               ├── sim-specific tools (12 total)
    │                      └── drivers/*.py (physics injected)
    ▼
real hardware
```

### Package structure

```
nanobot-bridge/
├── bridge_core/            # Shared: DriverLoader, TaskManager, sandbox
├── robot_bridge/           # Real hardware MCP server (6 tools)
├── sim_bridge/             # Simulation MCP server (12 tools)
├── tests/
│   ├── test_core/          # Shared component tests (17)
│   ├── test_robot/         # Robot server integration + benchmarks (14)
│   └── test_sim/           # Sim server + physics tests (15)
└── examples/
    └── drivers/            # Reference drivers (so100_real, so100_sim)
```

### Key design decisions

- **Cross-environment**: Bridges run in the robot SDK's conda env (e.g. `lerobot` Python 3.10). Nanobot runs in its own env. MCP stdio connects them.
- **Driver protocol**: Plain Python files loaded at runtime via `importlib`. The LLM agent can write, modify, and hot-reload drivers.
- **Instant vs streaming**: Instant methods return immediately. Streaming methods (policy inference, teleop) run as background asyncio tasks — the LLM is never in the control loop.
- **Lazy sim init**: PyBullet engine and GUI window only start when first sim tool is called, not at bridge startup.
- **Shared core**: `bridge_core` eliminates code duplication between robot and sim bridges.

## Installation

### Quick start (simulation only)

```bash
conda activate nanobot-dev  # or any Python >= 3.10 env

# Install with simulation dependencies
pip install -e "/path/to/nanobot-bridge[sim,dev]"

# Run tests
pytest tests/ -v
```

### Full setup (real hardware + simulation)

```bash
# 1. Install in the simulation environment
conda activate nanobot-dev
pip install -e "/path/to/nanobot-bridge[sim]"

# 2. Install in the robot SDK environment (no sim deps needed)
conda activate lerobot
pip install -e /path/to/nanobot-bridge

# 3. Copy reference drivers to workspace
mkdir -p ~/.nanobot/workspace/drivers
cp examples/drivers/so100_real.py ~/.nanobot/workspace/drivers/
cp examples/drivers/so100_sim.py ~/.nanobot/workspace/drivers/
# Edit so100_sim.py to set your URDF_PATH
```

### Configure nanobot

Add to `~/.nanobot/config.json`:

```json
{
  "tools": {
    "mcp_servers": {
      "robot": {
        "command": "/path/to/conda/envs/lerobot/bin/python",
        "args": ["-m", "robot_bridge.server"],
        "env": {"NANOBOT_WORKSPACE": "~/.nanobot/workspace"},
        "tool_timeout": 60
      },
      "sim": {
        "command": "/path/to/conda/envs/nanobot-dev/bin/python",
        "args": ["-m", "sim_bridge.server", "--gui"],
        "env": {"NANOBOT_WORKSPACE": "~/.nanobot/workspace"},
        "tool_timeout": 60
      }
    }
  }
}
```

> **Use absolute Python paths**, not `conda run`. The `conda run` command doesn't properly pipe stdio for MCP.

> **DISPLAY passthrough** is automatic — nanobot's MCP client passes `DISPLAY` and related env vars to child processes.

### Verify

```bash
# Robot bridge
/path/to/envs/lerobot/bin/python -m robot_bridge.server  # Ctrl+C to exit

# Sim bridge
/path/to/envs/nanobot-dev/bin/python -m sim_bridge.server  # Ctrl+C to exit
```

## MCP Tools

### Robot bridge (6 tools)

| Tool | Description |
|---|---|
| `probe_env` | Python version, packages, available/loaded drivers |
| `exec_in_env` | Execute Python code in bridge's environment |
| `load_driver` | Load driver from `~/.nanobot/workspace/drivers/{name}.py` |
| `call` | Call a driver method (instant or streaming) |
| `task_status` | Check background task progress |
| `stop_task` | Cancel a running background task |

### Sim bridge (12 tools)

All 6 robot-bridge tools, plus:

| Tool | Description |
|---|---|
| `sim_load_robot` | Load URDF into PyBullet (triggers lazy engine init) |
| `sim_get_joints` | Read joint positions from simulation |
| `sim_set_joints` | Set joint targets and step sim |
| `sim_step` | Step physics forward (default 240 = 1 second) |
| `sim_reset` | Reset entire simulation |
| `sim_log` | Read PyBullet debug log |

## Driver Protocol

Drivers are Python files in `~/.nanobot/workspace/drivers/`. Each exports a `Driver` class:

```python
class Driver:
    name = "my_robot"
    description = "Description for the LLM"

    methods = {
        "connect": {
            "type": "instant",           # or "streaming"
            "description": "Connect to robot",
            "params": {"port": "str"},
        },
    }

    async def connect(self, port="/dev/ttyACM0"):
        return {"status": "connected"}

    # Streaming methods get _report_status callback:
    async def run_policy(self, model, *, _report_status=None):
        for step in range(100):
            _report_status({"step": step})
            await asyncio.sleep(0.02)  # 50Hz
        return {"status": "done"}
```

See `examples/drivers/` for complete examples.

## Tests

```bash
# All tests (core tests always run; sim URDF tests need SO100_URDF_PATH)
pytest tests/ -v

# Core only (no hardware or sim deps)
pytest tests/test_core/ -v

# Robot bridge only
pytest tests/test_robot/ -v

# Sim bridge only (set SO100_URDF_PATH to enable URDF-dependent tests)
SO100_URDF_PATH=/path/to/SO-ARM100/Simulation/SO100/so100.urdf pytest tests/test_sim/ -v
```

## Known Limitations & Next Steps

### Design flaws

1. **Hardcoded paths** — Driver URDF paths and config.json Python paths are absolute. No portable path resolution yet.
2. **No auth** — `exec_in_env` executes arbitrary code. Fine for local dev, not for shared deployments.
3. **PhysicsEngine is synchronous** — `step()` blocks the asyncio event loop. Long rollouts freeze other tool calls.
4. **No error recovery** — Hardware disconnects raise exceptions with no retry or safe-stop logic.
5. **Streaming has no backpressure** — `_report_status` is fire-and-forget. No way to send commands to a running stream.
6. **`mcp_sim_sim_*` name stutter** — MCP server name `sim` + tool name `sim_load_robot` produces `mcp_sim_sim_load_robot` in nanobot.
7. **No driver dependency declaration** — Drivers can't specify their pip requirements.

### Roadmap

- [ ] `nanobot init-robot` CLI — one-command setup (create envs, install bridges, write config)
- [ ] Rename sim tools to avoid double `sim_` prefix
- [ ] Camera/vision tools for sim and real
- [ ] Policy inference driver template (ACT, diffusion policy)
- [ ] Teleoperation driver (leader-follower at 100Hz)
- [ ] Data collection driver (record to HDF5/LeRobot format)
- [ ] Thread-pool physics stepping
- [ ] Docker-based bridge deployment
- [ ] Health monitoring and auto-reconnect
- [ ] Object spawning for manipulation tasks
- [ ] Domain randomization for sim-to-real

## License

MIT
