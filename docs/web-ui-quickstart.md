# RoboClaw Web UI 快速开始

## 安装

### 1. 安装 Python 依赖（包含 web 支持）

```bash
uv venv
uv sync --extra dev --extra web
```

`run.py` and the Web chat UI do not require the embodied learning stack. Only
add `--extra learning` when you also want LeRobot-backed collection or training
features:

```bash
uv sync --extra dev --extra web --extra learning
```

### 2. 安装前端依赖

```bash
cd roboclaw-web
npm install
```

## 开发模式

### 一键启动

```bash
uv run run.py
```

这个入口会：

- 通过 `uv run --extra web --locked roboclaw web start` 启动后端
- 在前端依赖缺失时自动执行 `npm install`
- 启动 `roboclaw-web` 前端开发服务器

默认地址：

- 前端: `http://localhost:5173`
- 后端: `http://localhost:8765`

### 启动后端（Terminal 1）

```bash
uv run roboclaw web start
```

后端将在 http://localhost:8765 启动

### 启动前端（Terminal 2）

```bash
cd roboclaw-web
npm run dev
```

前端将在 http://localhost:5173 启动

### 访问

打开浏览器访问 http://localhost:5173

## 生产模式

### 构建前端

```bash
cd roboclaw-web
npm run build
```

### 启动服务器

```bash
roboclaw web start
```

## 功能状态

- ✅ **对话界面**: 可用 - 与 RoboClaw agent 实时对话
- 🚧 **机器人监控**: 开发中 - 实时状态和传感器数据
- 🚧 **控制面板**: 开发中 - 遥操作界面
- 🚧 **数据集工作台**: 计划中 - Nexla 集成

## 架构

```
┌─────────────────────────────────────┐
│   React Frontend (Port 5173)       │
│   - Chat UI                         │
│   - Monitor (coming soon)           │
│   - Control (coming soon)           │
└──────────────┬──────────────────────┘
               │ WebSocket
┌──────────────▼──────────────────────┐
│   FastAPI Backend (Port 8765)      │
│   - WebSocket server                │
│   - Message routing                 │
└──────────────┬──────────────────────┘
               │ Message Bus
┌──────────────▼──────────────────────┐
│   RoboClaw Agent Runtime            │
└─────────────────────────────────────┘
```

## 故障排除

### WebSocket 连接失败

确保后端服务器正在运行：
```bash
uv run roboclaw web start
```

### 前端构建失败

清理并重新安装依赖：
```bash
cd roboclaw-web
rm -rf node_modules package-lock.json
npm install
```

### 端口冲突

修改端口：
- 后端：编辑 `server.py` 中的 `port` 参数
- 前端：编辑 `vite.config.ts` 中的 `server.port`

## 下一步

- [ ] 实现机器人状态监控
- [ ] 实现遥操作控制界面
- [ ] 集成 Nexla 数据集工作台
- [ ] 添加认证和授权
- [ ] 性能优化和测试
