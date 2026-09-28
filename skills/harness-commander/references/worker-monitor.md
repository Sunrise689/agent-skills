# 子 Agent 监控（Worker Monitor）

**核心问题**：子 Agent 在后台跑的时候，主指挥怎么知道它是活着、卡了、还是已经死透了？

## 一、状态文件

### 格式（JSON）

每个子 Agent 在启动时创建状态文件 `.harness/workers/{run_id}.json`：

```json
{
  "run_id": "task-001-agent-a",
  "label": "搜索：仓库内 AUTH 相关文件",
  "status": "starting|running|blocked|error|done",
  "step": "2/4",
  "progress": "已扫描 45 个文件，发现 3 个候选",
  "error": null,
  "question": null,
  "heartbeat_at": "2026-08-09T14:30:00Z",
  "lifecycle": {
    "started_at": "2026-08-09T14:28:00Z",
    "duration_seconds": 120,
    "timeout_seconds": 600
  }
}
```

### 字段说明

| 字段 | 说明 |
|---|---|
| `run_id` | 唯一标识，格式：`{task_id}-{agent_role}` |
| `label` | 人类可读的任务标题 |
| `status` | 五态之一 |
| `step` | 当前第几步/总步数 |
| `progress` | 自然语言描述当前进度 |
| `error` | 错误信息，正常时为 null |
| `question` | blocked 时的问题，正常时为 null |
| `heartbeat_at` | ISO8601 时间戳，每次更新时必须刷新 |
| `lifecycle` | 生命周期信息（启动时间、已用时长、超时时间） |

### 五态说明

| 状态 | 含义 | 主指挥应做什么 |
|---|---|---|
| `starting` | 已启动，正在接收上下文 | 等待，≤120s 未转入 running 则视为启动失败 |
| `running` | 正在执行中 | 检查心跳，无异常不干预 |
| `blocked` | 遇到需要主指挥回答的问题 | 读 `question`→回答→更新状态文件→unblock |
| `error` | 遇到错误，无法继续 | 读 `error`→按失败分类处理（见 recovery.md） |
| `done` | 完成，结果已产出 | 收集结果，写回状态总账 |

## 二、心跳机制

### 规则

1. 子 Agent 每完成一个子步骤或至少每 3 分钟刷新 `heartbeat_at`
2. 主指挥每隔一段时间读出状态文件的 `heartbeat_at`
3. **超过 10 分钟未更新** → 判定为卡死/超时/上下文丢失

### 卡死处理

```
检测到 run_id=task-001-agent-a 心跳超时（上次更新 10 分钟前）
  ↓
1. 读状态文件，获取最后进度和可能的错误信息
2. 强制终止该子 Agent
3. 评估已产出物是否有可用部分
4. 决定：重启 vs 换策略 vs 主指挥自己完成 vs 升级用户
```

## 三、上下文卫生规则

子 Agent 运行时上下文管理不当，会导致心跳超时、幻觉、回答质量下降。

### 规则

| 规则 | 原因 | 做法 |
|---|---|---|
| **命令输出 tail-20** | 全量命令输出撑爆上下文 | 长输出只取最后 20 行或 grep 过滤关键词 |
| **spawn 前压缩** | 父会话上下文随轮次膨胀 | 派生子 Agent 前压缩指令到最小必要集合 |
| **必须设超时** | 不限时可能永远等待 | 每个子 Agent 必须设 timeout（默认 600s） |
| **不传无关文件** | 上下文越干净，Agent 越精准 | 只传递该通道需要的文件内容 |

### spawn 压缩清单

派生子 Agent 时，传递的内容应压缩到：
- 任务简报（task-brief.md 规范格式）
- 必要的输入文件内容（非整个仓库）
- 明确的输出格式要求
- timeout 和状态文件路径

不传递：
- 其他子 Agent 的结论
- 主对话的全部历史
- 无关的 reference 文件
- 主指挥的内部思考记录

## 四、blocked 处理流程

子 Agent 的状态文件中 `question` 非 null 时：

```
1. 读 question 内容
2. 主指挥分析问题
3. 如果可以自行回答（纯信息类）→ 直接回答
4. 如果涉及决策（需用户确认）→ 转述给用户
5. 回答后：更新该 Agent 的状态文件，将 status 改回 running，question 清空
6. 如 5 分钟内未收到有效回答 → Agent 视为超时，走卡死处理
```

## 五、与状态总账的联动

- 子 Agent 启动时：状态总账新增子任务行，status=starting
- 每次心跳：状态总账更新对应子任务的 updated_at
- done/error：状态总账更新状态和结果摘要
- 全任务完成：状态总账标记 overall status=done

> **一句话原则**：看不见的子 Agent = 失控的子 Agent。每个 Agent 都必须可观测。