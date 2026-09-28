---
name: cloud-coder
description: 一键给智能体装上云端编码引擎——OpenCode（开源免费）或 CodeX CLI（OpenAI生态），单选双选都行。装完即用：自然语言说需求，引擎自动走完代码生成→测试→修复→交付闭环。不换模型、不加API成本，靠编码引擎外挂让基础模型产出高级代码。已适配DeepSeek V4 Flash（约¥2/百万Token），也支持硅基流动、OpenRouter。覆盖代码生成、多文件重构、脚本编写、复杂架构4大高频场景。安装仅3步：选引擎→贴API Key→自然语言驱动。当用户提到"安装云编程""编码引擎""装OpenCode""装CodeX""代码外挂""提升代码质量""云端写代码""代码加速器""安装编码工具"等意图时使用。
---

# 云编程 Cloud Coding

给你的智能体装上云端编码引擎——OpenCode 还是 CodeX，你挑，我装。

**用法极简：选引擎 → 粘贴 API Key → 自然语言提需求 → 等着拿代码。** 装在 workspace 目录下，会话结束不丢失。

---

## 第一步：问用户选引擎

加载本技能后，先不要直接装任何东西。用下面这段话问用户：

> 你想装哪个云端编码引擎？可以单选，也可以两个都要。我帮你介绍一下：
>
> 🧠 **OpenCode**（开源免费，推荐）
> - 基于 DeepSeek V4 Flash，代码能力出色
> - 轻量快速，新用户送免费额度
> - 擅长：代码生成、多文件项目、重构、调试
> - 适合：日常编码、脚本编写、中小型项目
>
> 🤖 **CodeX CLI**（OpenAI 生态，功能更全面）
> - 原生 Responses API，Agent 工具调用
> - 擅长：复杂架构、自动化测试、CI/CD 流水线
> - 适合：大型项目、企业级开发、重度编码
>
> 📦 **两个都要**— 日常轻量任务用 OpenCode（省钱快），复杂项目用 CodeX（能力强），互补搭配。
>
> 两者的 Key 都能免费领。你选哪个？1️⃣ OpenCode  2️⃣ CodeX  3️⃣ 两个都要。把 API Key 发我，一键装好。

等用户回复选择后，进入第二步。

---

## 第二步：环境预检

安装前先跑这段，确保沙箱环境没问题：

```bash
echo "=== 云编程 Cloud Coding · 环境预检 ==="

# 1. 检查 Node.js（必需）
if command -v node &> /dev/null; then
  NODE_VER=$(node --version 2>&1)
  echo "✅ Node.js: $NODE_VER"
  MAJOR=$(echo "$NODE_VER" | sed 's/^v//' | cut -d'.' -f1)
  if [ "$MAJOR" -lt 18 ]; then
    echo "❌ Node.js 版本过低（需 ≥18），当前 $NODE_VER"
    echo "   提示：请在支持 Node 18+ 的扣子沙箱中使用本技能"
    exit 1
  fi
else
  echo "❌ 未检测到 Node.js"
  echo "   提示：当前沙箱不支持 Node.js，本技能需要 Node 18+ 环境"
  exit 1
fi

# 2. 检查 npm
if command -v npm &> /dev/null; then
  echo "✅ npm: $(npm --version 2>&1)"
else
  echo "❌ 未检测到 npm"
  exit 1
fi

# 3. 检查 workspace 可写（持久化目录）
WORKSPACE_DIR="$(pwd)"
if [ ! -w "$WORKSPACE_DIR" ]; then
  echo "❌ workspace 目录不可写: $WORKSPACE_DIR"
  exit 1
fi
echo "✅ workspace 可写: $WORKSPACE_DIR"

# 4. 检查磁盘空间（至少 500MB）
AVAIL_KB=$(df "$WORKSPACE_DIR" 2>/dev/null | tail -1 | awk '{print $4}')
if [ -n "$AVAIL_KB" ] && [ "$AVAIL_KB" -lt 512000 ]; then
  echo "⚠️  磁盘空间不足 500MB (可用 ${AVAIL_KB}KB)，安装可能失败"
fi

# 5. 检查网络（连 npm registry）
if curl -s --connect-timeout 5 https://registry.npmjs.org/ > /dev/null 2>&1; then
  echo "✅ 网络可达: npm registry"
else
  echo "⚠️  npm registry 不可达，尝试国内镜像..."
  npm config set registry https://registry.npmmirror.com 2>/dev/null
  if curl -s --connect-timeout 5 https://registry.npmmirror.com/ > /dev/null 2>&1; then
    echo "✅ 已切换至 npmmirror 镜像"
  else
    echo "❌ 网络不通，无法安装"
    exit 1
  fi
fi

echo "=== 预检通过，开始安装 ==="
```

