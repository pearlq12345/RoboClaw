# nanobot-bridge 架构设计文档

> 本文档记录了 nanobot-bridge 的完整设计思路、技术决策、踩过的坑和解决方案。目的是让团队成员快速理解这套系统的来龙去脉。

---

## 1. 核心问题：LLM 怎么控制机器人？

我们的 nanobot 是一个 LLM agent 框架。我们要让 LLM 能够：

1. **直接控制真实硬件** — SO-100 6-DOF 机械臂（Feetech STS3215 舵机）
2. **操作仿真环境** — PyBullet 物理引擎
3. **启动实时任务** — 策略推理(50Hz)、遥操作(100Hz)，但 LLM 不在实时控制环路内
4. **动态写代码适配新硬件** — Agent 自己写 driver 文件，自己加载

关键矛盾：nanobot 运行在 Python 3.11（nanobot-dev conda env），而 lerobot（机器人 SDK）需要 Python 3.10（lerobot conda env）。它们不能在同一个进程里。

---

## 2. 解决方案：MCP Bridge

### 2.1 为什么选 MCP？

MCP（Model Context Protocol）是一个 JSON-RPC over stdio 的协议。nanobot 已经原生支持 MCP——外部进程通过 stdin/stdout 暴露 tools，nanobot 把它们包装成 `MCPToolWrapper`，LLM 完全无法区分 MCP tool 和原生 tool。

这意味着：
- Bridge 作为独立子进程运行，**可以用任意 Python 版本和 conda 环境**
- Bridge 常驻运行，**持有硬件连接**（不需要每次调用都重连）
- 对 LLM 完全透明，**不需要教 LLM 什么是 MCP**

### 2.2 整体架构

```
nanobot (LLM agent, nanobot-dev env, Python 3.11)
    │ stdio JSON-RPC (MCP protocol)
    ├──────────────────────────┐
    ▼                          ▼
robot-bridge                 sim-bridge
(lerobot env, Python 3.10)   (nanobot-dev env, Python 3.11)
    │                          │
    ▼                          ├── PhysicsEngine (PyBullet, lazy init)
drivers/*.py                   ├── sim-specific tools (12 total)
    │                          └── drivers/*.py (_physics injected)
    ▼
SO-100 real hardware
(Feetech STS3215 via serial)
```

nanobot 启动时根据 `~/.nanobot/config.json` 中的 `mcp_servers` 配置，spawn 两个子进程：
- `robot-bridge` — 使用 lerobot 环境的 Python 解释器
- `sim-bridge` — 使用 nanobot-dev 环境的 Python 解释器

每个 bridge 暴露一组 MCP tools，nanobot 自动发现并注册。

### 2.3 config.json 配置

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

**关键：必须用 Python 解释器的绝对路径**，不能用 `conda run`。原因见下文"踩坑记录"。

---

## 3. Bridge 内部架构

### 3.1 代码结构（monorepo）

```
nanobot-bridge/
├── bridge_core/            # 共享组件
│   ├── driver_loader.py    # 动态 driver 导入（importlib）
│   ├── task_manager.py     # 后台 asyncio 任务生命周期
│   └── sandbox.py          # exec_in_env 代码沙箱
├── robot_bridge/           # 真机 MCP 服务器（6 tools）
│   └── server.py
├── sim_bridge/             # 仿真 MCP 服务器（12 tools）
│   ├── server.py
│   └── physics.py          # PyBullet 封装
├── examples/drivers/       # 参考 driver
│   ├── so100_real.py
│   └── so100_sim.py
└── tests/                  # 46 tests, 3 seconds
    ├── test_core/          # 17 tests
    ├── test_robot/         # 14 tests (含 benchmark)
    └── test_sim/           # 15 tests
```

### 3.2 共享核心：bridge_core

**DriverLoader** — 动态导入 driver 文件：

```python
class DriverLoader:
    def load(self, name, reload=False):
        path = self.drivers_dir / f"{name}.py"
        spec = importlib.util.spec_from_file_location(f"_nanobot_driver_{name}", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        instance = module.Driver()
        self.loaded[name] = instance
        return instance
```

核心思路：用 `importlib` 从 `~/.nanobot/workspace/drivers/{name}.py` 动态加载。支持 reload（agent 修改 driver 后重新加载）。每个 driver 文件必须导出一个 `Driver` class。

**TaskManager** — 流式任务管理：

