#!/usr/bin/env bash
# =============================================================================
# CodeX Meta — 安装脚本 (Mac / Linux)
# 一键安装 CodeX CLI + 配置 API Key
# =============================================================================
set -euo pipefail

# --- 颜色输出 ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

log_info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
log_ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }
log_step()  { echo ""; echo -e "${CYAN}========================================${NC}"; echo -e "${CYAN}  $*${NC}"; echo -e "${CYAN}========================================${NC}"; }

# --- 检测操作系统 ---
detect_os() {
    case "$(uname -s)" in
        Darwin)  OS="macOS" ;;
        Linux)   OS="Linux" ;;
        MINGW*|MSYS*|CYGWIN*) OS="Windows" ;;
        *)       OS="Unknown" ;;
    esac
    log_info "检测到操作系统: ${OS}"
}

# --- 检查 Node.js ---
check_node() {
    log_step "第一步：检查 Node.js 环境"

    if command -v node &> /dev/null; then
        NODE_VERSION=$(node --version)
        NODE_MAJOR=$(echo "$NODE_VERSION" | sed 's/v//' | cut -d. -f1)
        log_ok "Node.js 已安装: ${NODE_VERSION}"

        if [ "$NODE_MAJOR" -lt 18 ]; then
            log_error "Node.js 版本过低（当前 ${NODE_MAJOR}，需要 ≥ 18）"
            log_info "请升级 Node.js："
            log_info "  - nvm: nvm install --lts && nvm use --lts"
            log_info "  - Homebrew (Mac): brew upgrade node"
            log_info "  - 官网: https://nodejs.org"
            exit 1
        fi
    else
        log_error "Node.js 未安装"
        log_info "请先安装 Node.js ≥ 18："
        log_info "  - Mac:  brew install node"
        log_info "  - Linux: curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.0/install.sh | bash && nvm install --lts"
        log_info "  - 官网:  https://nodejs.org"
        exit 1
    fi

    if command -v npm &> /dev/null; then
        NPM_VERSION=$(npm --version)
        log_ok "npm 已安装: v${NPM_VERSION}"
    else
        log_error "npm 未安装（通常随 Node.js 一起安装）"
        exit 1
    fi
}

# --- 检查 Git ---
check_git() {
    if command -v git &> /dev/null; then
        GIT_VERSION=$(git --version)
        log_ok "Git 已安装: ${GIT_VERSION}"
    else
        log_warn "Git 未安装（推荐安装，CodeX CLI 默认需要在 Git 仓库下运行）"
        log_info "安装 Git:"
        log_info "  - Mac:  brew install git"
        log_info "  - Ubuntu: sudo apt install git -y"
        log_info "  - 官网: https://git-scm.com"
    fi
}

# --- 安装 CodeX CLI ---
install_codex() {
    log_step "第二步：安装 CodeX CLI"

    if command -v codex &> /dev/null; then
        CODEX_VERSION=$(codex --version 2>&1 || echo "unknown")
        log_ok "CodeX CLI 已安装: ${CODEX_VERSION}"
        log_info "如需重新安装，请先卸载: npm uninstall -g @openai/codex"
        return 0
    fi

    log_info "正在通过 npm 全局安装 @openai/codex..."
    if npm install -g @openai/codex 2>&1; then
        log_ok "CodeX CLI 安装成功"
    else
        log_error "CodeX CLI 安装失败"
        log_info "常见解决方案："
        log_info "  1. 检查网络连接"
        log_info "  2. 如遇到权限问题，尝试配置 npm 全局目录："
        log_info "     mkdir ~/.npm-global && npm config set prefix '~/.npm-global'"
        log_info "     echo 'export PATH=~/.npm-global/bin:\$PATH' >> ~/.bashrc"
        log_info "     source ~/.bashrc"
        log_info "  3. 重新运行此脚本"
        exit 1
    fi
}

