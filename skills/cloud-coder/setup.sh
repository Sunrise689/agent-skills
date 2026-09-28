#!/bin/bash
# 云编程 Cloud Coding · 安装引导脚本
# 检测环境并引导安装 OpenCode / CodeX CLI

set -e

echo "=== 云编程 Cloud Coding ==="
echo ""

# 环境检测
check_node() {
    if command -v node &> /dev/null; then
        NODE_VER=$(node -v 2>&1 | sed 's/v//' | cut -d'.' -f1)
        if [ "$NODE_VER" -ge 18 ]; then
            echo "✅ Node.js: $(node -v)"
            return 0
        fi
    fi
    echo "❌ 需要 Node.js 18+，当前: $(node -v 2>/dev/null || echo '未安装')"
    return 1
}

check_npm() {
    if command -v npm &> /dev/null; then
        echo "✅ npm: $(npm -v)"
        return 0
    fi
    echo "❌ 未检测到 npm"
    return 1
}

check_network() {
    if curl -s --connect-timeout 5 https://registry.npmjs.org/ > /dev/null 2>&1; then
        echo "✅ 网络可达"
        return 0
    fi
    echo "⚠️  境外 npm 不可达，将使用国内镜像"
    npm config set registry https://registry.npmmirror.com 2>/dev/null || true
    return 0
}

echo "环境预检..."
check_node || exit 1
check_npm || exit 1
check_network

echo ""
echo "环境就绪。在你的 Agent 对话中说："
echo "  - '安装 OpenCode'   → 安装开源云端编码引擎"
echo "  - '安装 CodeX CLI'   → 安装 OpenAI 编码引擎"
echo "  - '两个都要'         → 同时安装两者"
echo ""
echo "然后提供你的 DeepSeek/OpenRouter API Key，一键完成安装。"
echo "=== 预检通过 ==="
