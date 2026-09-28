---
name: yingdao-app-pipeline
description: 通过影刀（ShadowBot）本地 MCP 接口与命令行，把一个 RPA 应用从建流、写码、填参、诊断到本地发布完整交付的生产线流程。适用于在本机影刀客户端中自动化创建、调试并发布流程应用；强调固定生产顺序，以及 save 不等于发布。触发词：影刀、ShadowBot、RPA 应用、MCP 建应用、发布应用、流程机器人、自动化应用。
---

# 影刀 RPA 应用生产线

## 何时使用

- 触发词：影刀、ShadowBot、RPA、建流程、发布应用、MCP 建应用、自动化应用。
- 适用：本机已安装影刀客户端，需要用 MCP/CLI 完成"创建应用 → 写代码 → 填参数 → 诊断 → 发布"的全流程交付。
- 不适用：影刀之外的 RPA 平台；不涉及任何平台对抗、刷量、风控规避或账号自动化类需求。
- 前置条件：影刀客户端已安装并登录，本机进程 ShadowBot.Shell 在运行（监听本地 REST 端口 42500 与 8087），实测基线为客户端 6.3.x；需要真实桌面会话——锁屏状态下前台类操作必然失败。

## 任务目标

用固定顺序把需求交付为一个本地已发布、可运行的影刀应用，参数可经外部输入注入，产出附诊断与端到端验收证据。

## 操作步骤

1. 确认入口。MCP：`http://127.0.0.1:42500/api/v1/mcp`，streamable HTTP，无需会话握手，curl/node 可直接调用（browser-use MCP 在 `api/v1/browser-use-mcp/mcp`）。CLI：`<安装目录>\shadowbot.shell-cli.exe`，常用子命令 `studio create/open/current/save|sync`、`console app list/detail/publish`、`console task run --inputs-file`。本地 SDK 文档用 `wiki.read` 工具读取，勿凭记忆猜 API。
2. 建流。`studio create` 创建应用 → `studio open --app-id` 打开 → `app.create_flow`，代码型应用 kind 选 `code`。
3. 写码。`codeflow.write` 整段写入 Python 实现；依赖用 `python_pip` 安装；静态资源用 `app.resource.add`。
4. 填参。`flow.write_parameters` 声明核心 In/Out 参数与 main 的 In 参数 → `flow.edit_blocks` 插入 `process.run` 块 → `flow.fill_blocks` 一次性填全 process 与全部 arguments、outputs（整体替换，见坑 2）。
5. 保存与自检。`app.update_info` 更新应用信息 → `app.save` → `diagnostics.snapshot` 做诊断；有错误先清零再前进。
6. 同步。`studio current sync` 把本地状态同步到平台。
7. 发布。`console app publish` 执行本地发布——save 不等于发布，缺这一步应用不可用。随后 `console app detail` 核对 flowParamInfo 与参数定义一致。
8. 运行验收。`app.run`（或 CLI `console task run --inputs-file <UTF-8 JSON 文件>`）跑端到端用例，`app.logs` 取日志，逐条核对输入输出；发布后再复验一次。

## 坑与红线

- 中文参数必须走 UTF-8 文件：把含中文的流程名/参数写入 UTF-8 编码的 JSON 文件再作参数传入（或经脚本从 stdin 读入）；shell 命令行内联中文会变成乱码。
- `fill_blocks` 是对块的 inputs 整体替换：补填时必须一次填全所有 arguments，否则此前已填的会被清空。
- 未填的 In 参数会以 None 传入并覆盖代码默认值：代码里必须写 `if x is None: x = default` 兜底。
- `app.save` 会冲掉可视化流程中未保存的表单编辑：先改核心 CodeFlow，最后才填 main 的块。
- CLI 社区版 `task run` 有每日额度（0 点重置）；MCP 的 `app.run`（studio 通道）不受此限，验收优先走 MCP。
- 锁屏或键鼠被锁定时，前台窗口操作（SetForegroundWindow 类）必然失败：应用内必须先校验前台窗口状态并拒点，不得盲点；锁屏期间不安排真机验收。
- 运行时 Python 为 3.7（venv 在应用目录下）：依赖需选兼容版本（实测 numpy 1.21.6、opencv-python 4.5.5.64 可用，Pillow/openpyxl 预装），写码前先确认版本约束。
- 涉及账号登录、验证码、平台风控的自动化一律不做。

## 验证方式

- 诊断清零：`diagnostics.snapshot` 无错误项。
- 发布核验：`console app detail` 可见应用且 flowParamInfo 与设计一致；发布版 `app.run` 端到端用例全部通过。
- 证据留存：每次交付保留建流参数、代码版本、端到端用例输出与运行日志；拒点防护做一次锁屏场景的负向验证。
