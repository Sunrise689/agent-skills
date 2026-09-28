# =============================================================================
# CodeX Meta — 安装脚本 (Windows PowerShell)
# 一键安装 CodeX CLI + 配置 API Key
# 用法: powershell -ExecutionPolicy Bypass -File install.ps1
# =============================================================================
param()

$ErrorActionPreference = "Stop"

# --- 颜色输出 ---
function Write-Info  { Write-Host "[INFO]  " -ForegroundColor Blue   -NoNewline; Write-Host $args }
function Write-OK    { Write-Host "[OK]    " -ForegroundColor Green  -NoNewline; Write-Host $args }
function Write-Warn  { Write-Host "[WARN]  " -ForegroundColor Yellow -NoNewline; Write-Host $args }
function Write-Error2 { Write-Host "[ERROR] " -ForegroundColor Red    -NoNewline; Write-Host $args }
function Write-Step  {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  $args" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
}

# --- 检测操作系统 ---
function Detect-OS {
    $osInfo = Get-CimInstance -ClassName Win32_OperatingSystem
    Write-Info "检测到操作系统: $($osInfo.Caption)"
    Write-Info "架构: $env:PROCESSOR_ARCHITECTURE"
}

# --- 检查 Node.js ---
function Check-Node {
    Write-Step "第一步：检查 Node.js 环境"

    try {
        $nodeVersion = node --version 2>&1
        $nodeMajor = [int]($nodeVersion -replace 'v','' -replace '\..*','')
        Write-OK "Node.js 已安装: $nodeVersion"

        if ($nodeMajor -lt 18) {
            Write-Error2 "Node.js 版本过低（当前 $nodeMajor，需要 ≥ 18）"
            Write-Info "请升级 Node.js："
            Write-Info "  - 官网下载 LTS: https://nodejs.org"
            Write-Info "  - 或使用 nvm-windows: https://github.com/coreybutler/nvm-windows"
            exit 1
        }
    } catch {
        Write-Error2 "Node.js 未安装"
        Write-Info "请先安装 Node.js ≥ 18："
        Write-Info "  - 官网下载: https://nodejs.org (选择 LTS 版本)"
        Write-Info "  - 安装后重启 PowerShell 再运行此脚本"
        exit 1
    }

    try {
        $npmVersion = npm --version 2>&1
        Write-OK "npm 已安装: v$npmVersion"
    } catch {
        Write-Error2 "npm 未安装"
        exit 1
    }
}

# --- 检查 Git ---
function Check-Git {
    try {
        $gitVersion = git --version 2>&1
        Write-OK "Git 已安装: $gitVersion"
    } catch {
        Write-Warn "Git 未安装（推荐安装，CodeX CLI 默认需要在 Git 仓库下运行）"
        Write-Info "安装 Git: https://git-scm.com/download/win"
    }
}

