# 循环规格卡模板（Loop Spec Card）

**用途**：为通过 Loop Discovery 决策门的重复工作流编写结构化规格。六要素（WHEN → SEE → DO → CHECK → STOP → LEAVE）必须全部填写，缺一不可。

## 一、空白模板

```text
LOOP SPEC CARD: <Loop 名称（简短，≤10 字）>

WHEN: <触发条件>
  - 触发类型: [ 定时巡检 | 事件响应 | 目标完成 | 主动发现 | 系统改进 ]
  - 触发信号: <具体事件/频率/cron 表达式>
  - 前置条件: <触发前必须满足的状态条件>

SEE: <观测点>
  - 行动前必须检查的具体证据: <文件路径/数据源/API endpoint>
  - 检查内容: <需要确认的字段/状态/值>
  - 异常处理: <如果检查不通过怎么办>

DO: <执行体>
  - 允许动作清单:
    1. <步骤 1>
    2. <步骤 2>
    ...
  - 明确排除项:
    - ❌ <不允许的操作>
    - ❌ <不允许的操作>
  - 输入: <schema/格式/来源>
  - 输出: <schema/格式/落盘位置>

CHECK: <验证信号>
  - 成功判据: <具体的断言/退出码/日志模式>
  - 失败判据: <什么算失败>
  - 证据不足判据: <什么情况算"无法判断"，需人工介入>

STOP: <停止边界>
  - 最大重试次数: <N>
  - 超时时间: <秒/分钟>
  - 降级策略: <停止后做什么——发通知/写日志/不做任何事>
  - 人工决策边界: <什么情况必须暂停，等待人工决策>

LEAVE: <退出后产物>
  - 成功时留下: <补丁/报告/运行日志/更新后的状态文件>
  - 失败时留下: <错误日志/未完成清单/需要人工处理的项>
  - 证据不足时留下: <观察到的状态快照/缺失条件列表/恢复操作指引>
```

## 二、填写示例：定时代码规范简报

```text
LOOP SPEC CARD: 每日 Lint 健康简报

WHEN: <触发条件>
  - 触发类型: 定时巡检
  - 触发信号: 每日 08:00 UTC+8 (cron: 0 0 8 * * *)
  - 前置条件: 仓库 `main` 分支已成功 pull 最新代码；`node_modules` 已安装

SEE: <观测点>
  - 行动前必须检查的具体证据: 仓库根目录 `package.json` 中 `scripts.lint` 字段
  - 检查内容: 确认 lint 命令存在且非空；确认 `node_modules/.bin/eslint` 可执行
  - 异常处理: 若 lint 命令不存在 → 输出「未配置 lint」报告，STOP → LEAVE（证据不足）

DO: <执行体>
  - 允许动作清单:
    1. `npm run lint -- --format json` 产出 lint 结果 JSON
    2. 解析 JSON，统计 error / warning 数量和按文件分布
    3. 与上次简报比较 delta（新增/修复/恶化项数）
    4. 写入简报文件 `.harness/daily-lint-brief.md`
  - 明确排除项:
    - ❌ 不自动修复 lint 错误（不做 `npm run lint -- --fix`）
    - ❌ 不修改任何源文件
    - ❌ 不执行 lint 以外的任何构建/测试任务
  - 输入: `npm run lint -- --format json` 的 stdout
  - 输出: `.harness/daily-lint-brief.md`（Markdown 格式简报）

CHECK: <验证信号>
  - 成功判据: lint 命令退出码 0，JSON 可成功解析，简报文件已写入
  - 失败判据: lint 命令退出码非 0 且非 lint 错误（如 node_modules 缺失）
  - 证据不足判据: lint JSON 解析失败（格式不兼容）→ 保留原始 stdout

STOP: <停止边界>
  - 最大重试次数: 1（不重试，lint 失败本身即是有效信号）
  - 超时时间: 120 秒
  - 降级策略: 暂停并写错误日志，下次定时触发时重新拉代码尝试
  - 人工决策边界: 同一条规则产生 >100 个 error 时（可能配置错误），简报标注「疑似配置异常」，不重试

LEAVE: <退出后产物>
  - 成功时留下: `.harness/daily-lint-brief.md`（含 error/warning 总数、delta、Top 5 问题文件）；更新 `.harness/lint-history.json`（追加当日记录）
  - 失败时留下: `.harness/daily-lint-error.log`（包含错误信息和原始 stdout）
  - 证据不足时留下: `.harness/daily-lint-brief.md` 写入「lint 命令不存在」标记；`.harness/lint-config-missing.md` 记录缺失的配置路径
```

## 三、填写指南

1. **WHEN** — 必须精确到能写成 cron 或 event hook。模糊描述如"需要时运行"不通过。
2. **SEE** — 必须写具体的文件路径/命令/API。不能写"检查配置是否正确"。
3. **DO** — 只写允许的操作。排除项比允许项更重要——防止 Agent 自由发挥导致不可逆后果。
4. **CHECK** — 三种情况都要覆盖。只写成功判据的卡不算完整。
5. **STOP** — 每次执行都有成本。必须限制重试和超时，防止死循环。
6. **LEAVE** — 不留下产物的 Loop = 不可观测的 Loop = 不可信的 Loop。三种退出情况都有对应产物。

<!-- 用途：循环规格卡模板与填写示例。在通过 Loop Discovery 决策门后，编写复用流程的六要素结构化规格时按需加载。 -->