---

## 第三步：安装

### 通用安装函数

以下逻辑同时用于 OpenCode 和 CodeX。核心策略：

1. **装到 workspace 的 `./tools/` 下** — 扣子沙箱唯一持久化目录
2. **已装则跳过** — 检测到已有安装直接返回
3. **安装失败自动重试 2 次** — 网络波动容错
4. **npm 走国内镜像** — 境外 registry 不可达时自动降级

### 选 OpenCode

```bash
PKG_NAME="opencode-ai"
INSTALL_DIR="./tools/opencode"
BIN_PATH="$INSTALL_DIR/node_modules/.bin/opencode"
CONFIG_DIR=".opencode"

echo "=== 安装 OpenCode ==="

# 检查是否已安装（用 .install-ok 标记判断完整性）
INSTALL_OK="$INSTALL_DIR/.install-ok"
if [ -f "$INSTALL_OK" ] && [ -f "$BIN_PATH" ]; then
  echo "✅ OpenCode 已安装，跳过"
  "$BIN_PATH" --version 2>&1 || { echo "❌ 二进制验证失败"; rm -f "$INSTALL_OK"; exit 1; }
else
  # 清理可能残留的不完整安装
  [ -d "$INSTALL_DIR" ] && rm -rf "$INSTALL_DIR"
  echo "📦 安装 $PKG_NAME → $INSTALL_DIR"
  mkdir -p "$INSTALL_DIR"

  # 重试逻辑
  RETRY=0
  MAX_RETRY=2
  CUR_DIR="$(pwd)"
  while [ $RETRY -le $MAX_RETRY ]; do
    cd "$INSTALL_DIR"
    if [ ! -f "package.json" ]; then
      npm init -y > /dev/null 2>&1
    fi
    if npm install "$PKG_NAME"@latest --save 2>&1; then
      cd "$CUR_DIR"
      break
    else
      RETRY=$((RETRY+1))
      if [ $RETRY -le $MAX_RETRY ]; then
        echo "⚠️  第 ${RETRY} 次重试..."
        sleep 3
      else
        cd "$CUR_DIR"
        rm -rf "$INSTALL_DIR"
        echo "❌ 安装失败，已重试 $MAX_RETRY 次"
        echo "   请检查网络或手动执行: mkdir -p $INSTALL_DIR && cd $INSTALL_DIR && npm init -y && npm install $PKG_NAME@latest"
        exit 1
      fi
    fi
  done

  cd "$CUR_DIR"

  # 验证：二进制存在 + 版本可执行 + npm 包可查
  if [ -f "$BIN_PATH" ]; then
    if "$BIN_PATH" --version 2>&1; then
      if npm list "$PKG_NAME" --depth=0 2>&1 | grep -q "$PKG_NAME"; then
        touch "$INSTALL_OK"
        echo "✅ OpenCode 安装成功"
      else
        echo "❌ npm 包验证失败"
        rm -rf "$INSTALL_DIR"
        exit 1
      fi
    else
      echo "❌ 版本验证失败"
      rm -rf "$INSTALL_DIR"
      exit 1
    fi
  else
    echo "❌ 安装后未找到二进制: $BIN_PATH"
    rm -rf "$INSTALL_DIR"
    exit 1
  fi
fi

# 写入配置
# ⚠️ 关键：执行本段前，必须先把 heredoc 中的 apiKey 占位符 "用户提供的Key"
#    替换为用户实际提供的 API Key（用 sed 或直接改 heredoc 内容）。
#    否则 config.json 里是无效占位符，引擎会 401。
mkdir -p "$CONFIG_DIR"
if [ ! -f "$CONFIG_DIR/config.json" ]; then
  cat > "$CONFIG_DIR/config.json" << 'OPENDECONFIG'
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "deepseek": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "DeepSeek",
      "options": {
        "baseURL": "https://api.deepseek.com/v1",
        "apiKey": "用户提供的Key"
      },
      "models": {
        "deepseek-v4-flash": {
          "name": "DeepSeek V4 Flash",
          "limit": {
            "context": 1048576,
            "output": 16384
          }
        }
      }
    }
  },
  "model": "deepseek/deepseek-v4-flash",
  "small_model": "deepseek/deepseek-v4-flash"
}
OPENDECONFIG
  echo "✅ 配置已写入 $CONFIG_DIR/config.json"
else
  echo "✅ 配置文件已存在，跳过"
fi

echo "=== OpenCode 就绪 ==="
echo "   二进制: $BIN_PATH"
echo "   配置: $CONFIG_DIR/config.json"
echo "   调用: $BIN_PATH run --auto \"<你的需求>\""
```