```python
class TaskManager:
    def start(self, coro_func) -> str:
        task_id = f"task_{uuid4().hex[:8]}"
        # 创建 asyncio task，注入 _report_status 回调
        asyncio_task = asyncio.get_event_loop().create_task(_run())
        return task_id

    def get_status(self, task_id) -> dict:
        # 返回 state, progress, result, error, elapsed_s

    def stop(self, task_id) -> dict:
        entry["_asyncio_task"].cancel()
```

LLM 调用 streaming method 时：
1. `call(driver, method)` → 返回 `{"task_id": "task_xxx"}`
2. LLM 可以随时 `task_status(task_id)` 查看进度
3. LLM 可以 `stop_task(task_id)` 终止任务

**LLM 永远不在实时控制环路内。** 50Hz/100Hz 的循环在 bridge 进程里跑，LLM 只管启动和监控。

**sandbox (exec_in_env)** — 在 bridge 环境中执行任意 Python 代码：

```python
async def exec_in_env(code, timeout=30):
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-c", code,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    return {"stdout": stdout.decode(), "stderr": stderr.decode(), "returncode": proc.returncode}
```

这让 LLM 可以在 bridge 的 conda 环境中探索——比如试试能不能 import lerobot，检查 GPU 状态等。对于写新 driver 之前的探索阶段非常有用。

### 3.3 Robot Bridge：6 个 MCP Tools

| Tool | 用途 |
|---|---|
| `probe_env` | 查看 Python 版本、已装包、可用 driver |
| `exec_in_env` | 在 bridge 环境执行 Python 代码 |
| `load_driver` | 从 workspace 加载 driver |
| `call` | 调用 driver 方法（instant 或 streaming） |
| `task_status` | 查询后台任务进度 |
| `stop_task` | 终止后台任务 |

### 3.4 Sim Bridge：12 个 MCP Tools

继承 robot bridge 全部 6 个 tool，额外加 6 个仿真专用 tool：

| Tool | 用途 |
|---|---|
| `sim_load_robot` | 加载 URDF 到 PyBullet |
| `sim_get_joints` | 读取仿真关节位置 |
| `sim_set_joints` | 设置关节目标并步进 |
| `sim_step` | 步进物理引擎（默认 240 步 = 1 秒） |
| `sim_reset` | 重置整个仿真 |
| `sim_log` | 读取 PyBullet 日志（debug 输出） |

**sim-bridge 的特殊设计：_physics 注入。** 当 driver 被 sim-bridge 加载时，如果 driver 有 `_physics` 属性，sim-bridge 会自动注入 `PhysicsEngine` 实例：

```python
# sim_bridge/server.py 中的 load_driver
if hasattr(driver, "_physics"):
    driver._physics = engine._ensure()  # 注入物理引擎
```

这样 driver 可以直接调用 `self._physics.load_urdf()`、`self._physics.step()` 等，不需要自己管理 PyBullet 连接。

---

## 4. Driver Protocol

Driver 是纯 Python 文件，存放在 `~/.nanobot/workspace/drivers/`。这个路径是 agent 的工作区，LLM 可以直接读写文件。

### 4.1 Driver 协议规范

每个 driver 文件必须导出一个 `Driver` class，包含：

```python
class Driver:
    name = "my_robot"           # 唯一标识
    description = "描述信息"     # LLM 会看到这个

    methods = {
        "connect": {
            "type": "instant",           # instant 或 streaming
            "description": "连接硬件",
            "params": {"port": "str"},   # 参数说明
        },
        "run_policy": {
            "type": "streaming",
            "description": "运行策略推理",
            "params": {"model": "str", "episodes": "int"},
        },
    }

    async def connect(self, port="/dev/ttyACM0"):
        # instant method: 直接返回结果
        return {"status": "connected"}

    async def run_policy(self, model, episodes=1, *, _report_status=None):
        # streaming method: 长时间运行，通过 _report_status 报告进度
        for ep in range(episodes):
            _report_status({"episode": ep + 1, "total": episodes})
            await asyncio.sleep(1)
        return {"status": "done"}
```

### 4.2 两种方法类型

**Instant** — 调用后立即返回结果。适用于：
- 连接/断开硬件
- 读取关节位置
- 发送单次动作
- 查询状态

**Streaming** — 调用后返回 `task_id`，在后台 asyncio task 中运行。适用于：
- 策略推理循环（50Hz）
- 遥操作（100Hz）
- 轨迹执行
- 数据采集

### 4.3 参考实现

**so100_real.py** — 真机 driver（通过 lerobot）：

```python
from lerobot.robots.so100_follower import SO100Follower, SO100FollowerConfig

class Driver:
    name = "so100_real"
    # methods: connect, get_joints, send_action, get_state, disconnect

    async def connect(self, port="/dev/ttyACM0"):
        config = SO100FollowerConfig(port=port, use_degrees=True)
        self._robot = SO100Follower(config)
        self._robot.connect(calibrate=True)
        return {"status": "connected", ...}
```

