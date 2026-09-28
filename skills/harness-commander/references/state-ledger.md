# 状态总账（State Ledger）

**核心问题**：复杂任务涉及多子任务、多 Agent、多轮交互。没有单一事实源，不同组件对"现在到哪了"的理解会悄悄分叉，最终导致遗漏、重复或冲突。

## 一、什么是状态总账

`HARNESS_STATE.json` 是伴随任务全生命周期的**单一事实源**（Single Source of Truth）。它记录的不是"怎么做"而是"现在是什么状态"。它和子 Agent 状态文件协同：总账管全局，状态文件管个体。

## 二、文件结构

```json
{
  "task_id": "harness-20260809-t001",
  "goal": "重构用户认证模块，从 Session 迁移到 JWT",
  "acceptance": {
    "complete": "所有 AUTH 端点返回 JWT；旧 Session 代码已清除；3 个集成测试通过",
    "fail": "任何端点仍依赖 Session；测试覆盖率下降；JWT secret 未配置"
  },
  "overall_status": "planning|executing|verifying|diagnosing|delivering|reflecting|done|paused",
  "phases": [
    {
      "phase": "understand",
      "status": "done",
      "output": ".harness/artifacts/understand.md"
    },
    {
      "phase": "scope",
      "status": "done",
      "output": ".harness/artifacts/scope.md"
    },
    {
      "phase": "execute",
      "status": "running",
      "output": null
    }
  ],
  "subtasks": [
    {
      "run_id": "t001-search-auth",
      "label": "搜索仓库内 AUTH 相关文件",
      "worker": "agent-a",
      "status": "done",
      "evidence_level": "Wired",
      "result_summary": "发现 3 个 AUTH 相关文件",
      "started_at": "2026-08-09T14:28:00Z",
      "updated_at": "2026-08-09T14:35:00Z"
    },
    {
      "run_id": "t001-migrate-endpoints",
      "label": "迁移 3 个 AUTH 端点到 JWT",
      "worker": "agent-b",
      "status": "running",
      "evidence_level": null,
      "result_summary": null,
      "started_at": "2026-08-09T14:36:00Z",
      "updated_at": "2026-08-09T14:40:00Z"
    }
  ],
  "blockers": [],
  "owner": "Master Agent",
  "created_at": "2026-08-09T14:25:00Z",
  "updated_at": "2026-08-09T14:40:00Z"
}
```

### 字段说明

| 字段 | 类型 | 说明 |
|---|---|---|
| `task_id` | string | 唯一标识，格式 `harness-{date}-t{序号}` |
| `goal` | string | 一句话目标 |
| `acceptance.complete` | string | 明确完成判据 |
| `acceptance.fail` | string | 明确不合格判据 |
| `overall_status` | string | 八态：planning/executing/verifying/diagnosing/delivering/reflecting/done/paused |
| `phases[]` | array | 七步闭环每步的状态和产出物路径 |
| `subtasks[]` | array | 子任务列表 |
| `blockers[]` | array | 阻塞项列表 |
| `owner` | string | 负责人/Agent |
| `created_at/updated_at` | ISO8601 | 时间戳 |

### subtask 字段

| 字段 | 说明 |
|---|---|
| `run_id` | 对应 worker-monitor 中的 run_id |
| `label` | 人类可读任务名 |
| `worker` | 执行者标识 |
| `status` | pending/starting/running/blocked/error/done |
| `evidence_level` | 完成后标记：Present/Wired/Exercised/Outcome/Insufficient |
| `result_summary` | 一句话结果 |
| `started_at/updated_at` | 时间戳 |

## 三、好处

### 3.1 中断恢复

对话中断或被新消息打断后，只需读 `HARNESS_STATE.json` 就知道：
- 当前在哪个阶段
- 哪些子任务已完成（及证据等级）
- 哪些子任务还在跑
- 是否有阻塞项

无需重新梳理整个对话历史。

### 3.2 多任务全局视图

如果同时有多个 harness 任务在跑（极少但可能），`HARNESS_STATE.json` 是最小的"任务仪表盘"。一眼可见所有任务状态。

### 3.3 沉淀有据

任务完成后，`HARNESS_STATE.json` 就是完整的执行记录。Loop Discovery 评审时可直接使用其中的子任务、失败记录、耗时等作为决策数据。

## 四、操作时机

| 时机 | 操作 |
|---|---|
| 第一步（理解）完成时 | 创建 `HARNESS_STATE.json`，填入 goal/acceptance/overall_status=planning |
| 每步开始时 | 更新 phases 中对应项 status |
| 子 Agent 启动时 | subtasks 新增一行 status=starting |
| 子 Agent 完成时 | 更新 status/evidence_level/result_summary/updated_at |
| 遇到阻塞时 | blockers 新增项 |
| 任务整体完成 | overall_status=done |

## 五、与 worker-monitor 分工

| 维度 | 状态总账 | Worker 状态文件 |
|---|---|---|
| 范围 | 全任务全局 | 单个子 Agent |
| 内容 | 目标/验收/阶段/子任务/阻塞 | 进度/心跳/错误/question |
| 更新者 | 主指挥 | 子 Agent 自身 |
| 更新频率 | 每阶段切换时 | 每子步骤或每 3 分钟 |
| 文件位置 | `.harness/HARNESS_STATE.json` | `.harness/workers/{run_id}.json` |

> **一句话原则**：状态总账 = 任务的单一事实源。任何时候想知道"现在到哪了"，只读这一个文件，不看对话历史。