> 其他 API 同理，在 `provider` 块中替换对应的 `baseURL` 和模型名即可。硅基流动填 `https://api.siliconflow.cn/v1`，OpenRouter 填 `https://openrouter.ai/api/v1`。

### 选 CodeX CLI

```bash
PKG_NAME="@openai/codex"
INSTALL_DIR="./tools/codex"
BIN_PATH="$INSTALL_DIR/node_modules/.bin/codex"
CONFIG_DIR=".codex"

echo "=== 安装 CodeX CLI ==="

# 检查是否已安装（用 .install-ok 标记判断完整性）
INSTALL_OK="$INSTALL_DIR/.install-ok"
if [ -f "$INSTALL_OK" ] && [ -f "$BIN_PATH" ]; then
  echo "✅ CodeX CLI 已安装，跳过"
  "$BIN_PATH" --version 2>&1 || { echo "❌ 二进制验证失败"; rm -f "$INSTALL_OK"; exit 1; }
else
  # 清理可能残留的不完整安装
  [ -d "$INSTALL_DIR" ] && rm -rf "$INSTALL_DIR"
  echo "📦 安装 $PKG_NAME → $INSTALL_DIR"
  mkdir -p "$INSTALL_DIR"

  RETRY=0
  MAX_RETRY=2
  CUR_DIR="$(pwd)"
  while [ $RETRY -le $MAX_RETRY ]; do
    cd "$INSTALL_DIR"
    if [ ! -f "package.json" ]; then
      npm init -y > /dev/null 2>&1
    fi
    if npm install "$PKG_NAME"@latest --save 2>&1; then
      cd "$CUR_DIR"
      break
    else
      RETRY=$((RETRY+1))
      if [ $RETRY -le $MAX_RETRY ]; then
        echo "⚠️  第 ${RETRY} 次重试..."
        sleep 3
      else
        cd "$CUR_DIR"
        rm -rf "$INSTALL_DIR"
        echo "❌ 安装失败，已重试 $MAX_RETRY 次"
        exit 1
      fi
    fi
  done

  cd "$CUR_DIR"

  if [ -f "$BIN_PATH" ]; then
    if "$BIN_PATH" --version 2>&1; then
      if npm list "$PKG_NAME" --depth=0 2>&1 | grep -q "$PKG_NAME"; then
        touch "$INSTALL_OK"
        echo "✅ CodeX CLI 安装成功"
      else
        echo "❌ npm 包验证失败"
        rm -rf "$INSTALL_DIR"
        exit 1
      fi
    else
      echo "❌ 版本验证失败"
      rm -rf "$INSTALL_DIR"
      exit 1
    fi
  else
    echo "❌ 安装后未找到二进制: $BIN_PATH"
    rm -rf "$INSTALL_DIR"
    exit 1
  fi
fi

# 写入配置
mkdir -p "$CONFIG_DIR"
if [ ! -f "$CONFIG_DIR/config.toml" ]; then
  cat > "$CONFIG_DIR/config.toml" << 'CODEXCONFIG'
model = "deepseek-v4-flash"
model_provider = "deepseek"
cli_auth_credentials_store = "file"

[model_providers.deepseek]
name = "DeepSeek"
base_url = "https://api.deepseek.com/v1"
wire_api = "responses"
env_key = "DEEPSEEK_API_KEY"
CODEXCONFIG
  echo "✅ 配置已写入 $CONFIG_DIR/config.toml"
else
  echo "✅ 配置文件已存在，跳过"
fi

# 设置环境变量
# ⚠️ 关键：同样需要先把占位符替换为用户实际提供的 Key，再 export。
#    注意 export 只对当前会话 shell 生效；config.toml 已通过 env_key 读取该变量。
export DEEPSEEK_API_KEY="用户提供的Key"

echo "=== CodeX CLI 就绪 ==="
echo "   二进制: $BIN_PATH"
echo "   配置: $CONFIG_DIR/config.toml"
echo "   调用: DEEPSEEK_API_KEY=你的Key $BIN_PATH exec \"<你的需求>\""
```