**so100_sim.py** — 仿真 driver（通过注入的 _physics）：

```python
class Driver:
    name = "so100_sim"
    # methods: connect, get_joints, send_action, reset, step, run_trajectory(streaming)

    def __init__(self):
        self._physics = None  # sim-bridge 自动注入
        self._robot_id = None

    async def connect(self, urdf_path=None):
        self._robot_id = self._physics.load_urdf(path)

    async def run_trajectory(self, waypoints, hz=50, *, _report_status=None):
        # streaming: 50Hz 控制循环
        for i, wp in enumerate(waypoints):
            self._physics.set_joint_positions(self._robot_id, wp)
            self._physics.step(steps=steps_per_tick)
            _report_status({"waypoint": i + 1, "total": len(waypoints)})
            await asyncio.sleep(1.0 / hz)
```

### 4.4 Agent 如何使用 Driver（典型工作流）

```
1. LLM: probe_env()
   → 看到有哪些 driver 文件、已装什么包

2. LLM: load_driver(name="so100_sim")
   → driver 被加载，返回可用方法列表

3. LLM: call(driver="so100_sim", method="connect", params={...})
   → 连接到仿真中的机器人

4. LLM: call(driver="so100_sim", method="get_joints")
   → 读取关节位置

5. LLM: call(driver="so100_sim", method="run_trajectory", params={"waypoints": [...]})
   → 返回 {"task_id": "task_abc123"}

6. LLM: task_status(task_id="task_abc123")
   → {"state": "running", "progress": {"waypoint": 5, "total": 10}}

7. LLM: task_status(task_id="task_abc123")
   → {"state": "completed", "result": {"final_joints": {...}}}
```

**关键：Agent 可以自己写新 driver。** 如果遇到不支持的硬件，LLM 可以：
1. `exec_in_env` 探索环境中有什么库
2. 用 `write_file` 写一个新 driver 到 `~/.nanobot/workspace/drivers/`
3. `load_driver` 加载
4. 测试、修改、`load_driver(reload=True)` 重新加载

---

## 5. 仿真引擎（PyBullet）

### 5.1 PhysicsEngine 封装

`sim_bridge/physics.py` 封装了 PyBullet 的常用操作：

```python
class PhysicsEngine:
    def __init__(self, headless=True, gravity=-9.81):
        mode = p.DIRECT if headless else p.GUI
        self.physics_client = p.connect(mode)
        p.setGravity(0, 0, gravity)

    def load_urdf(self, urdf_path, base_position=None, use_fixed_base=True) -> int
    def get_robot_info(self, robot_id) -> dict
    def get_joint_positions(self, robot_id) -> dict[str, float]
    def set_joint_positions(self, robot_id, positions: dict[str, float])
    def step(self, steps=1)
    def reset()
    def close()
```

加载 URDF 后自动扫描所有非固定关节，建立 `joint_name -> joint_index` 映射。后续操作都用关节名称而不是索引。

### 5.2 懒加载（LazyEngine）

问题：如果 nanobot 启动时就初始化 PhysicsEngine，GUI 窗口会立即弹出——即使用户还没用到仿真。

解决：`_LazyEngine` 代理类，第一次访问时才创建真正的 PhysicsEngine：

```python
class _LazyEngine:
    def __init__(self, headless=True):
        self._headless = headless
        self._engine = None

    def _ensure(self) -> PhysicsEngine:
        if self._engine is None:
            self._engine = PhysicsEngine(headless=self._headless)
            self._engine.load_plane()
        return self._engine

    def __getattr__(self, name):
        return getattr(self._ensure(), name)
```

通过 `__getattr__`，所有对 engine 的属性访问都会先触发 `_ensure()`。对外接口完全透明。

---

## 6. 踩坑记录与解决方案

### 6.1 conda run 不能用于 MCP

**问题：** 最初尝试用 `conda run -n lerobot python -m robot_bridge.server`，但 `conda run` 不能正确 pipe stdin/stdout，进程直接退出。

**解决：** 用 conda 环境中 Python 解释器的绝对路径：
```
/home/user/miniconda3/envs/lerobot/bin/python -m robot_bridge.server
```

### 6.2 PyBullet 的 stdout 污染

**问题：** PyBullet 是 C 库，GUI 模式下会直接往 fd 1（stdout）写 debug 信息：
```
startThreads creating 1 threads.
requestBodyInfo id=0
```
这些文本混入 MCP 的 JSON-RPC 流，导致 JSON 解析失败。