# --- 配置 API Key ---
configure_api() {
    log_step "第三步：配置 API Key"

    CONFIG_DIR="${HOME}/.codex"
    CONFIG_FILE="${CONFIG_DIR}/config.toml"

    # 如果已存在配置文件
    if [ -f "$CONFIG_FILE" ]; then
        log_ok "配置文件已存在: ${CONFIG_FILE}"
        log_info "如需重新配置，请删除后重试: rm ${CONFIG_FILE}"
        echo ""
        cat "$CONFIG_FILE"
        return 0
    fi

    echo ""
    echo "  请选择 API 提供商："
    echo "  ┌────┬─────────────────────────────────┐"
    echo "  │ 1  │ DeepSeek（推荐，¥2/百万Token）     │"
    echo "  │ 2  │ OpenRouter（多模型聚合）            │"
    echo "  │ 3  │ 硅基流动 SiliconFlow（国内低延迟）  │"
    echo "  │ 4  │ OpenAI 官方                        │"
    echo "  │ 5  │ Grok (xAI)                         │"
    echo "  │ 6  │ 本地 Ollama（免费，完全离线）        │"
    echo "  │ 7  │ 自定义（手动输入 base_url）         │"
    echo "  └────┴─────────────────────────────────┘"
    echo ""

    read -r -p "  请输入数字 (1-7): " PROVIDER_CHOICE

    mkdir -p "$CONFIG_DIR"

    case "$PROVIDER_CHOICE" in
        1)
            read -r -p "  请输入 DeepSeek API Key: " API_KEY
            cat > "$CONFIG_FILE" << 'TOML_EOF'
model = "deepseek-v4-flash"
model_provider = "deepseek"

[model_providers.deepseek]
name = "DeepSeek"
base_url = "https://api.deepseek.com/v1"
wire_api = "responses"
TOML_EOF
            echo "api_key = \"${API_KEY}\"" >> "$CONFIG_FILE"
            log_ok "已配置 DeepSeek"
            log_info "获取 Key: https://platform.deepseek.com/api_keys"
            ;;
        2)
            read -r -p "  请输入 OpenRouter API Key: " API_KEY
            cat > "$CONFIG_FILE" << 'TOML_EOF'
model = "openai/gpt-4.1"
model_provider = "openrouter"

[model_providers.openrouter]
name = "OpenRouter"
base_url = "https://openrouter.ai/api/v1"
wire_api = "responses"
TOML_EOF
            echo "api_key = \"${API_KEY}\"" >> "$CONFIG_FILE"
            log_ok "已配置 OpenRouter"
            log_info "获取 Key: https://openrouter.ai/keys"
            ;;
        3)
            read -r -p "  请输入硅基流动 API Key: " API_KEY
            cat > "$CONFIG_FILE" << 'TOML_EOF'
model = "deepseek-ai/DeepSeek-V3"
model_provider = "siliconflow"

[model_providers.siliconflow]
name = "SiliconFlow"
base_url = "https://api.siliconflow.cn/v1"
wire_api = "responses"
TOML_EOF
            echo "api_key = \"${API_KEY}\"" >> "$CONFIG_FILE"
            log_ok "已配置硅基流动"
            log_info "获取 Key: https://siliconflow.cn"
            ;;
        4)
            read -r -p "  请输入 OpenAI API Key: " API_KEY
            cat > "$CONFIG_FILE" << 'TOML_EOF'
model = "gpt-4.1"
model_provider = "openai"

[model_providers.openai]
name = "OpenAI"
base_url = "https://api.openai.com/v1"
wire_api = "responses"
TOML_EOF
            echo "api_key = \"${API_KEY}\"" >> "$CONFIG_FILE"
            log_ok "已配置 OpenAI"
            ;;
        5)
            read -r -p "  请输入 Grok API Key: " API_KEY
            cat > "$CONFIG_FILE" << 'TOML_EOF'
model = "grok-3"
model_provider = "grok"

