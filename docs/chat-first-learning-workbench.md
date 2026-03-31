# RoboClaw Chat-First Learning Workbench Design

## 1. 背景

RoboClaw 当前已经有三个和 Web UI 相关的事实：

- 根架构文档把 `Web UI` 放在 `Interface` 层，与 CLI、Discord、Telegram、WeChat 并列。
- 仓库里已经存在 `roboclaw-web/`，并且前端路由已经预留了 `/chat`、`/monitor`、`/control`、`/workbench` 四个入口。
- 仓库里已经存在 `roboclaw/channels/web.py`，说明项目方向上已经认可“Web 是正式入口”。

与此同时，Nexla 对 RoboClaw 的定位已经明确：

- Nexla 不是新的总入口。
- Nexla 是给 RoboClaw 的 `Learning` 模块提供支持的工作台。
- 其核心链路是：

```text
Data Collection
  -> ProSemA workflow
  -> Train + Deploy
```

因此，Web UI 的合理目标不是“把 Nexla 做成一个独立大应用并行存在”，也不是“把 ProSemA 退化成一个 prompt-only skill”，而是：

```text
Chat-first Web UI
  -> 对话入口和控制台
  -> 调用 ProSemA skill
  -> ProSemA skill 调用稳定的 workflow tool/service
  -> Learning 模块执行数据与训练流程
```

## 2. 设计目标

本设计要实现三件事：

1. 给 RoboClaw 提供一个真正可用的 Web 对话入口。
2. 让 ProSemA workflow 能从对话入口被调用。
3. 在保持 chat-first 的前提下，为必须结构化交互的学习环节保留工作台面板。

## 3. 非目标

本设计当前不追求：

- 把整个 Learning 工作流都塞进聊天消息里完成
- 用 prompt 替代结构化 workflow 状态
- 让 Web UI 成为一套绕开 `MessageBus` 和 `AgentLoop` 的第二运行时
- 立即构建完整大而全的 Nexla 独立工作台

## 4. 当前状态与问题

### 4.1 当前已有基础

- `roboclaw-web/src/App.tsx`
  - 已经定义了 `/chat`、`/control`、`/monitor`、`/workbench` 路由。
- `roboclaw-web/src/features/workbench/WorkbenchPage.tsx`
  - 已经预留了工作台页面，但当前仍是占位。
- `docs/web-ui-quickstart.md`
  - 已经把“对话界面 + 机器人监控 + 控制面板 + 数据集工作台”定义成目标产品方向。

### 4.2 当前实现缺口

当前 `roboclaw/channels/web.py` 更像早期原型，不应直接视为最终实现，主要原因：

- 它没有严格对齐当前 `BaseChannel` / `MessageBus` / `InboundMessage` 契约。
- 它混合了 transport、API、连接管理、消息路由，边界过粗。
- 它适合作为参考原型，不适合作为 Learning Workbench 的长期后端形态。

因此，现有 Web 相关代码应该被视为：

- 前端外壳已有
- Web channel 方向已定
- 但后端接法和 Learning 工作台分层仍需要重构

## 5. 核心结论

### 5.1 Web UI 应该是两个层次，不是一个东西

RoboClaw 的 Web UI 应拆成两个逻辑层：

1. `Chat Shell`
   - 统一对话窗口
   - 用户的主入口
   - 发起任务、追踪状态、解释结果

2. `Learning Workbench`
   - 服务于 Learning 模块
   - 包含 ProSemA workflow 的结构化交互
   - 在需要时以页面或侧边面板形式打开

这两个层次可以共存于同一个 `roboclaw-web` 前端里，但职责不同。

### 5.2 ProSemA 应该是 “skill + tool/service”，不是 prompt-only skill

推荐关系如下：

```text
User message
  -> Agent
  -> ProSemA skill
  -> learning_workbench tool
  -> workflow service
  -> Learning execution / persistence
```

其中：

- `skill` 负责自然语言理解、意图路由和步骤编排
- `tool` 负责结构化 action 调用
- `service` 负责稳定、可测试、可恢复的 workflow 逻辑

