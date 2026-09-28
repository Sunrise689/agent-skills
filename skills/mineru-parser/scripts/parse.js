#!/usr/bin/env node
/**
 * 文档大师 Files Master · 文档解析 CLI
 * 基于 MinerU 云端 API，将任何文件转为 LLM 可读的结构化文本
 */

const { MinerU, saveAll } = require('mineru-open-sdk');
const fs = require('fs');
const path = require('path');
const { program } = require('commander');

// 从环境变量读取 API Key（扣子技能凭证优先）
function getApiKey() {
  return process.env.COZE_MINERU_API_KEY_7663336507444445227 ||
         process.env.MINERU_API_KEY ||
         process.env.MINERU_API_TOKEN ||
         process.env.MINERU_TOKEN;
}

// 带重试的 API 调用
async function withRetry(fn, maxRetries = 2, label = 'API') {
  for (let i = 0; i <= maxRetries; i++) {
    try {
      return await fn();
    } catch (error) {
      if (i < maxRetries) {
        console.error(`⚠️  ${label} 第 ${i + 1} 次失败，${2 - i} 秒后重试...`);
        await new Promise(r => setTimeout(r, 2000));
      } else {
        throw error;
      }
    }
  }
}

program
  .name('files-master')
  .description('文档大师 - PDF/Word/PPT/Excel/图片 → LLM 可读的 Markdown/JSON/HTML')
  .version('1.0.0');

program
  .option('-u, --url <string>', '远程文档 URL')
  .option('-f, --file <string>', '本地文件路径')
  .option('-d, --dir <string>', '批量处理目录')
  .option('--format <type>', '输出格式: markdown | json | html', 'markdown')
  .option('--ocr', '启用 OCR（扫描件必开）', false)
  .option('--formula', '启用公式识别', false)
  .option('--no-table', '禁用表格提取', false)
  .option('--pages <string>', '页码范围（如 1-5,8,10-12）')
  .option('--lang <string>', 'OCR 语言（ch/en/ch+en 等）', 'ch')
  .option('--model <type>', '解析模式: pipeline(快) | vlm(准)', 'pipeline')
  .option('-o, --output <dir>', '输出目录', './files-master-output')
  .option('--zip', '保存完整资源包（含图片/表格）；指定 --output 时默认即保存完整资源，本选项兼容保留', false)
  .action(async (options) => {
    const apiKey = getApiKey();
    if (!apiKey) {
      console.error('❌ 未配置 MINERU_API_KEY');
      console.error('   请去 https://mineru.net/apiManage/token 免费申请 Token');
      console.error('   然后在技能配置页填入 MINERU_API_KEY');
      process.exit(1);
    }

    const client = new MinerU(apiKey);
    const outputDir = options.output ? path.resolve(options.output) : null;

    // 支持的扩展名
    const SUPPORTED_EXTS = /\.(pdf|docx|pptx|xlsx|jpg|jpeg|png|webp|gif|bmp)$/i;

    async function processOne(source, label) {
      console.log(`\n🔄 处理: ${label}`);

      const result = await withRetry(async () => {
        const model = options.model === 'vlm' ? 'vlm' : 'pipeline';
        console.log(`   模式: ${model === 'vlm' ? 'VLM（高精度，耗 Token）' : 'Pipeline（快速，省 Token）'}`);
        const res = await client.extract(source, {
          model,
          ocr: options.ocr,
          formula: options.formula,
          table: options.table !== false,
          language: options.lang,
          // 注意：SDK 的 pages 参数是字符串（如 "1-5,8,10-12"），直接透传
          pages: options.pages || undefined,
          extraFormats: options.format !== 'markdown' ? [options.format] : undefined,
          timeout: 600
        });
        return res;
      }, 2, label);

      // 保存到文件（SDK 的 saveAll 会解包完整资源：Markdown + 图片 + JSON 等）
      if (outputDir) {
        await saveAll(result, outputDir);
        console.log(`✅ 结果已保存: ${outputDir}`);
      }

      // 标准输出
      if (options.format === 'json') {
        console.log(JSON.stringify({
          taskId: result.taskId,
          state: result.state,
          progress: result.progress,
          markdown: result.markdown,
          images: result.images?.map(img => ({ url: img.url, caption: img.caption })),
          contentList: result.contentList
        }, null, 2));
      } else if (options.format === 'html') {
        const html = result.html || result.markdown || '';
        console.log(html || '⚠️  无 HTML 输出，试试 --format markdown');
      } else {
        console.log(result.markdown || '⚠️  无 Markdown 输出，试试 --format json');
      }

      if (result.zipUrl) {
        console.log(`📦 资源包: ${result.zipUrl}`);
      }

      return result;
    }

    try {
      if (options.dir) {
        const dir = path.resolve(options.dir);
        if (!fs.existsSync(dir)) {
          console.error(`❌ 目录不存在: ${dir}`);
          process.exit(1);
        }

        const files = fs.readdirSync(dir)
          .filter(f => SUPPORTED_EXTS.test(f))
          .map(f => path.join(dir, f));

        if (files.length === 0) {
          console.log('⚠️  目录中没有支持的文件格式');
          process.exit(0);
        }

        console.log(`📁 发现 ${files.length} 个文件`);

        let success = 0;
        let failed = 0;
        for (const file of files) {
          try {
            await processOne(file, path.basename(file));
            success++;
          } catch (e) {
            console.error(`❌ ${path.basename(file)}: ${e.message}`);
            failed++;
          }
        }
        console.log(`\n✅ 完成: ${success} 成功, ${failed} 失败`);
      } else if (options.url) {
        await processOne(options.url, options.url);
      } else if (options.file) {
        const file = path.resolve(options.file);
        if (!fs.existsSync(file)) {
          console.error(`❌ 文件不存在: ${file}`);
          process.exit(1);
        }
        if (!SUPPORTED_EXTS.test(file)) {
          console.error(`❌ 不支持的文件格式: ${path.extname(file)}`);
          console.error('   支持的格式: PDF, DOCX, PPTX, XLSX, JPG, PNG, WEBP, GIF, BMP');
          process.exit(1);
        }
        await processOne(file, file);
      } else {
        console.log('文档大师 · 用法:');
        program.help();
      }
    } catch (error) {
      console.error(`❌ ${error.message}`);
      process.exit(1);
    }
  });

program.parse();