[model_providers.grok]
name = "Grok"
base_url = "https://api.x.ai/v1"
wire_api = "responses"
TOML_EOF
            echo "api_key = \"${API_KEY}\"" >> "$CONFIG_FILE"
            log_ok "已配置 Grok (xAI)"
            ;;
        6)
            read -r -p "  请输入 Ollama 模型名（默认: qwen2.5-coder:7b）: " OLLAMA_MODEL
            OLLAMA_MODEL="${OLLAMA_MODEL:-qwen2.5-coder:7b}"
            cat > "$CONFIG_FILE" << TOML_EOF
model = "${OLLAMA_MODEL}"
model_provider = "ollama"

[model_providers.ollama]
name = "Ollama"
base_url = "http://localhost:11434/v1"
wire_api = "responses"
TOML_EOF
            log_ok "已配置本地 Ollama"
            log_info "确保 Ollama 已安装且模型已拉取: ollama pull ${OLLAMA_MODEL}"
            ;;
        7)
            read -r -p "  请输入 Provider 名称: " CUSTOM_PROVIDER
            read -r -p "  请输入 base_url: " CUSTOM_BASE_URL
            read -r -p "  请输入模型名: " CUSTOM_MODEL
            read -r -p "  请输入 API Key: " CUSTOM_API_KEY
            cat > "$CONFIG_FILE" << TOML_EOF
model = "${CUSTOM_MODEL}"
model_provider = "${CUSTOM_PROVIDER}"

[model_providers.${CUSTOM_PROVIDER}]
name = "${CUSTOM_PROVIDER}"
base_url = "${CUSTOM_BASE_URL}"
wire_api = "responses"
api_key = "${CUSTOM_API_KEY}"
TOML_EOF
            log_ok "已配置自定义 Provider: ${CUSTOM_PROVIDER}"
            ;;
        *)
            log_error "无效选择，跳过配置"
            log_info "你可以稍后手动编辑: ${CONFIG_FILE}"
            ;;
    esac

    echo ""
    log_info "配置文件已保存到: ${CONFIG_FILE}"
    echo "---"
    cat "$CONFIG_FILE"
    echo "---"
}

# --- 验证安装 ---
verify_installation() {
    log_step "第四步：验证安装"

    if command -v codex &> /dev/null; then
        CODEX_VERSION=$(codex --version 2>&1)
        log_ok "CodeX CLI 版本: ${CODEX_VERSION}"
    else
        log_error "CodeX CLI 命令未找到，安装可能失败"
        log_info "请检查 PATH 配置或重新安装"
        exit 1
    fi

    if [ -f "$HOME/.codex/config.toml" ]; then
        log_ok "配置文件存在: ~/.codex/config.toml"
    else
        log_warn "配置文件未找到，请手动创建 ~/.codex/config.toml"
    fi

    log_info "运行快速测试..."
    echo ""

    if codex exec --skip-git-repo-check "用 Python 打印 'Hello from CodeX Meta!'" 2>&1; then
        log_ok "测试通过！CodeX Meta 安装成功 🎉"
    else
        log_warn "测试执行遇到问题，但 CLI 已安装。请检查 API Key 配置和网络"
    fi
}

# --- 完成 ---
show_done() {
    log_step "安装完成 ✅"
    echo ""
    echo "  🚀 CodeX Meta 已就绪！"
    echo ""
    echo "  快速开始："
    echo "    codex exec \"用 Python 写一个计算器\""
    echo ""
    echo "  更多用法："
    echo "    codex --help"
    echo ""
    echo "  从手机/平板遥控你的电脑："
    echo "    通过 desktop-control-win (Windows) 或 SSH (Mac/Linux)"
    echo "    远程操控终端执行 codex exec 命令"
    echo ""
    echo "  切换模型："
    echo "    编辑 ~/.codex/config.toml 修改顶层的 model 字段"
    echo ""
}

# =============================================================================
# 主流程
# =============================================================================
main() {
    echo ""
    echo -e "${CYAN}╔══════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║        CodeX Meta — 安装脚本                ║${NC}"
    echo -e "${CYAN}║    本地 CodeX CLI + 远程遥控编码引擎        ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════╝${NC}"
    echo ""

    detect_os
    check_node
    check_git
    install_codex
    configure_api
    verify_installation
    show_done
}

main "$@"