**解决（分两层）：**

**第一层：C 函数调用时的临时重定向**

```python
@contextmanager
def _redirect_stdout_to_log():
    log_path = _ensure_log_file()
    old_fd = os.dup(1)                    # 保存原始 fd 1
    log_fd = os.open(str(log_path), ...)  # 打开日志文件
    os.dup2(log_fd, 1)                    # fd 1 -> 日志
    os.close(log_fd)
    try:
        yield
    finally:
        os.dup2(old_fd, 1)               # 恢复 fd 1
        os.close(old_fd)
```

所有 PyBullet 调用都包在 `with _redirect_stdout_to_log():` 里。

**第二层：GUI 线程的永久重定向**

问题：PyBullet GUI 会启动后台线程，在 context manager 退出后继续往 fd 1 写东西。

解决：在 `main()` 中做永久的 fd 级别重定向：

```python
# 1. 保存真正的 fd 1（给 MCP JSON-RPC 用）
real_stdout_fd = os.dup(1)

# 2. fd 1 永久指向日志文件（PyBullet C 代码写这里）
log_fd = os.open(str(log_path), os.O_WRONLY | os.O_CREAT | os.O_APPEND)
os.dup2(log_fd, 1)
os.close(log_fd)

# 3. Python 的 sys.stdout 指向保存的真实 fd（MCP 用这个）
sys.stdout = io.TextIOWrapper(
    io.FileIO(real_stdout_fd, "w", closefd=False),
    line_buffering=True,
)
```

效果：
- PyBullet C 代码写 fd 1 → 进入日志文件
- Python/MCP 写 sys.stdout → 进入真实 stdout → nanobot 收到干净的 JSON-RPC
- Agent 可以通过 `sim_log` tool 查看日志

### 6.3 DISPLAY 环境变量不传递

**问题：** MCP SDK 的 `get_default_environment()` 只传递 HOME、PATH、SHELL 等基本变量，不包含 DISPLAY。PyBullet GUI 模式需要 DISPLAY 才能连接 X11。

**解决：** 修改了 nanobot 的 `nanobot/agent/tools/mcp.py`，让 MCP 客户端传递显示相关的环境变量：

```python
if transport_type == "stdio":
    _passthrough = ("DISPLAY", "WAYLAND_DISPLAY", "XDG_RUNTIME_DIR",
                    "XAUTHORITY", "DBUS_SESSION_BUS_ADDRESS")
    _env = {k: os.environ[k] for k in _passthrough if k in os.environ}
    if cfg.env:
        _env.update(cfg.env)
    params = StdioServerParameters(command=cfg.command, args=cfg.args, env=_env or None)
```

### 6.4 无 DISPLAY 时 GUI 崩溃

**问题：** `p.connect(p.GUI)` 在没有 DISPLAY 的环境（SSH、headless server）会直接崩溃。

**解决：** PhysicsEngine 构造函数中检测：
```python
if not headless and not os.environ.get("DISPLAY"):
    headless = True  # 自动降级到 DIRECT 模式
```

### 6.5 hatchling 打包找不到 package

**问题：** `pip install -e .` 报错找不到 module。

**解决：** `pyproject.toml` 中显式声明 packages：
```toml
[tool.hatch.build.targets.wheel]
packages = ["bridge_core", "robot_bridge", "sim_bridge"]
```

### 6.6 FastMCP call_tool 返回类型

**问题：** `server.call_tool()` 返回的是 `(content_list, is_error)` tuple，不是直接的 content。测试代码需要解包。

**解决：**
```python
def _parse(result) -> dict:
    content_list, _is_error = result
    return json.loads(content_list[0].text)
```

---

## 7. Always-On Skill：让 LLM 自带机器人知识

为了让 LLM 一启动就知道怎么用 bridge，我们写了一个 always-on skill 文件：

`~/.nanobot/workspace/skills/robot/SKILL.md`

```yaml
---
name: robot
description: Control robots and simulations via MCP bridge tools.
always: true
---
```

`always: true` 表示这个 skill 会在每次对话开始时自动加载到 LLM context。内容包括：
- 两个 bridge 的用途说明
- 探索新机器人的标准流程
- 日常使用的 tool 调用模式
- streaming task 的使用模式
- driver 协议规范

这样 LLM 不需要"学习"如何使用 bridge，每次对话都自带这些知识。

---

## 8. Benchmark 结果