# --- 安装 CodeX CLI ---
function Install-Codex {
    Write-Step "第二步：安装 CodeX CLI"

    try {
        $codexVersion = codex --version 2>&1
        Write-OK "CodeX CLI 已安装: $codexVersion"
        Write-Info "如需重新安装，请先卸载: npm uninstall -g @openai/codex"
        return
    } catch {
        # 未安装，继续
    }

    Write-Info "正在通过 npm 全局安装 @openai/codex..."
    try {
        npm install -g @openai/codex 2>&1 | Out-Host
        if ($LASTEXITCODE -eq 0) {
            Write-OK "CodeX CLI 安装成功"
        } else {
            throw "npm install failed"
        }
    } catch {
        Write-Error2 "CodeX CLI 安装失败"
        Write-Info "常见解决方案："
        Write-Info "  1. 检查网络连接"
        Write-Info "  2. 以管理员身份运行 PowerShell 再执行此脚本"
        Write-Info "  3. 如遇权限问题，尝试配置 npm 全局目录："
        Write-Info "     npm config set prefix `"$env:USERPROFILE\.npm-global`""
        Write-Info "     然后将该目录添加到 PATH 环境变量"
        exit 1
    }
}

# --- 配置 API Key ---
function Configure-API {
    Write-Step "第三步：配置 API Key"

    $ConfigDir = "$env:USERPROFILE\.codex"
    $ConfigFile = "$ConfigDir\config.toml"

    if (Test-Path $ConfigFile) {
        Write-OK "配置文件已存在: $ConfigFile"
        Write-Info "如需重新配置，请删除后重试: Remove-Item $ConfigFile"
        Write-Host ""
        Get-Content $ConfigFile | Write-Host
        return
    }

    Write-Host ""
    Write-Host "  请选择 API 提供商："
    Write-Host "  ┌────┬─────────────────────────────────┐"
    Write-Host "  │ 1  │ DeepSeek（推荐，¥2/百万Token）     │"
    Write-Host "  │ 2  │ OpenRouter（多模型聚合）            │"
    Write-Host "  │ 3  │ 硅基流动 SiliconFlow（国内低延迟）  │"
    Write-Host "  │ 4  │ OpenAI 官方                        │"
    Write-Host "  │ 5  │ Grok (xAI)                         │"
    Write-Host "  │ 6  │ 本地 Ollama（免费，完全离线）        │"
    Write-Host "  │ 7  │ 自定义（手动输入 base_url）         │"
    Write-Host "  └────┴─────────────────────────────────┘"
    Write-Host ""

    $choice = Read-Host "  请输入数字 (1-7)"

    if (-not (Test-Path $ConfigDir)) {
        New-Item -ItemType Directory -Path $ConfigDir -Force | Out-Null
    }

    switch ($choice) {
        "1" {
            $apiKey = Read-Host "  请输入 DeepSeek API Key"
            @"
model = "deepseek-v4-flash"
model_provider = "deepseek"

[model_providers.deepseek]
name = "DeepSeek"
base_url = "https://api.deepseek.com/v1"
wire_api = "responses"
api_key = "$apiKey"
"@ | Out-File -FilePath $ConfigFile -Encoding UTF8
            Write-OK "已配置 DeepSeek"
            Write-Info "获取 Key: https://platform.deepseek.com/api_keys"
        }
        "2" {
            $apiKey = Read-Host "  请输入 OpenRouter API Key"
            @"
model = "openai/gpt-4.1"
model_provider = "openrouter"

[model_providers.openrouter]
name = "OpenRouter"
base_url = "https://openrouter.ai/api/v1"
wire_api = "responses"
api_key = "$apiKey"
"@ | Out-File -FilePath $ConfigFile -Encoding UTF8
            Write-OK "已配置 OpenRouter"
            Write-Info "获取 Key: https://openrouter.ai/keys"
        }
        "3" {
            $apiKey = Read-Host "  请输入硅基流动 API Key"
            @"
model = "deepseek-ai/DeepSeek-V3"
model_provider = "siliconflow"

[model_providers.siliconflow]
name = "SiliconFlow"
base_url = "https://api.siliconflow.cn/v1"
wire_api = "responses"
api_key = "$apiKey"
"@ | Out-File -FilePath $ConfigFile -Encoding UTF8
            Write-OK "已配置硅基流动"
            Write-Info "获取 Key: https://siliconflow.cn"
        }
        "4" {
            $apiKey = Read-Host "  请输入 OpenAI API Key"
            @"
model = "gpt-4.1"
model_provider = "openai"

[model_providers.openai]
name = "OpenAI"
base_url = "https://api.openai.com/v1"
wire_api = "responses"
api_key = "$apiKey"
"@ | Out-File -FilePath $ConfigFile -Encoding UTF8
            Write-OK "已配置 OpenAI"
        }
        "5" {
            $apiKey = Read-Host "  请输入 Grok API Key"
            @"
model = "grok-3"
model_provider = "grok"

[model_providers.grok]
name = "Grok"
base_url = "https://api.x.ai/v1"
wire_api = "responses"
api_key = "$apiKey"
"@ | Out-File -FilePath $ConfigFile -Encoding UTF8
            Write-OK "已配置 Grok (xAI)"
        }
        "6" {
            $ollamaModel = Read-Host "  请输入 Ollama 模型名（默认: qwen2.5-coder:7b）"
            if (-not $ollamaModel) { $ollamaModel = "qwen2.5-coder:7b" }
            @"
model = "$ollamaModel"
model_provider = "ollama"

[model_providers.ollama]
name = "Ollama"
base_url = "http://localhost:11434/v1"
wire_api = "responses"
"@ | Out-File -FilePath $ConfigFile -Encoding UTF8
            Write-OK "已配置本地 Ollama"
            Write-Info "确保 Ollama 已安装且模型已拉取: ollama pull $ollamaModel"
        }
        "7" {
            $customProvider = Read-Host "  请输入 Provider 名称"
            $customBaseUrl = Read-Host "  请输入 base_url"
            $customModel = Read-Host "  请输入模型名"
            $customApiKey = Read-Host "  请输入 API Key"
            @"
model = "$customModel"
model_provider = "$customProvider"

[model_providers.$customProvider]
name = "$customProvider"
base_url = "$customBaseUrl"
wire_api = "responses"
api_key = "$customApiKey"
"@ | Out-File -FilePath $ConfigFile -Encoding UTF8
            Write-OK "已配置自定义 Provider: $customProvider"
        }
        default {
            Write-Error2 "无效选择，跳过配置"
            Write-Info "你可以稍后手动编辑: $ConfigFile"
        }
    }

    Write-Host ""
    Write-Info "配置文件已保存到: $ConfigFile"
    Write-Host "---"
    Get-Content $ConfigFile | Write-Host
    Write-Host "---"
}

# --- 验证安装 ---
function Verify-Installation {
    Write-Step "第四步：验证安装"

    try {
        $codexVer = codex --version 2>&1
        Write-OK "CodeX CLI 版本: $codexVer"
    } catch {
        Write-Error2 "CodeX CLI 命令未找到，安装可能失败"
        Write-Info "请检查 PATH 配置或重新安装"
        exit 1
    }

    $configFile = "$env:USERPROFILE\.codex\config.toml"
    if (Test-Path $configFile) {
        Write-OK "配置文件存在: $configFile"
    } else {
        Write-Warn "配置文件未找到，请手动创建 $configFile"
    }

    Write-Info "运行快速测试..."
    Write-Host ""

    try {
        codex exec --skip-git-repo-check "用 Python 打印 'Hello from CodeX Meta!'" 2>&1 | Out-Host
        if ($LASTEXITCODE -eq 0) {
            Write-OK "测试通过！CodeX Meta 安装成功 🎉"
        } else {
            Write-Warn "测试执行遇到问题，但 CLI 已安装。请检查 API Key 配置和网络"
        }
    } catch {
        Write-Warn "测试执行遇到问题，但 CLI 已安装。请检查 API Key 配置和网络"
    }
}

# --- 完成 ---
function Show-Done {
    Write-Step "安装完成 ✅"
    Write-Host ""
    Write-Host "  🚀 CodeX Meta 已就绪！"
    Write-Host ""
    Write-Host "  快速开始："
    Write-Host '    codex exec "用 Python 写一个计算器"'
    Write-Host ""
    Write-Host "  更多用法："
    Write-Host "    codex --help"
    Write-Host ""
    Write-Host "  从手机/平板遥控你的电脑："
    Write-Host "    通过 desktop-control-win 远程操控终端执行 codex exec 命令"
    Write-Host ""
    Write-Host "  切换模型："
    Write-Host "    编辑 $env:USERPROFILE\.codex\config.toml 修改顶层的 model 字段"
    Write-Host ""
}

# =============================================================================
# 主流程
# =============================================================================
function Main {
    Write-Host ""
    Write-Host "╔══════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "║        CodeX Meta — 安装脚本                ║" -ForegroundColor Cyan
    Write-Host "║    本地 CodeX CLI + 远程遥控编码引擎        ║" -ForegroundColor Cyan
    Write-Host "╚══════════════════════════════════════════════╝" -ForegroundColor Cyan
    Write-Host ""

    Detect-OS
    Check-Node
    Check-Git
    Install-Codex
    Configure-API
    Verify-Installation
    Show-Done
}

Main