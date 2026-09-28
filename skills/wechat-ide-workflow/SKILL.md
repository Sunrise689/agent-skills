---
name: wechat-ide-workflow
description: 用微信开发者工具命令行入口（wechatide）完成小程序/小游戏从创建导入、编译预览、真机验证到上传的全流程自动化。适用于任何微信小程序或小游戏项目：新建并导入项目、模拟器编译与页面跳转、自动预览到手机、生成预览二维码、上传体验版，以及 PROJECT_*、APPID_ERROR、登录过期等常见报错处理。触发词：微信开发者工具、小程序、小游戏、编译、预览、上传、提审、project.config.json。
---

# 微信开发者工具全流程

## 何时使用

- 触发词：微信开发者工具、小程序/小游戏、新建项目、编译、预览、上传体验版、提审、模拟器、project.config.json。
- 适用：任何微信小程序（compileType 为 miniprogram）或小游戏（compileType 为 game）项目的开发、调试与发布流程。
- 不适用：通用编码辅助、与小程序无关的桌面自动化、公众号/微信支付等开发者工具之外的范畴。
- 前置条件：本机已安装微信开发者工具且命令行入口 `wechatide` 可调用；已完成扫码登录；必须在非沙箱、可访问本机桌面的 shell 中执行——沙箱内调用必然失败，应说明并改用非沙箱，勿反复重试。

## 任务目标

以命令行驱动开发者工具，走通"项目就绪 → 编译可见 → 真机可验 → 版本可传"的完整链路，全程保留可核对的结果（任务 ID、二维码、上传版本号）。

## 操作步骤

1. 运行前门禁（每个会话一次）：执行 `wechatide -c <clientName> check_wechatide_status --skill-version <当前版本号>`。`versionRelation` 为 `equal` 或 `agent_ahead` 且 `loginExpired: false` 才可继续；`agent_behind` 先从安装目录单向导入配套 skill 后重查。`loginExpired: true` 时执行 `login`，出码后主动轮询到成功终态——出码不等于已登录。返回 `tokenRequired: true` 时向用户索取"设置 → 安全"中的 CLI 访问令牌，后续命令带 `--token`；禁止猜测或旁路，令牌不得写入仓库或日志。
2. 项目创建与导入：用 `get_user_appids`（可加 `--type miniprogram|minigame`）列出账号下 AppID 供用户选择；建本地目录并写最小 `project.config.json`（含有效 `appid`、`projectname`、`compileType`），小程序还需 `app.json`（至少含 `pages`）与页面文件，小游戏需 `game.json` 与 `game.js`；然后 `project_import --project <绝对路径>` 导入项目列表，返回 `alreadyImported: true` 视为成功。
3. 编译与模拟器验证：`open_project_window --project <路径>`（默认 liteMode 只开模拟器，需编辑器/调试器用 fullMode）→ `simulator_open_page --page pages/...` 跳页 → `simulator_refresh` 刷新 → 用到 npm 依赖时 `build_npm`。注意刷新成功不等于编译通过；异常时用截图与 console/network 取证。
4. 预览与真机验证：`auto_preview --project <路径>` 自动推送预览到手机（可不打开项目窗口，可加 `--page-path`、`--query`）；需要落地二维码时用 `create_preview_qrcode --project <路径> --qr-format window`。真机远程调试面板目前需在工具与手机上手动发起，自动化覆盖预览与上传环节。
5. 上传与提审：仅当用户明确要求时执行 `upload --project <路径> --upload-version x.y.z --desc "备注"`。返回 `pending + taskId` 属异步任务：提醒用户在工具内确认，记录 taskId，继续前先查旧任务结果，不要直接重发。上传成功后，在微信公众平台后台人工提交审核（命令行不覆盖提审动作）。
6. 常见报错后置处理（先调用、出错再修，不要调用前预检）：`PROJECT_PATH_NOT_FOUND` → 核对目录存在、拼写与盘符，补建后同参数重试；`PROJECT_CONFIG_JSON_ERROR` → 修复 `project.config.json` 的非法 JSON（注释、尾逗号、截断、编码），合并写入保留无关字段后重试；`APPID_ERROR` → 读配置补有效 appid（可再查 `get_user_appids`）后重试一次，仍失败则请用户换有权限的 AppID 或重新登录，不要死循环。

## 坑与红线

- 禁止在沙箱中运行 `wechatide`；禁止用其他脚本冒充其入口。
- `upload` 只能在用户明确要求时调用；用户拒绝或取消后不得自动重试。
- `-c <clientName>` 填当前智能体产品简称，须与授权弹窗一致且同一会话不变；工具名为下划线形式，不确定先查 `--help`，勿编造。
- 异步任务分工：仅登录类需主动轮询；其余（上传、删除、云写等）提醒用户确认后凭 taskId 查询，不要重复下发原操作。
- 单文件编译（compile_wxml/compile_wxss）仅适用于小程序页面，不适用于小游戏，且结果不代表整包成功。
- 执行失败原样抛出错误，不要吞掉后猜测修复。

## 验证方式

- 创建导入：`project_import` 成功或返回 `alreadyImported: true`，开窗后模拟器能渲染首页。
- 编译：目标页在模拟器正常打开，截图无报错弹层，console 无新增错误。
- 真机：手机实际打开预览版本并走通主路径，截图留证。
- 上传：拿到上传成功终态与版本号，版本列表可见新版本；提审动作在公众平台后台确认。
