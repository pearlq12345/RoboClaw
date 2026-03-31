# RoboClaw Web UI

RoboClaw 的 Web 用户界面，提供可视化的机器人控制、监控和数据集管理能力。

## 功能

- **对话界面**: 与 RoboClaw agent 实时对话
- **机器人监控**: 实时状态显示和传感器数据可视化（即将推出）
- **控制面板**: 遥操作和控制界面（即将推出）
- **数据集工作台**: 数据集管理和标注（即将推出）

## 开发

### 安装依赖

```bash
npm install
```

### 启动开发服务器

```bash
npm run dev
```

访问 http://localhost:5173

### 构建生产版本

```bash
npm run build
```

## 技术栈

- React 18
- TypeScript
- Vite
- Tailwind CSS
- Zustand (状态管理)
- React Router
- WebSocket (实时通信)

## 架构

```
src/
├── features/          # 功能模块
│   ├── chat/         # 对话界面
│   ├── control/      # 控制面板
│   ├── monitor/      # 监控面板
│   └── workbench/    # 数据集工作台
├── shared/           # 共享代码
│   ├── components/   # 共享组件
│   ├── hooks/        # 自定义 hooks
│   ├── api/          # API 客户端
│   └── utils/        # 工具函数
└── assets/           # 静态资源
```

## 与后端通信

Web UI 通过 WebSocket 与 RoboClaw 后端通信：

- WebSocket 端点: `ws://localhost:8765/ws`
- REST API: `http://localhost:8765/api/*`

确保后端 Web Channel 已启动：

```bash
roboclaw web start
```
