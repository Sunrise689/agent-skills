---
name: codex-meta
description: 本地 CodeX CLI 编码引擎——在个人电脑上部署 OpenAI 官方 CodeX CLI，支持 3 大平台（Windows/Mac/Linux）、6+ 兼容 API 提供商（DeepSeek/OpenRouter/SiliconFlow/OpenAI/Grok/本地Ollama），手机远程遥控写代码跑任务。比云端编码更安全（代码不出本地）、更灵活（任意项目目录）、更省钱（DeepSeek V4 Flash ¥2/百万Token）。适用场景：手机写Python脚本、远程改项目Bug、iPad上跑数据分析、任何设备操控家中电脑编码。电脑需开机。
---

# CodeX Meta — 本地 CodeX CLI + 远程遥控

让任何设备（手机、平板、第三方平台）通过自然语言操控自己电脑上的 CodeX CLI 写代码、跑任务。纯本地方案，代码不离开你的电脑。

## 一、简介

### 这是什么

CodeX Meta 是一套**纯本地**的编码方案，包含三个核心能力：

| 能力 | 说明 |
|------|------|
| **安装** | 在你的电脑上一键部署 CodeX CLI（OpenAI 官方命令行编码工具） |
| **遥控** | 从手机/平板/任何平台远程操控电脑上的 CodeX CLI |
| **执行** | 自然语言描述任务，`codex exec` 自动完成——写代码、改Bug、跑分析、生成报告 |

### 为什么选本地而不是云端

| 维度 | 本地 CodeX Meta | 云端编码 |
|------|----------------|---------|
| **数据安全** | 代码/数据不出本地电脑 | 代码上传到云端服务器 |
| **灵活性** | 任意项目目录，直接读写本地文件 | 仅限沙箱环境 |
| **成本** | 仅 API Token 费用（DeepSeek ¥2/百万Token） | 平台订阅 + API 费用 |
| **模型选择** | 6+ 兼容 API 提供商自由切换 | 受限于平台支持的模型 |
| **项目上下文** | 完整 Git 历史、本地依赖、环境变量 | 需要手动上传项目 |

### 兼容的 API 提供商

任何兼容 OpenAI Responses API 的模型都能用：

| 提供商 | 推荐模型 | 价格（百万Token） | 备注 |
|--------|---------|-------------------|------|
| **DeepSeek** | deepseek-v4-flash | ¥2 输入 / ¥8 输出 | 推荐，性价比最高 |
| **OpenRouter** | 多种模型 | 按模型浮动 | 一站式多模型 |
| **硅基流动** | DeepSeek-V3 等 | 按量计费 | 国内低延迟 |
| **OpenAI** | GPT-4o / GPT-4.1 | 按 OpenAI 定价 | 官方，最贵 |
| **Grok** | grok-3 | 按量计费 | xAI 出品 |
| **本地 Ollama** | 本地模型 | 免费 | 完全离线 |

---

## 二、安装 CodeX CLI

### 2.1 前置检查

在安装前，确保你的电脑满足以下条件：

| 条件 | 检查方式 | 最低要求 |
|------|---------|---------|
| Node.js | `node --version` | ≥ 18.0.0 |
| npm | `npm --version` | ≥ 9.0.0 |
| Git | `git --version` | ≥ 2.30（可选，但推荐） |

