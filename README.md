# Agent Skills 合集

27 个可直接安装使用的 AI Agent 技能包，遵循 Agent Skills 开放标准（每个技能 = 一个目录，内含 `SKILL.md` 主文件与可选的 `references/`、`scripts/` 等支撑文件）。

技能以**方法论**为主：讲清一套流程怎么走、证据怎么抓、边界在哪，而不是绑定某个具体产品。

## 目录结构

```
skills/<name>/       解包目录版，可直接拷贝进 Agent 技能目录
packages/<name>.zip  压缩包版，结构与目录版一致（<name>/SKILL.md），便于分发与平台上传
```

## 技能清单（27）

### 故障排查与修复

| 技能 | 一句话 |
| --- | --- |
| [fault-triage](skills/fault-triage/SKILL.md) | 故障排查通用方法：把偶现问题当作临界状态的周期表现，以现场采样、时间戳对时、分层排除与对照实验定位根因 |
| [reversible-repair](skills/reversible-repair/SKILL.md) | 桌面 GUI「界面失效 / 状态异常」的可回滚、证据驱动修复流程，以真实 UI 操作作为唯一验收标准 |
| [coze-agent-link-repair](skills/coze-agent-link-repair/SKILL.md) | 本地编程 Agent 接入 Coze 前端的链路排障：全模型 502、思维链缺失、bridge 掉线、模型清单不同步四类故障 |
| [safe-residual-cleanup](skills/safe-residual-cleanup/SKILL.md) | 软件安全卸载与残留清理：先盘点、官方途径卸载、备份校验后定向删除、逐项复核 |

### 工程交付与工具链

| 技能 | 一句话 |
| --- | --- |
| [fullstack-closed-loop](skills/fullstack-closed-loop/SKILL.md) | 软件产品从边界定义到灰度发布的全栈闭环：先统一事实层、多入口分层交付、证据阶梯验收、发布留回滚回路 |
| [wechat-ide-workflow](skills/wechat-ide-workflow/SKILL.md) | 微信开发者工具命令行全流程：创建导入、编译预览、真机验证、上传体验版与常见报错处理 |
| [yingdao-app-pipeline](skills/yingdao-app-pipeline/SKILL.md) | 通过本地 MCP 把 RPA 应用从建流、写码、填参、诊断做到本地发布的完整生产线 |
| [cloud-coder](skills/cloud-coder/SKILL.md) | 给智能体装上云端编码引擎（OpenCode / CodeX CLI），自然语言驱动「生成→测试→修复→交付」闭环 |
| [codex-meta](skills/codex-meta/SKILL.md) | 在本机部署 CodeX CLI 编码引擎：多平台、多兼容 API 提供商、手机远程遥控，代码不出本地 |
| [desktop-coordinate-library](skills/desktop-coordinate-library/SKILL.md) | 桌面坐标库三件套：UIA 建库、按名点击、锚点兜底；坐标库由使用者在自己机器上现场生成 |

### 验证、评估与编排

| 技能 | 一句话 |
| --- | --- |
| [task-proportional-verification](skills/task-proportional-verification/SKILL.md) | 按任务比例验证：简单明确的任务只做最小修改与最小验证，防止验证范围被自动升级 |
| [answer-quality-attribution](skills/answer-quality-attribution/SKILL.md) | 回答质量的证据化归因：沿输入理解、生成行为、上下文与记忆、技能编排四层定位首个偏差层 |
| [small-step-orchestration](skills/small-step-orchestration/SKILL.md) | 批量处理与并行委派纪律：一小步 3~5 个关联问题，以文件、契约、范围与验收条件划界 |
| [harness-commander](skills/harness-commander/SKILL.md) | 复杂任务指挥框架：七步闭环、引导模式、循环收敛、证据分级与安全护栏 |
| [agent-software-scan](skills/agent-software-scan/SKILL.md) | 对新 Agent 软件做全盘功能扫描：循环、调度与上下文、技能系统、记忆机制四层，输出适配性判断 |

### 知识、记忆与协作

| 技能 | 一句话 |
| --- | --- |
| [knowledge-sedimentation](skills/knowledge-sedimentation/SKILL.md) | 三层知识沉淀：经验层、方法层、哲学层归档与索引更新，宁缺毋滥 |
| [multi-agent-memory-unification](skills/multi-agent-memory-unification/SKILL.md) | 多 Agent 记忆统一：盘点、归档、归并分层、改启动协议、按清单验收——一个正本，多种工具 |
| [task-handoff](skills/task-handoff/SKILL.md) | 生成结构化任务交接文档，在不同对话、不同 Agent 之间传递任务状态 |

### 数据分析与金融工具

| 技能 | 一句话 |
| --- | --- |
| [deterministic-value-modeling](skills/deterministic-value-modeling/SKILL.md) | 确定性数值建模五层流水线：把「值不值、选哪个」变成可复算的数字结论 |
| [kline-pattern-master](skills/kline-pattern-master/SKILL.md) | 多周期 K 线技术分析报告生成与校验（A 股 / 港股） |
| [best-sma-finder](skills/best-sma-finder/SKILL.md) | 移动平均线分析：暴力枚举 SMA 回测最优单 / 双均线策略、无忧线与被套时长、浮亏深度分析 |
| [api-price-finder](skills/api-price-finder/SKILL.md) | 全网 LLM API 比价 + 智力对标 + 场景推荐三合一，实时数据源，默认只搜便宜锚点以下 |

### 研究、内容与通用能力

| 技能 | 一句话 |
| --- | --- |
| [deep-search](skills/deep-search/SKILL.md) | 深度搜索：多探针联网搜索 + 信息原子提纯，主流深度研究功能的平替方案 |
| [flash-reason](skills/flash-reason/SKILL.md) | 为快速模型开启轻量推理思考模式，在尽量不增加耗时的前提下提升输出稳定性 |
| [progressive-disclosure](skills/progressive-disclosure/SKILL.md) | 复杂产品说明的分层披露法：第一层只给能做决定的信息，证据与公式按需下钻 |
| [mineru-parser](skills/mineru-parser/SKILL.md) | 文档解析：PDF、Word、PPT、Excel、扫描件与图片转 Markdown，保留表格、公式与版面顺序 |
| [starbreaker](skills/starbreaker/SKILL.md) | 手游资源包定向解包方法论：哈希路径、分块 trailer 反查与数值表还原（仅限自有设备对已购内容做个人研究） |

## 安装

- **目录版**：把 `skills/<name>/` 整个拷进你所使用 Agent 的技能目录（不同工具的路径不同，如 `~/.agents/skills/`、项目内 `.agents/skills/` 等），即装即用。
- **压缩包版**：`packages/<name>.zip` 解压得到同名目录，结构与目录版一致。

## 说明

- 各技能的具体前置条件、依赖与执行环境要求，以各自 `SKILL.md` 正文为准；部分技能含平台/环境相关步骤，请按文中前置条件准备。
- 技能内容归各技能作者所有，含各自的使用说明与声明。