如果只有 `skill` 而没有 `tool/service`，后续会出现：

- 状态不可恢复
- 结果不可复算
- 标注与聚类难以审计
- 前后端耦合到 prompt 语义

## 6. 总体架构

推荐使用下面这条主链路：

```text
Browser
  -> Chat Shell
  -> Web Chat API / WebSocket
  -> Agent runtime
  -> ProSemA skill
  -> learning_workbench tool
  -> Learning workflow service
  -> dataset / annotation / prototype / semantic / train
```

当 workflow 进入需要结构化交互的步骤时：

```text
Agent response
  -> 前端识别 structured UI intent
  -> 打开 Workbench panel / page
  -> 用户进行视频审阅 / prototype 选择 / annotation 编辑
  -> Workbench API
  -> Learning workflow service
```

## 7. 三层设计

### 7.1 第一层：Chat Shell

职责：

- 统一入口
- 发送消息给 agent
- 渲染回复、progress、tool hint
- 展示 session 列表与会话历史
- 在需要时跳转或弹出 Learning Workbench

前端放置位置：

- 继续使用 `roboclaw-web/`

建议页面结构：

- `/chat`
  - 默认入口
- `/workbench`
  - Learning Workbench 容器
- `/workbench/datasets/:datasetId`
  - dataset 工作台
- `/workbench/workflows/:workflowId`
  - 当前 workflow 详情

### 7.2 第二层：ProSemA Skill + Tool

职责：

- 把自然语言转成结构化 workflow action
- 管理“当前在第几步”
- 输出下一步建议
- 在需要人工确认时，引导用户打开结构化面板

这里必须明确：

- ProSemA skill 不自己保存复杂业务状态
- ProSemA skill 不直接实现聚类、标注传播、质量过滤
- 它只编排已有工具和服务

推荐新增：

- `roboclaw/agent/tools/learning_workbench.py`
- `roboclaw/skills/prosema/SKILL.md`

### 7.3 第三层：Learning Workflow Service

职责：

- 保存 workflow 状态
- 执行 quality filtering
- 执行 prototype discovery
- 保存 annotation
- 执行 semantic propagation
- 汇总 final result
- 触发 train / deploy

推荐放置位置：

- `roboclaw/learning/`

建议子目录：

```text
roboclaw/learning/
├── workflow/
│   ├── quality.py
│   ├── prototypes.py
│   ├── annotation.py
│   ├── semantic.py
│   └── final_result.py
├── services/
├── storage/
└── schemas/
```

## 8. 哪些步骤留在聊天里，哪些步骤弹工作台

### 8.1 保留在聊天里的步骤

这些操作适合在对话窗口完成：

- 选择 dataset
- 查看 dataset 摘要
- 启动 workflow
- 调整 workflow 参数
- 运行 quality filtering
- 运行 prototype discovery
- 查询 workflow 状态
- 查询训练状态
- 请求系统解释结果
- 请求系统给出下一步建议

### 8.2 必须弹出结构化工作台的步骤

这些操作不应只靠聊天完成：

- 视频逐帧审阅
- prototype 选择对比
- annotation span 编辑
- 时间轴精修
- 语义传播结果对比验证
- final result 的可视化审查

原则：

- chat 负责“发起、控制、解释”
- workbench 负责“编辑、审阅、验证”

## 9. 建议的工具接口

推荐把 ProSemA 相关能力收敛为一个工具组，而不是很多松散工具。

工具名建议：

- `learning_workbench`

建议 action：

- `list_datasets`
- `open_dataset`
- `create_workflow`
- `get_workflow_status`
- `run_quality_filter`
- `run_prototype_discovery`
- `list_prototypes`
- `save_annotation`
- `get_annotation`
- `get_annotation_suggestions`
- `run_semantic_propagation`
- `get_final_result`
- `start_train`
- `get_train_status`
- `open_workbench`

其中：

- `open_workbench` 不直接做业务，只返回前端可跳转的 structured payload
- `save_annotation`、`get_annotation` 等 action 必须走稳定存储，而不是只存在 session 里