| 操作 | 平均延迟 |
|---|---|
| Driver method call (instant) | ~0.01ms |
| exec_in_env (subprocess) | ~9.33ms |
| Streaming task startup | ~0.07ms |

instant method 调用几乎无开销，因为只是 Python 函数调用。exec_in_env 需要 spawn subprocess，约 10ms。streaming 只是创建 asyncio task，开销极小。

---

## 9. 已知问题与缺陷

1. **硬编码路径** — config.json 中的 Python 路径是绝对路径，换机器就要改。Driver 的 URDF 路径也是硬编码。
2. **无认证机制** — `exec_in_env` 可以执行任意代码。本地开发没问题，部署到共享环境有安全风险。
3. **PhysicsEngine 同步阻塞** — `step()` 是同步调用，会阻塞 asyncio event loop。长时间 rollout 期间其他 tool 调不通。
4. **无错误恢复** — 硬件断开直接抛异常，没有重连逻辑或安全停止机制。
5. **Streaming 无反压/命令通道** — `_report_status` 是单向的（task -> LLM），没有 LLM -> task 的命令通道。比如不能中途改参数。
6. **工具名称冗余** — MCP server 名 `sim` + tool 名 `sim_load_robot` -> nanobot 注册为 `mcp_sim_sim_load_robot`，双重 `sim_` 很丑。
7. **无 driver 依赖声明** — Driver 不能声明自己需要哪些 pip 包。
8. **base tools 代码重复** — robot-bridge 和 sim-bridge 的 6 个 base tools 实现完全一样但各自写了一份（已通过共享 bridge_core 减轻，但 server.py 中的 tool 定义仍有重复）。

---

## 10. 下一步 Roadmap

### 近期
- [ ] 真机测试 — SO-100 端到端验证
- [ ] 重命名 sim tools，消除 `sim_sim_` 前缀
- [ ] `nanobot init-robot` CLI 命令 — 一键创建 conda env、安装 bridge、写 config

### 中期
- [ ] Camera/vision tools（仿真截图 + 真机摄像头）
- [ ] Policy inference driver 模板（ACT、Diffusion Policy）
- [ ] Teleoperation driver（leader-follower 100Hz）
- [ ] Data collection driver（录制 HDF5/LeRobot 格式）
- [ ] PhysicsEngine 用线程池避免阻塞 event loop

### 远期
- [ ] Docker 化部署（bridge 跑在容器里）
- [ ] 多机器人管理
- [ ] 健康监控和自动重连
- [ ] 物体生成（仿真 manipulation task）
- [ ] Domain randomization（sim-to-real）
- [ ] Streaming 双向通道（LLM 可以给运行中的 task 发命令）

---

## 11. 如何快速上手

### 环境准备

```bash
# 解压
unzip nanobot-bridge.zip

# 仿真环境（最简）
conda activate nanobot-dev  # 或任何 Python >= 3.10
cd nanobot-bridge
pip install -e ".[sim,dev]"

# 跑测试
pytest tests/ -v
# 预期结果: 36 passed, 10 skipped (URDF 相关测试跳过)

# 如果有 SO-100 URDF 文件，可以跑全部测试：
SO100_URDF_PATH=/path/to/so100.urdf pytest tests/ -v
# 预期结果: 46 passed
```

### 在 nanobot 中使用

1. 把 nanobot-bridge 装到对应 conda 环境
2. 编辑 `~/.nanobot/config.json` 添加 mcp_servers（见第 2.3 节）
3. 启动 nanobot，应该能看到 bridge 的 tools 被注册
4. LLM 就可以用了

---

## 12. 关键文件索引

| 文件 | 作用 |
|---|---|
| `bridge_core/driver_loader.py` | 动态 driver 导入 |
| `bridge_core/task_manager.py` | 后台任务生命周期管理 |
| `bridge_core/sandbox.py` | exec_in_env 实现 |
| `robot_bridge/server.py` | 真机 MCP 服务器（6 tools） |
| `sim_bridge/server.py` | 仿真 MCP 服务器（12 tools + LazyEngine） |
| `sim_bridge/physics.py` | PyBullet 封装 + stdout 重定向 |
| `examples/drivers/so100_real.py` | SO-100 真机 driver |
| `examples/drivers/so100_sim.py` | SO-100 仿真 driver |
| `~/.nanobot/config.json` | nanobot MCP 服务器配置 |
| `~/.nanobot/workspace/drivers/` | Agent 工作区 driver 目录 |
| `~/.nanobot/workspace/skills/robot/SKILL.md` | Always-on LLM skill |
| `nanobot/agent/tools/mcp.py` | nanobot 端 DISPLAY 传递 patch |