### 两个都要（OpenCode + CodeX）

把上面两个安装流程各执行一遍。两者互不冲突，都装在 `./tools/` 下各自目录中。装完效果：

- 日常轻量 → `./tools/opencode/node_modules/.bin/opencode run` 快速出活
- 复杂项目 → `./tools/codex/node_modules/.bin/codex exec` 深度处理
- 同一份 API Key 两边都能用

装完提醒用户：以后直接说需求，我来判断复杂度，自动选合适的引擎。

---

## 第四步：自然语言驱动

安装完成后，用户只需在对话中用自然语言描述需求。

### 任务路由

**简单任务**（单文件改、SQL、小脚本）→ 你直接处理。

**复杂任务**（多文件、重构、测试迭代）→ 调引擎：

```bash
# OpenCode
cd <项目目录> && ./tools/opencode/node_modules/.bin/opencode run --auto --format json "<任务>"

# CodeX
cd <项目目录> && ./tools/codex/node_modules/.bin/codex exec "<任务>"
```

### 自动闭环

引擎自动完成：生成代码 → 运行测试 → 失败就修复 → 再测 → 通过后交付。

---

## 故障速查

| 现象 | 原因 | 解决 |
|------|------|------|
| `❌ 未检测到 Node.js` | 沙箱无 Node | 切换到支持 Node 的扣子沙箱 |
| `❌ Node.js 版本过低` | 低于 v18 | 同上 |
| `❌ npm registry 不可达` | 境外网络不通 | 已自动切换 npmmirror 镜像 |
| `❌ 安装失败，已重试 2 次` | 持续网络问题 | 检查网络，稍后重试 |
| `❌ 安装后未找到二进制` | npm 包结构变化 | 检查包名和版本，更新技能 |
| `✅ 已安装，跳过` | 上次装过了 | 正常，直接用 |
| `⚠️ .install-ok 丢失但二进制存在` | 标记文件被清理 | 重新安装以恢复标记 |
| 配置不生效 | API Key 未替换 | 确认 Key 已写入配置文件 |

---

## 免费 API Key 获取

| 服务 | 链接 | 说明 |
|------|------|------|
| DeepSeek | https://platform.deepseek.com | 新用户送额度，V4 Flash 代码强劲 |
| 硅基流动 | https://cloud.siliconflow.cn | 国产模型丰富 |
| OpenRouter | https://openrouter.ai | 聚合平台，可接 Luna |

---

## 许可

MIT 开源。本技能为引导式安装工具，不捆绑第三方代码。