## 10. 建议的 Web API

### 10.1 Chat API

- `GET /api/health`
- `GET /api/chat/sessions`
- `GET /api/chat/sessions/{session_id}`
- `POST /api/chat/sessions/{session_id}/messages`
- `WS /ws/chat/{session_id}`

### 10.2 Learning Workbench API

- `GET /api/learning/datasets`
- `GET /api/learning/datasets/{dataset_id}`
- `POST /api/learning/workflows`
- `GET /api/learning/workflows/{workflow_id}`
- `POST /api/learning/workflows/{workflow_id}/quality-run`
- `POST /api/learning/workflows/{workflow_id}/prototype-run`
- `GET /api/learning/workflows/{workflow_id}/prototypes`
- `GET /api/learning/workflows/{workflow_id}/annotations`
- `POST /api/learning/workflows/{workflow_id}/annotations`
- `POST /api/learning/workflows/{workflow_id}/semantic-run`
- `GET /api/learning/workflows/{workflow_id}/final-result`
- `POST /api/learning/workflows/{workflow_id}/train`
- `GET /api/learning/workflows/{workflow_id}/train-status`

## 11. 目录落点建议

### 11.1 继续保留的目录

- `roboclaw-web/`
  - 前端工作区
- `roboclaw/agent/`
  - 对话编排
- `roboclaw/channels/`
  - chat transport
- `roboclaw/embodied/learning/`
  - 训练与部署相关基础能力

### 11.2 建议新增的目录

```text
roboclaw/
├── learning/
│   ├── workflow/
│   ├── services/
│   ├── storage/
│   └── schemas/
├── web/
│   ├── app.py
│   ├── routes/
│   │   ├── chat.py
│   │   └── learning.py
│   └── connection_hub.py
└── agent/
    └── tools/
        └── learning_workbench.py
```

## 12. 分阶段落地建议

### Phase 1：先把 Web chat 真正跑通

目标：

- 让 `roboclaw-web` 的 `/chat` 成为可用入口
- Web transport 对齐当前 `MessageBus` / `BaseChannel` / `SessionManager`

交付物：

- 可工作的 Web chat
- session 列表和历史
- progress 渲染
- `/new` `/stop` 支持

### Phase 2：接入 Learning tool，而不是先做完整 workbench

目标：

- 用户可以在聊天里发起 ProSemA workflow
- agent 能结构化调用 `learning_workbench`

交付物：

- 基础 ProSemA tool actions
- workflow 状态查询
- dataset 选择与启动链路

### Phase 3：把 `/workbench` 做成真正的结构化面板

目标：

- 把最不适合聊天的交互移到工作台

首批建议功能：

- 视频预览
- prototype 选择
- annotation 编辑
- semantic result 审阅

### Phase 4：训练与部署闭环

目标：

- 从 workflow 结果直接进入 train / deploy

交付物：

- train status
- deploy trigger
- 从 annotation 到 policy 的闭环导航

## 13. 产品原则

### 13.1 chat-first，而不是 chat-only

默认从聊天开始，但不强迫所有任务都在聊天里做完。

### 13.2 tool-first，而不是 prompt-first

复杂 Learning workflow 的真实执行必须落在 tool/service 上。

### 13.3 workbench 是 Learning 的增强层，不是第二个 RoboClaw

Nexla 作为 Learning Workbench 服务于 RoboClaw，而不是与 RoboClaw 并排竞争总入口。

## 14. 最终结论

最合理的方向是：

- `roboclaw-web` 继续作为前端壳
- 先把 Web chat 入口修到和现有 agent runtime 正确对齐
- 把 ProSemA 作为 `skill + tool/service` 的组合能力接入
- 把复杂标注与审阅环节放到 `/workbench`
- 形成一个 `chat-first, workbench-backed` 的 Learning Web UI

简化成一句话：

```text
用户先打开对话窗口，再由对话窗口驱动 ProSemA workflow；
只有在需要结构化交互时，系统才切换到 Learning Workbench 面板。
```
