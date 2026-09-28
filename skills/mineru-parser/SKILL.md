---
name: mineru-parser
description: 文档大师——把 PDF、Word、PPT、Excel、扫描件、图片全转成 LLM 能直接读的 Markdown。不需要模型内置多模态能力，任何模型都能理解你的文件。表格保留 HTML 结构，公式转 LaTeX，版面按阅读顺序还原。识别准确率远超通用 OCR，专为 RAG、知识库、论文阅读、财报分析场景优化。当用户需要解析文档、提取文件内容、把文件转成可读文本时使用。
---

# 文档大师 Files Master

把任何文件变成 LLM 能读的文字——PDF、Word、PPT、Excel、扫描件、图片，统统转成结构化 Markdown。

**核心理念：让你的模型不需要"眼睛"。** 不管用的模型能不能读图、有没有多模态，文件内容都能喂进去。底层引擎是上海 AI 实验室开源的 MinerU，比普通 OCR 准确率高得多——表格结构、数学公式、阅读顺序都给你保留好。

---

## 为什么用文档大师？

| 对比 | 普通 OCR | 文档大师 |
|------|---------|---------|
| 表格 | 碎成一堆文字 | HTML 表格，结构完整 |
| 公式 | 乱码或丢失 | LaTeX，可直接渲染 |
| 版面 | 从上到下机械提取 | 按阅读顺序智能排列 |
| 扫描件 | 需要额外工具 | 内置 109 语言 OCR |
| 输出 | 纯文本 | Markdown / JSON / HTML |

---

## 支持的格式

### 输入

| 格式 | 扩展名 | 说明 |
|------|--------|------|
| PDF | `.pdf` | 文本型/扫描型/图层型全支持 |
| Word | `.docx` | 原生解析，不转 PDF |
| PowerPoint | `.pptx` | 幻灯片结构保留 |
| Excel | `.xlsx` | Flash 模式输出 HTML 表格 |
| 图片 | `.jpg .png .webp .gif .bmp` | 自动 OCR |

### 输出

- **Markdown** — 最常用，直接喂给 LLM
- **JSON** — 结构化数据，程序处理
- **HTML** — 表格/版面完整保留

---

## 使用方式

### 快速开始

```bash
# 解析 PDF 链接
node scripts/parse.js --url "https://example.com/paper.pdf"

# 解析本地文件 + 开启 OCR + 公式识别
node scripts/parse.js --file "./扫描件.pdf" --ocr --formula

# 批量解析整个目录
node scripts/parse.js --dir "./docs" --output "./result"

# 输出 JSON（含结构化数据）
node scripts/parse.js --file "./report.pdf" --format json
```

### 常用命令速查

```bash
# 扫描件 PDF（必须开 OCR）
node scripts/parse.js --file "./scan.pdf" --ocr --lang ch+en

# 学术论文（开启公式识别）
node scripts/parse.js --file "./paper.pdf" --formula --model vlm

# 财报（保留表格 HTML）
node scripts/parse.js --file "./财报.pdf" --format html

# 提取指定页
node scripts/parse.js --file "./book.pdf" --pages "10-25,30,35-40"
```

---

## 配置凭证

1. 去 https://mineru.net/apiManage/token 免费申请 Token
2. 在技能配置页填入 `MINERU_API_KEY`

无需付费，免费额度够日常使用。

---

## 故障速查

| 现象 | 原因 | 解决 |
|------|------|------|
| `❌ 未配置 MINERU_API_KEY` | 没填 Token | 去 mineru.net 申请免费 Token |
| `❌ 文件不存在` | 路径写错 | 检查文件路径 |
| API 超时 | 文件太大或网络慢 | 文件保持在 10MB 以下，或用 `--pages` 分批 |
| 扫描件识别差 | 没开 OCR | 加 `--ocr` 参数 |
| 公式乱码 | 没开公式识别 | 加 `--formula` 参数 |
| 批量处理中断 | 某个文件失败 | 会自动跳过继续处理下一个 |

---

## 许可

基于 MinerU (AGPL-3.0)，上海 AI 实验室 OpenDataLab 开源。商用请遵守协议。
