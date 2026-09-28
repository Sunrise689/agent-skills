---
name: coze-agent-link-repair
description: 排查“把 Claude Code / Codex 等本地编程 Agent 接入扣子前端”链路故障的方法。覆盖四类高频故障：全模型 502（上游强制会话头缺失，用声明式 providerPlugins 注入修复）、前端看不到思维链（源头 Agent 默认未开 thinking）、bridge 掉线（重启与守护自愈）、模型清单三处不同步。当出现 502、All target providers failed、无思考块、agent 掉线、模型下拉缺失等关键词时使用。
---

# 扣子 × 本地编程 Agent 链路排障

链路全貌：扣子前端 → bridge（ACP 协议，默认 `~/.coze/bridge/`）→ 适配器 → 本地 Agent CLI（Claude Code / Codex 等）→ 网关（如 claude-code-router）→ 上游供应商。排障先定段，再下手。

## 何时使用
- 触发词：扣子接本地 Agent、bridge 掉线/离线、502、All target providers failed、前端没有思维链/思考块、模型下拉缺模型、“升级本地 agent”弹窗。
- 适用环境：Windows 本机装有 bridge 与网关，能杀进程、能改配置文件。
- 不适用：纯云端模型接口故障（无本地链路）、扣子平台侧工作流编排问题。
- 前置条件：bridge 凭据文件（connection.json 类，存 PAT/token）只确认存在，绝不读取或记录内容；桌面端与 CLI 的 node 版本可能不同，会触发 daemon 自动重启，属正常现象。

## 任务目标
恢复“前端→bridge→适配器→Agent→网关→上游”全链路可用；每次修改前有 .bak 备份，失败可回滚。

## 操作步骤（按故障速查）

### ① 全模型 502 / All target providers failed
1. 先看网关日志里的上游真实返回：常见是上游 400 被逐层包装成 502，别停在 502 表象。
2. 高频根因：上游强制要求自定义会话头（实测案例：要求 `x-opencode-session`，缺失报 400 MissingSessionID，带 key 也没用；加任意非空值即恢复）。
3. 修法：在网关配置的声明式 `providerPlugins` 数组追加一条，按 provider 匹配上游，`auth.headers` 注入该会话头（值为任意非空固定标识）。
4. 改前把配置备份为 `*.bak`；改完杀网关进程重启（守护进程不一定拉起新配置，必要时手动启动 gateway 引导脚本）。
5. 验证：直连网关抽测多个模型，全部 200 即修复。

### ② 前端看不到思维链
1. 链路逐段排查：前端 → bridge → 适配器 → Agent → 网关。
2. 已知事实：bridge 的转发原样透传不过滤；适配器支持 thought（有思考文本就发）。断点几乎都在源头——本地 Agent 默认不开启 thinking，流里没有思考文本，适配器自然无块可发。
3. 修法：从源头注入环境变量强制开启（如 `MAX_THINKING_TOKENS=10240`），注入点在 Agent 启动配置或 bridge 启动代码；改前备份原文件为 `*.bak`。
4. 语言规范写入 Agent 全局记忆文件（如 `~/.claude/CLAUDE.md`）：思考默认中文、术语可夹英文。
5. 重启 bridge 生效。

### ③ bridge 掉线 /“掉线了+要求升级”弹窗
1. 铁律：先跑 `coze-bridge status` 看 agents 列表，并检查本地 agents 注册目录是否齐全，再谈版本。注册目录丢失 → 心跳停 → 云端判掉线，升级弹窗多为误诊表象，与版本无关。
2. 真实版本以 `~/.coze/bridge/lib/index.js` 里的版本常量为准（config.json 的 libVersion 只是记录，须交叉验证）；再对照 npm 官方源与镜像源 dist-tags 判断是否真落后。
3. `connect` 幂等：同凭据 + env 时打 noop。掉线先杀旧进程重新 connect，守护自愈（auto-revive）会重新注册 agent。
4. 若“我已执行”报升级失败：失败多半在桌面端自己那一侧——查 `%APPDATA%` 下桌面端日志（搜“检测 Agent Bridge 升级结果失败”），bridge 侧日志无 upgrade 帧即证明请求从未到达；重启桌面端重建缓存。
5. 已是最新版时反复跑 `@latest` 是纯 noop，无意义；确需指定版本时向官方索取。

### ④ 模型清单不同步
1. 清单存在三处，必须一起同步对齐：网关侧 provider models、bridge 模型缓存（`~/.coze/bridge/` 下 model-cache.json）、客户端/前端 provider 配置。
2. 以上游 `/v1/models` 全量为基准；本地 Agent 侧模型名用裸名。
3. 三处修改前各留 `*.bak`，改完核对条目数一致；桌面端模型下拉属平台侧配置，按清单人工填写。

## 坑与红线
- 一切修改前先做 `.bak` 备份；回滚 = 还原备份 + 重启对应进程。
- 网关新版配置真身可能在 sqlite 数据库（app_config 表一行存全量 JSON），旧版 config.json 空目录是幌子。
- CLI 与 daemon 的 node 版本不一致会触发 daemon 自动重启并换 PID，不是故障。
- 凭据/token 文件绝不读取、不记录、不外传内容；不做绕过上游鉴权的操作——会话头是协议要求，任意非空值即可。
- 桌面端的版本门限与模型下拉在云端/平台侧下发，本地翻不到，别在本地空找。

## 验证方式
- 502：对上游全量模型普查，记录可用数与不可用原因（503=套餐不含；400=需同意条款的默认拒绝类）。
- 思维链：前端开新会话发推理问题，看到思考块即通过；有块但英文→重开会话；完全无块→下一刀查网关是否透传 thinking 字段。
- 掉线：status 显示 WS established、agents 全部在线注册、心跳稳定运行。
- 清单：三处条目数一致，前端下拉实测可见新模型。
