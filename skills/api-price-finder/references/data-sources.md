# 数据源清单（2026-08调研版）

> 比价时按此清单查询，禁止随意搜索碰运气。标注"价格API"表示可程序化获取。

## 一、官方厂商定价页（16家，交叉基准）

| 厂商 | 定价页 | 价格API | 备注 |
|---|---|---|---|
| OpenAI | platform.openai.com/pricing | ❌ | 官网页 |
| Anthropic | anthropic.com/pricing | ❌ | 限时价多（Sonnet 5 $2/$10 至2026-08-31） |
| Google Gemini | ai.google.dev/pricing | ❌ | 免费层已砍到20req/天 |
| xAI Grok | x.ai/api | ❌ | |
| Mistral | mistral.ai/pricing | ❌ | |
| NVIDIA NIM | build.nvidia.com | ❌ | 名义免费实际大量调用失败 |
| DeepSeek | platform.deepseek.com/pricing | ❌ | 2026-08涨价80%~3倍 |
| 智谱GLM | open.bigmodel.cn/pricing | ❌ | GLM-4-Flash真免费仅30并发 |
| 豆包/火山 | volcanoengine.com | ❌ | 有折扣活动（如2.5折） |
| 阿里百炼 | bailian.aliyun.com | ❌ | 新用户100万token/90天 |
| 腾讯混元 | cloud.tencent.com | ❌ | |
| 月之暗面Kimi | platform.moonshot.cn | ❌ | 限频不限量 |
| MiniMax | minimaxi.com | ❌ | 49元/6亿token套餐 |
| 阶跃StepFun | platform.stepfun.com | ❌ | credit制 |
| 书生InternLM | internlm.ai | ❌ | ⭐宝藏源：注册即用9000万/月、30RPM |
| 百川 | — | ❌ | 未找到公开定价页，业务转向医疗AI，不列入 |

## 二、第三方聚合平台（12家，核心比价源）

| 平台 | 价格API | 免费档 | 备注 |
|---|---|---|---|
| **OpenRouter** | ✅ /api/v1/models（免鉴权全量JSON）| :free 50req/天 | ⭐主链路 |
| SiliconFlow硅基流动 | ❌ 页面 | 14元新人 | ⚠️自购GPU，与官方有差异 |
| Together AI | ✅ | 部分免费 | |
| Groq | ❌ | 免费档5RPM | 速度极快 |
| Cerebras | ❌ | 免费档降为5RPM | 速度极快 |
| DeepInfra | ✅ | 部分 | 常比官方低30%+ |
| Fireworks | ✅ | | |
| Novita | ✅ | | |
| GitHub Models | ✅ | 有免费额度 | |
| HF Inference | ✅ | 部分 | 模型全 |
| Azure OpenAI | ❌ | 教育优惠 | 有学生免费额度 |
| AWS Bedrock | ❌ | | |

## 三、权威价格/智力数据库

| 数据源 | 用途 | 备注 |
|---|---|---|
| Artificial Analysis | ⭐智力指数（10项基准等权pass@1）+价格对比 | 有Data API |
| LMArena | 模型排行榜（人类偏好） | |
| Cloudflare AI Gateway | 多模型统一网关 | |
| Portkey | 模型价格追踪 | |

## 四、宝藏渠道（被低估，重点推荐）

| 渠道 | 优势 | 注意 |
|---|---|---|
| 上海AI实验室书生 | 注册即用9000万token/月、30RPM | ⭐最值得锁定；额度会变动 |
| Qwen3-Coder | OpenRouter免费版，被称"最强免费编程模型" | 促销性 |
| OpenRouter :free编程池 | 6+个免费编程模型 | 50req/天 |
| 国家超算长沙中心 | 免费 | 限校园网 |
| 华为云/ModelScope | 有免费额度 | |

## 五、教育/优惠渠道（固定知识）

- GitHub Education：免费额度/优惠
- Azure for Students：学生免费额度
- AWS Educate
- ⚠️ 礼品卡/闲鱼折扣：动态价格，按需搜索，标注黑卡风险