**Windows 用户**：如未安装 Node.js，去 [nodejs.org](https://nodejs.org) 下载 LTS 版本安装。

**Mac 用户**：推荐用 Homebrew：
```bash
brew install node git
```

**Linux 用户**：
```bash
# Ubuntu/Debian
sudo apt install nodejs npm git -y

# 或使用 nvm（推荐）
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.0/install.sh | bash
nvm install --lts
```

### 2.2 安装 CodeX CLI

**三步完成安装：**

#### 方式一：自动安装脚本（推荐）

```bash
# Mac / Linux
bash scripts/install.sh

# Windows PowerShell（管理员运行）
powershell -ExecutionPolicy Bypass -File scripts/install.ps1
```

脚本会自动完成：检测环境 → 安装 CodeX CLI → 引导配置 API Key → 验证安装。

#### 方式二：手动安装

```bash
# 第一步：全局安装 CodeX CLI
npm install -g @openai/codex

# 第二步：验证安装
codex --version
# 预期输出：CodeX CLI v0.146.0 或更高版本
```

### 2.3 配置 API Key

CodeX CLI 通过 `~/.codex/config.toml` 配置文件管理 API 连接。安装脚本会自动引导你配置。

#### 写入配置文件

选择你的 API 提供商，复制对应配置写入 `~/.codex/config.toml`。

> ⚠️ **格式说明（重要）**：CodeX CLI 使用 `model_provider` + `[model_providers.xxx]` 配置段（旧版 `[default]`/`[providers.xxx]` 格式在 v0.147+ 已不再支持，会报 `unknown configuration field 'default'`）。

**方案一：DeepSeek（推荐）**

```toml
model = "deepseek-v4-flash"
model_provider = "deepseek"

[model_providers.deepseek]
name = "DeepSeek"
base_url = "https://api.deepseek.com/v1"
wire_api = "responses"
api_key = "sk-your-deepseek-api-key"
```

获取 Key：[platform.deepseek.com/api_keys](https://platform.deepseek.com/api_keys)

**方案二：OpenRouter**

```toml
model = "openai/gpt-4.1"
model_provider = "openrouter"

[model_providers.openrouter]
name = "OpenRouter"
base_url = "https://openrouter.ai/api/v1"
wire_api = "responses"
api_key = "sk-or-v1-your-openrouter-key"
```

获取 Key：[openrouter.ai/keys](https://openrouter.ai/keys)

**方案三：硅基流动（国内低延迟）**

```toml
model = "deepseek-ai/DeepSeek-V3"
model_provider = "siliconflow"

[model_providers.siliconflow]
name = "SiliconFlow"
base_url = "https://api.siliconflow.cn/v1"
wire_api = "responses"
api_key = "sk-your-siliconflow-key"
```

获取 Key：[siliconflow.cn](https://siliconflow.cn)

**方案四：OpenAI 官方**

```toml
model = "gpt-4.1"
model_provider = "openai"

[model_providers.openai]
name = "OpenAI"
base_url = "https://api.openai.com/v1"
wire_api = "responses"
api_key = "sk-your-openai-api-key"
```

**方案五：Grok (xAI)**

```toml
model = "grok-3"
model_provider = "grok"

[model_providers.grok]
name = "Grok"
base_url = "https://api.x.ai/v1"
wire_api = "responses"
api_key = "xai-your-grok-api-key"
```

**方案六：本地 Ollama（免费，完全离线）**

```toml
model = "qwen2.5-coder:7b"
model_provider = "ollama"

[model_providers.ollama]
name = "Ollama"
base_url = "http://localhost:11434/v1"
wire_api = "responses"
```

前提：已安装 [Ollama](https://ollama.com) 并拉取模型 `ollama pull qwen2.5-coder:7b`。

#### 使用环境变量（可选，更安全）

如果你不想在配置文件中明文写 API Key，可以用 `env_key` 字段指向环境变量：

```toml
model = "deepseek-v4-flash"
model_provider = "deepseek"

[model_providers.deepseek]
name = "DeepSeek"
base_url = "https://api.deepseek.com/v1"
wire_api = "responses"
env_key = "DEEPSEEK_API_KEY"
```

然后在终端中设置：
```bash
# Mac / Linux
export DEEPSEEK_API_KEY="sk-your-key"

# Windows PowerShell
$env:DEEPSEEK_API_KEY = "sk-your-key"
```

### 2.4 验证安装

```bash
# 检查版本
codex --version

# 测试执行（用一个简单任务；非 Git 目录需加 --skip-git-repo-check）
codex exec --skip-git-repo-check "用 Python 打印 'Hello from CodeX Meta!'"

# 预期输出中应包含 Python 代码和 "Hello from CodeX Meta!"
```

---

## 三、远程遥控

安装好 CodeX CLI 之后，你就可以从**手机、平板、任何第三方平台**远程操控电脑上的 CodeX CLI 写代码了。

### 3.1 前提条件

| 条件 | 说明 |
|------|------|
| **电脑开机** | 必须开机，不能关机 |
| **不建议锁屏** | 锁屏状态下部分窗口操作受限；最好保持解锁状态 |
| **网络通畅** | 电脑需要联网（API 调用需要） |
| **CodeX CLI 已安装** | 按照第二章完成安装和配置 |

### 3.2 Windows 遥控（desktop-control-win）

Windows 遥控通过 `desktop-control-win` 技能实现，核心流程：

```
你的手机/平板 → Agent → desktop-control-win → Windows 电脑上的终端 → CodeX CLI
```

#### 工作流程

**Step 1：确保电脑未休眠**

如果电脑可能处于休眠状态，先尝试唤醒：
```powershell
# 通过 desktop-control-win 发送按键唤醒
powershell -ExecutionPolicy Bypass -File "$env:USERPROFILE/.openclaw/workspace/skills/desktop-control-win/scripts/input-sim.ps1" -Action send-keys -Keys "Enter"
```

**Step 2：打开终端窗口**

```powershell
# 方法一：启动 Windows Terminal（推荐）
powershell -ExecutionPolicy Bypass -File "$env:USERPROFILE/.openclaw/workspace/skills/desktop-control-win/scripts/app-control.ps1" -Action launch -Target "wt"

# 方法二：启动 PowerShell
powershell -ExecutionPolicy Bypass -File "$env:USERPROFILE/.openclaw/workspace/skills/desktop-control-win/scripts/app-control.ps1" -Action launch -Target "powershell"
```

**Step 3：聚焦终端窗口**

```powershell
powershell -ExecutionPolicy Bypass -File "$env:USERPROFILE/.openclaw/workspace/skills/desktop-control-win/scripts/app-control.ps1" -Action focus -Target "Windows Terminal"
```

**Step 4：cd 到项目目录并执行 CodeX**

```powershell
# 输入 cd 命令
powershell -ExecutionPolicy Bypass -File "$env:USERPROFILE/.openclaw/workspace/skills/desktop-control-win/scripts/input-sim.ps1" -Action type-text -Text "cd C:\Users\username\my-project"

# 按回车
powershell -ExecutionPolicy Bypass -File "$env:USERPROFILE/.openclaw/workspace/skills/desktop-control-win/scripts/input-sim.ps1" -Action send-keys -Keys "Enter"

# 输入 codex exec 命令
powershell -ExecutionPolicy Bypass -File "$env:USERPROFILE/.openclaw/workspace/skills/desktop-control-win/scripts/input-sim.ps1" -Action type-text -Text "codex exec `"帮我写一个数据分析脚本，读取 data.csv 并生成柱状图`""

# 按回车执行
powershell -ExecutionPolicy Bypass -File "$env:USERPROFILE/.openclaw/workspace/skills/desktop-control-win/scripts/input-sim.ps1" -Action send-keys -Keys "Enter"
```

**Step 5：截图查看结果**

```powershell
powershell -ExecutionPolicy Bypass -File "$env:USERPROFILE/.openclaw/workspace/skills/desktop-control-win/scripts/screen-info.ps1" -Action screenshot -Target "Windows Terminal" -OutputPath "$env:USERPROFILE/codex-result.png"
```

#### 遥控操作速查

| 操作 | desktop-control-win 命令 |
|------|------------------------|
| 唤醒电脑 | `input-sim.ps1 -Action send-keys -Keys "Enter"` |
| 打开终端 | `app-control.ps1 -Action launch -Target "wt"` |
| 聚焦窗口 | `app-control.ps1 -Action focus -Target "Windows Terminal"` |
| 输入文字 | `input-sim.ps1 -Action type-text -Text "..."` |
| 按回车 | `input-sim.ps1 -Action send-keys -Keys "Enter"` |
| 按 Ctrl+C | `input-sim.ps1 -Action send-keys -Keys "Ctrl+C"` |
| 截图 | `screen-info.ps1 -Action screenshot -OutputPath "..."` |

### 3.3 Mac / Linux 遥控（SSH / Bash）

Mac 和 Linux 电脑通过 SSH 或 bash 直接执行命令，无需模拟键盘输入。

#### 工作流程

**Step 1：确认电脑在线**

```bash
# 通过 bash 工具指定桌面设备名称执行
whoami && uptime
```

**Step 2：直接执行 codex exec**

```bash
# cd 到项目目录
cd /path/to/your/project

# 执行 CodeX
codex exec "帮我重构 utils.py 里的重复代码，提取公共函数"
```

**Step 3：查看结果**

```bash
# 查看 CodeX 生成的文件
ls -la
cat generated_script.py
```

### 3.4 电脑休眠唤醒

如果电脑进入了休眠/睡眠状态：

| 系统 | 唤醒方式 |
|------|---------|
| **Windows** | 通过 desktop-control-win 发送键盘输入（任意按键），或配置 BIOS 允许网络唤醒（Wake-on-LAN） |
| **Mac** | 通过 SSH 发送 `caffeinate` 命令阻止休眠；如果已休眠，需要物理唤醒 |
| **Linux** | 通过 SSH 执行 `systemctl suspend` 的反操作；配置 Wake-on-LAN |

**建议**：如果经常远程使用，将电脑电源设置改为"永不睡眠"：

- **Windows**：设置 → 系统 → 电源 → 屏幕和睡眠 → 设为"从不"
- **Mac**：系统设置 → 锁定屏幕 → 设为"永不"
- **Linux**：`sudo systemctl mask sleep.target suspend.target hibernate.target`

---

## 四、执行代码任务

### 4.1 基础执行

用自然语言描述任务，CodeX CLI 自动完成：

```bash
# 写一个新脚本
codex exec "用 Python 写一个网页爬虫，爬取豆瓣电影 Top 250，保存为 CSV"

# 修改现有代码
codex exec "重构 src/utils.py，把重复的日期处理逻辑提取成一个公共函数"

# 数据分析
codex exec "读取 sales_2024.csv，分析月度销售额趋势，生成折线图和 Markdown 报告"

# Bug 修复
codex exec "修复 api/server.py 第 42 行的 SQL 注入漏洞，使用参数化查询"
```

### 4.2 指定工作目录

```bash
# 在特定目录下执行
cd ~/projects/my-app && codex exec "添加一个用户登录接口"

# 或者用 -C/--cd 参数指定工作目录
codex exec "写一个 Dockerfile" -C ~/projects/my-app
```

### 4.3 Git 仓库处理

CodeX CLI 默认需要在 Git 仓库目录下执行。如果不在 Git 仓库中：

```bash
# 方法一：初始化 Git 仓库
git init
codex exec "你的任务"

# 方法二：跳过 Git 检查（如果 CLI 支持）
codex exec "你的任务" --skip-git-repo-check
```

### 4.4 提示词最佳实践

给 CodeX 的提示词质量直接决定输出质量。遵循以下原则：

#### ✅ 好的提示词

```
"在 src/api/ 目录下创建一个 FastAPI 用户模块，包含：
1. POST /users/register — 用户注册（邮箱 + 密码，密码 bcrypt 加密）
2. POST /users/login — 用户登录（返回 JWT token）
3. GET /users/me — 获取当前用户信息（需认证）

要求：
- 使用 SQLAlchemy ORM 操作 PostgreSQL
- 遵循 PEP 8 代码风格
- 添加参数校验（Pydantic）
- 写单元测试（pytest）
- 生成 API 文档注释"
```

#### ❌ 差的提示词

```
"帮我写个用户系统"
```

#### 提示词要素

| 要素 | 说明 | 示例 |
|------|------|------|
| **任务目标** | 一句话说清楚要做什么 | "创建一个 FastAPI 用户模块" |
| **背景上下文** | 项目结构、技术栈、现有代码 | "使用 SQLAlchemy + PostgreSQL，文件放在 src/api/" |
| **具体需求** | 逐条列出，越具体越好 | "POST /users/register，邮箱+密码，bcrypt" |
| **输出格式** | 期望产出什么 | "生成 Python 文件 + 测试文件 + API 文档" |
| **约束条件** | 不能做什么、注意什么 | "遵循 PEP 8，不要用 Flask，用 FastAPI" |

### 4.5 提示词较长时

如果提示词超过 200 字，建议先写入文件再通过 stdin 传入：

```bash
# 将提示词写入文件
cat > /tmp/codex-prompt.txt << 'EOF'
（你的长提示词）
EOF

# 通过 stdin 传入（注意：codex exec 没有 -f 参数，用重定向）
codex exec < /tmp/codex-prompt.txt
```

---

## 五、故障速查表

| 问题 | 可能原因 | 解决方法 |
|------|---------|---------|
| `codex: command not found` | CodeX CLI 未安装或 PATH 未配置 | 重新执行 `npm install -g @openai/codex`，检查 npm 全局 bin 目录是否在 PATH 中 |
| `Authentication failed` / `401` | API Key 错误或过期 | 检查 `~/.codex/config.toml` 中的 `api_key` 是否正确；去对应平台重新生成 Key |
| `Connection refused` | 网络不通或 base_url 错误 | 检查 `base_url` 是否正确；确认电脑能访问外网；尝试 `curl <base_url>/models` |
| `git repository not found` | 不在 Git 仓库目录下 | 执行 `git init` 或使用 `--skip-git-repo-check` 参数 |
| `Node.js version not supported` | Node.js 版本过低 | 升级到 Node.js ≥ 18：`nvm install --lts` |
| `npm install` 权限错误 (Mac/Linux) | npm 全局安装需要 sudo | 配置 npm 前缀：`mkdir ~/.npm-global && npm config set prefix '~/.npm-global'`，然后加到 PATH |
| 执行超时（> 5 分钟） | 任务太复杂或网络慢 | 拆分任务为多个小步骤；检查网络延迟；用更快的模型（如 deepseek-v4-flash） |
| 生成代码有语法错误 | 模型输出不稳定 | 重新执行相同任务，或换一个模型；在提示词中强调"确保代码可运行" |
| 电脑休眠无法遥控 | 电源管理设置 | 参考 3.4 节，将电源设置改为"永不睡眠" |
| Windows 终端打不开 | Windows Terminal 未安装 | 从 Microsoft Store 安装 Windows Terminal，或用 `powershell` 替代 |
| 遥控输入文字乱码 | 输入法或编码问题 | 切换到英文输入法；用 `type-text` 发送纯 ASCII 字符 |
| `wire_api` 协议不兼容 | 某些提供商不支持 Responses API | 尝试 `wire_api = "chat"` 或联系提供商确认 API 兼容性 |

---

## 六、配置参考

### 完整 config.toml 示例（多 Provider）

```toml
model = "deepseek-v4-flash"
model_provider = "deepseek"

# 可选：自动压缩长上下文，节省 Token
auto_compact_threshold = 120000

# 可选：推理深度（low/medium/high）
reasoning_effort = "medium"

# ===== DeepSeek =====
[model_providers.deepseek]
name = "DeepSeek"
base_url = "https://api.deepseek.com/v1"
wire_api = "responses"
env_key = "DEEPSEEK_API_KEY"

# ===== OpenRouter（备用） =====
[model_providers.openrouter]
name = "OpenRouter"
base_url = "https://openrouter.ai/api/v1"
wire_api = "responses"
env_key = "OPENROUTER_API_KEY"

# ===== 硅基流动（备用，国内） =====
[model_providers.siliconflow]
name = "SiliconFlow"
base_url = "https://api.siliconflow.cn/v1"
wire_api = "responses"
env_key = "SILICONFLOW_API_KEY"
```

### 切换模型

```bash
# 临时切换（单次执行）
codex exec "你的任务" --model deepseek-v4-flash

# 永久切换：修改 config.toml 顶层的 model 字段（不是 [default] 段）
```

### 查看当前配置

```bash
codex config list
```

---

## 输入

用户描述需要 CodeX CLI 执行的任务，包含：
- 要做什么（写代码 / 改 Bug / 跑分析 / 生成报告）
- 在哪个项目目录下执行（可选）
- 编程语言偏好（默认 Python）
- 特殊约束（可选）

## 输出

- CodeX CLI 执行结果（代码内容、运行输出、生成的文件等）
- 生成的文件路径

---

## 注意事项

1. **API 费用**：CodeX CLI 通过你配置的 API 提供商调用模型，费用由对应平台收取，与 CodeX CLI 本身无关
2. **电脑必须开机**：远程遥控的前提是电脑处于开机状态
3. **安全提示**：API Key 是敏感信息，建议使用环境变量 `${VAR}` 方式引用，不要明文写在配置文件中
4. **模型选择**：日常任务推荐 `deepseek-v4-flash`（¥2/百万Token），复杂任务用 `deepseek-chat`（¥8/百万Token）或 `gpt-4.1`
5. **网络要求**：电脑需要能访问对应 API 提供商的服务器（国内用户推荐硅基流动或 DeepSeek 官方）