#!/usr/bin/env python3
"""
全网API比价助手 - OpenRouter 实时价格+智力指数查询脚本
从 OpenRouter /api/v1/models（免鉴权）拉取全量模型价格 + Artificial Analysis 智力指数，
按「场景综合性价比」排序，默认只搜「便宜锚点以下」的免费/极低价模型。

用法：
  python main.py top <N>
  python main.py --scene coding top 10
  python main.py --scene agent --min-intel 40 top 10
  python main.py search <关键词>
  python main.py free
  python main.py compare <id1> <id2>
  python main.py --all top 10

场景与指数（--scene）：
  auto（默认）→ 按模型类型自动选指数
  chat   → 全部按 intelligence_index
  coding → 全部按 coding_index
  agent  → 全部按 agentic_index

--min-intel N：过滤场景指数 < N 的模型
--all：不套便宜锚点过滤，看全量
--html：输出单文件 HTML 可视化表格
"""
import sys
import os
import re
import json
import math
import time as _time
from datetime import datetime
from coze_workload_identity import requests

# ── 常量 ──────────────────────────────────────────────────────────────────

API_URL = "https://openrouter.ai/api/v1/models"
TIMEOUT = 20

API_LINKS = [
    ("openrouter", "https://openrouter.ai/keys"),
    ("deepseek", "https://platform.deepseek.com/"),
    ("openai", "https://platform.openai.com/api-keys"),
    ("anthropic", "https://console.anthropic.com/"),
    ("google", "https://aistudio.google.com/apikey"),
    ("z-ai", "https://open.bigmodel.cn/"),
    ("qwen", "https://bailian.console.aliyun.com/"),
    ("volcengine", "https://console.volcengine.com/ark"),
    ("hunyuan", "https://cloud.tencent.com/product/hunyuan"),
    ("moonshotai", "https://platform.moonshot.cn/"),
    ("moonshot", "https://platform.moonshot.cn/"),
    ("minimax", "https://platform.minimaxi.com/"),
    ("stepfun", "https://platform.stepfun.com/"),
    ("internlm", "https://internlm.ai/"),
    ("nvidia", "https://build.nvidia.com/"),
    ("siliconflow", "https://siliconflow.cn/"),
    ("groq", "https://console.groq.com/"),
    ("cerebras", "https://cloud.cerebras.ai/"),
    ("mistral", "https://console.mistral.ai/"),
    ("xai", "https://console.x.ai/"),
    ("huggingface", "https://huggingface.co/settings/tokens"),
    ("cohere", "https://dashboard.cohere.com/"),
    ("amazon", "https://console.aws.amazon.com/bedrock/"),
    ("azure", "https://portal.azure.com/#view/Microsoft_Azure_ProjectOxford/CognitiveServicesHub/~/AIHealth"),
    ("ibm-granite", "https://dataplatform.cloud.ibm.com/"),
    ("meta-llama", "https://llama.meta.com/"),
    ("microsoft", "https://azure.microsoft.com/"),
    ("ai21", "https://studio.ai21.com/"),
    ("upstage", "https://console.upstage.ai/"),
]
FALLBACK_LINK = "https://openrouter.ai/keys"

# 厂商标注：按模型 id 前缀显示来源厂商，让人一眼知道是谁家的
VENDOR_MAP = [
    ("deepseek", "深度求索 DeepSeek"),
    ("openai", "OpenAI"),
    ("anthropic", "Anthropic"),
    ("google", "谷歌 Google"),
    ("z-ai", "智谱 GLM"),
    ("qwen", "阿里通义千问"),
    ("volcengine", "字节豆包"),
    ("doubao", "字节豆包"),
    ("hunyuan", "腾讯混元"),
    ("moonshotai", "月之暗面 Kimi"),
    ("moonshot", "月之暗面 Kimi"),
    ("minimax", "MiniMax"),
    ("stepfun", "阶跃星辰 StepFun"),
    ("internlm", "上海AI实验室 书生"),
    ("nvidia", "英伟达 NVIDIA"),
    ("siliconflow", "硅基流动"),
    ("groq", "Groq"),
    ("cerebras", "Cerebras"),
    ("mistral", "Mistral"),
    ("xai", "xAI"),
    ("huggingface", "Hugging Face"),
    ("cohere", "Cohere"),
    ("amazon", "AWS"),
    ("azure", "微软 Azure"),
    ("ibm-granite", "IBM"),
    ("meta-llama", "Meta"),
    ("microsoft", "微软"),
    ("ai21", "AI21"),
    ("upstage", "Upstage"),
    ("inclusionai", "InclusionAI"),
    ("kwaipilot", "快手可灵"),
    ("poolside", "Poolside"),
    ("nex-agi", "NexAGI"),
    ("gryphe", "Gryphe"),
    ("sao10k", "SAO10K"),
    ("tencent", "腾讯"),
    ("aliyun", "阿里云"),
]


def get_vendor(model_id):
    """按模型 id 前缀返回厂商标注（如 '英伟达 NVIDIA'）。未匹配返回 None。"""
    if not model_id:
        return None
    mid = model_id.lower()
    for prefix, vendor in VENDOR_MAP:
        if mid.startswith(prefix):
            return vendor
    return None


def is_multimodal(model_raw):
    """判断是否多模态模型（架构含 image/audio/video 输入，或 modality 标注为 multimodal）。"""
    arch = model_raw.get("architecture") or {}
    modality = (arch.get("modality") or "").lower()
    return modality == "multimodal" or any(k in modality for k in ("image", "audio", "video"))

SCENE_INDEX = {"chat": "智力指数", "coding": "编程指数", "agent": "Agent指数"}
SCENE_LABEL = {
    "auto": "自动（按模型类型选指数：编程专用→编程指数，Agent→Agent指数，综合→智力指数）",
    "chat": "通用/聊天/推理（intelligence_index）",
    "coding": "编程/代码（coding_index）",
    "agent": "Agent任务/工具调用（agentic_index）",
}
SCENE_COST = {
    "auto": (0.9, 0.1, 0.7),
    "chat": (0.9, 0.1, 0.7),
    "coding": (0.6, 0.4, 0.7),
    "agent": (0.9, 0.1, 0.7),
}
TIER_DEFS = [(1, "旗舰", 55.0), (2, "主流", 45.0), (3, "轻量", 35.0)]
DS_FLASH_PREFIX = "deepseek/deepseek-v4-flash"
DS_FLASH_FALLBACK_USD = 0.0475
CNY_PER_USD_FALLBACK = 6.8

# ── 全局缓存 ──────────────────────────────────────────────────────────────

_cny_rate_cache = {"value": None, "ts": 0}
_OFFICIAL_PRICES = None
_TP_PLATFORMS = None
_AA_INTEL = None

# ── 汇率 ──────────────────────────────────────────────────────────────────

def get_cny_per_usd():
    now = _time.time()
    if _cny_rate_cache["value"] is not None and now - _cny_rate_cache["ts"] < 21600:
        return _cny_rate_cache["value"]
    try:
        resp = requests.get("https://open.er-api.com/v6/latest/USD", timeout=8)
        if resp.status_code == 200:
            rate = resp.json().get("rates", {}).get("CNY")
            if rate and float(rate) > 0:
                _cny_rate_cache["value"] = float(rate)
                _cny_rate_cache["ts"] = now
                return _cny_rate_cache["value"]
    except Exception:
        pass
    return CNY_PER_USD_FALLBACK

# ── API 申请链接 ──────────────────────────────────────────────────────────

def get_api_link(model_id):
    sorted_keys = sorted(API_LINKS, key=lambda x: len(x[0]), reverse=True)
    if not model_id:
        return FALLBACK_LINK
    mid = model_id.lower()
    for key, url in sorted_keys:
        if mid.startswith(key.lower()):
            return url
    return FALLBACK_LINK

# ── 数据加载 ──────────────────────────────────────────────────────────────

def fetch_models():
    """拉取 OpenRouter 全量模型；失败时打印友好错误并退出（避免裸 stack trace）。"""
    try:
        resp = requests.get(API_URL, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", [])
    except Exception as e:
        print(json.dumps({"error": f"获取 OpenRouter 模型列表失败：{e}",
                          "提示": "请检查网络或稍后重试"}, ensure_ascii=False))
        sys.exit(1)

def _load_official_prices():
    global _OFFICIAL_PRICES
    if _OFFICIAL_PRICES is not None:
        return _OFFICIAL_PRICES
    try:
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "references", "official_prices.json")
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        _OFFICIAL_PRICES = data.get("官方价") or {}
    except Exception:
        _OFFICIAL_PRICES = {}
    return _OFFICIAL_PRICES

def _load_tp_platforms():
    global _TP_PLATFORMS
    if _TP_PLATFORMS is not None:
        return _TP_PLATFORMS
    try:
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "references", "third_party_platforms.json")
        with open(p, "r", encoding="utf-8") as f:
            _TP_PLATFORMS = json.load(f)
    except Exception:
        _TP_PLATFORMS = {}
    return _TP_PLATFORMS

def _load_aa_intel():
    global _AA_INTEL
    if _AA_INTEL is not None:
        return _AA_INTEL
    try:
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "references", "aa_intelligence.json")
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        _AA_INTEL = {}
        for label, val in (data.get("models") or {}).items():
            if val and float(val) > 0:
                _AA_INTEL[_norm_aa(label)] = float(val)
    except Exception:
        _AA_INTEL = {}
    return _AA_INTEL

# ── 工具函数 ──────────────────────────────────────────────────────────────

def _norm_aa(label):
    s = label.lower()
    s = re.sub(r"\([^)]*\)", "", s)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s

def _strip_variant(mid):
    cands = []
    base = mid
    if ":" in base:
        base = base.split(":")[0]
        cands.append(base)
    if not base:
        return cands
    if base.startswith("~"):
        cands.append(base[1:])
    for suf in ("-latest", "-preview", "-fast", "-highspeed", "-beta", "-alpha"):
        if base.endswith(suf):
            cands.append(base[: -len(suf)])
    return cands

def _series_root(mid):
    s = mid.split(":")[0]
    s = s.lstrip("~")
    s = re.sub(r"-(pro|max|plus|mini|nano|small|highspeed|fast|latest|preview|beta|alpha)$", "", s)
    s = re.sub(r"-\d{2,8}$", "", s)
    return s

def _is_base_version(mid):
    s = mid.split(":")[0]
    s = s.lstrip("~")
    if re.search(r"-(pro|max|plus|mini|nano|small|highspeed|fast|latest|preview|beta|alpha)$", s):
        return False
    if re.search(r"-\d{2,8}$", s):
        return False
    return True

def _version_sort_key(mid):
    s = mid.split(":")[0]
    s = s.lstrip("~")
    if _is_base_version(mid):
        return (0, 0)
    if "-latest" in s:
        return (1, 0)
    m = re.search(r"-(\d{2,8})$", s)
    if m:
        return (2, -int(m.group(1)))
    if re.search(r"-(pro|max|plus)$", s):
        return (3, 0)
    return (4, 0)

def _dedupe_series(models):
    groups = {}
    for m in models:
        root = _series_root(m["id"])
        groups.setdefault(root, []).append(m)
    out = []
    for root, ms in groups.items():
        ms.sort(key=lambda x: _version_sort_key(x["id"]))
        out.append(ms[0])
    return out

def _merge_batch_free(models):
    mains = {}
    for m in models:
        if not m["id"].endswith(":batch") and not m["id"].endswith(":free"):
            mains[m["id"]] = m
    for m in models:
        mid = m["id"]
        if mid.endswith(":batch") or mid.endswith(":free"):
            base_id = mid.rsplit(":", 1)[0]
            if base_id not in mains:
                m["id"] = base_id
                mains[base_id] = m
    return list(mains.values())

# ── 官方价匹配 ────────────────────────────────────────────────────────────

def match_official_price(model_id):
    op = _load_official_prices()
    if not op or not model_id:
        return None
    mid = model_id.split(":")[0].lstrip("~").lower()
    if mid in op:
        return op[mid]
    for k, v in op.items():
        kk = k.lower()
        if mid.startswith(kk):
            return v
    return None

# ── 第三方平台提示 ─────────────────────────────────────────────────────────

def third_party_hint(model_id):
    tp = _load_tp_platforms()
    if not tp or not model_id:
        return None
    known = tp.get("典型模型多平台价差（调研时点）") or tp.get("典型模型多平台价差") or {}
    mid = model_id.lower()
    for k, v in known.items():
        kk = k.lower()
        if kk in mid or mid.split("/")[-1] in kk:
            suggestions = v.get("建议") or ""
            if "DeepInfra" in suggestions:
                return "DeepInfra 常比官方低30%+，可对比"
            if "OpenRouter" in suggestions:
                return "OpenRouter 可能比官方便宜，可对比"
            return "第三方平台可能更低，可对比"
    return None

# ── 综合单价计算 ──────────────────────────────────────────────────────────

def calc_composite(prompt_per_M, completion_per_M, cache_per_M, input_pct, output_pct, cache_hit):
    base = prompt_per_M * input_pct + completion_per_M * output_pct
    if prompt_per_M > 0:
        cache_discount = 1 - cache_hit * (1 - cache_per_M / prompt_per_M)
    else:
        cache_discount = 1
    return round(base * cache_discount, 4)

def resolve_prices(model_raw, input_pct, output_pct, cache_hit):
    """返回 (prompt_perM, completion_perM, cache_perM, composite_perM,
        官方输入_perM, 官方输出_perM, 官方缓存_perM, 官方复合_perM,
        价格来源, 平台提示)"""
    p = model_raw.get("pricing") or {}
    p_prompt = float(p.get("prompt") or 0)
    p_completion = float(p.get("completion") or 0)
    p_cache = float(p.get("input_cache_read") or 0)

    prompt_perM = round(p_prompt * 1_000_000, 4)
    completion_perM = round(p_completion * 1_000_000, 4)
    cache_perM = round(p_cache * 1_000_000, 4)
    plat_comp = calc_composite(prompt_perM, completion_perM, cache_perM, input_pct, output_pct, cache_hit)

    official = match_official_price(model_raw.get("id", ""))
    off_input_perM = None
    off_output_perM = None
    off_cache_perM = None
    off_comp = None

    if official:
        off_input_perM = float(official.get("input_usd_per_M") or 0)
        off_output_perM = float(official.get("output_usd_per_M") or 0)
        off_cache_perM = float(official.get("cache_read_usd_per_M") or 0)
        off_comp = calc_composite(off_input_perM, off_output_perM, off_cache_perM, input_pct, output_pct, cache_hit)

    is_free = (p_prompt == 0 and p_completion == 0)

    # 价格来源：官方名 / 具体平台名，不再用笼统"平台价"
    # 规则：① 官方价便宜且明显优于平台（差>10%）→ 标"官方价(厂商名)"；② 平台价便宜 → 标"OpenRouter省X%"；③ 官方价无明显优势 → 标平台价，不硬标官方
    PLATFORM_NAME = "OpenRouter"  # 当前实时价来源平台
    if official and off_comp is not None:
        if off_comp <= 0:
            # 官方免费（或官方价缺失）：直接用官方价，避免除零
            if plat_comp <= 0:
                composite = plat_comp
                price_src = f"{PLATFORM_NAME}价"
            else:
                composite = off_comp
                price_src = f"官方价({official.get('provider', '官方')})"
        else:
            diff_pct = (plat_comp - off_comp) / off_comp * 100
            if diff_pct > 10:
                # 官方价便宜且明显优于平台（低>10%）→ 标官方价
                composite = off_comp
                price_src = f"官方价({official.get('provider', '官方')})"
            elif diff_pct < -10:
                # 平台价便宜（低>10%）→ 标平台省X%
                composite = plat_comp
                pct_saved = int((1 - plat_comp / off_comp) * 100)
                price_src = f"{PLATFORM_NAME}省{pct_saved}%"
            else:
                # 官方与平台价差在 ±10% 内，无明显优势 → 标平台价，不硬标官方
                composite = plat_comp
                price_src = f"{PLATFORM_NAME}价"
    else:
        composite = plat_comp
        price_src = f"{PLATFORM_NAME}价"

    hint = third_party_hint(model_raw.get("id", ""))

    return (prompt_perM, completion_perM, cache_perM, composite,
            off_input_perM, off_output_perM, off_cache_perM, off_comp,
            price_src, hint, is_free)

# ── 智力指数提取 ──────────────────────────────────────────────────────────

def extract_intel(model_raw):
    aa = (model_raw.get("benchmarks") or {}).get("artificial_analysis") or {}
    return {
        "智力指数": aa.get("intelligence_index"),
        "编程指数": aa.get("coding_index"),
        "Agent指数": aa.get("agentic_index"),
    }

# ── 模型格式化（不含 DS Flash 倍数） ──────────────────────────────────────

def format_model(model_raw, input_pct, output_pct, cache_hit):
    prices = resolve_prices(model_raw, input_pct, output_pct, cache_hit)
    intel = extract_intel(model_raw)
    return {
        "id": model_raw.get("id") or "",
        "name": model_raw.get("name"),
        "context_length": model_raw.get("context_length"),
        "prompt_per_M": prices[0],
        "completion_per_M": prices[1],
        "cache_read_per_M": prices[2],
        "综合单价_per_M": prices[3],
        "官方输入价_per_M": prices[4],
        "官方输出价_per_M": prices[5],
        "官方缓存价_per_M": prices[6],
        "官方综合价_per_M": prices[7],
        "价格来源": prices[8],
        "平台提示": prices[9],
        "免费": prices[10],
        "厂商": get_vendor(model_raw.get("id")),
        "多模态": is_multimodal(model_raw),
        "智力指数": intel["智力指数"],
        "编程指数": intel["编程指数"],
        "Agent指数": intel["Agent指数"],
    }

# ── AA 智力指数补全 ──────────────────────────────────────────────────────

def enrich_missing_intel(result, raw_models):
    by_id = {m["id"]: m for m in raw_models}
    aa = _load_aa_intel()
    for r in result:
        # 变体继承
        for cand in _strip_variant(r["id"]):
            src = by_id.get(cand)
            if not src:
                continue
            bm = (src.get("benchmarks") or {}).get("artificial_analysis") or {}
            if bm.get("intelligence_index") is not None and r.get("智力指数") is None:
                r["智力指数"] = bm.get("intelligence_index")
            if bm.get("coding_index") is not None and r.get("编程指数") is None:
                r["编程指数"] = bm.get("coding_index")
            if bm.get("agentic_index") is not None and r.get("Agent指数") is None:
                r["Agent指数"] = bm.get("agentic_index")
            # 三个指数都补齐才早停，避免漏补其余指数
            if (r.get("智力指数") is not None and r.get("编程指数") is not None
                    and r.get("Agent指数") is not None):
                break
        if not aa or r.get("智力指数") is not None:
            continue
        # AA 缓存补全
        norm_id = _norm_aa(r["id"].split("/")[-1])
        for an, av in aa.items():
            if an and (an in norm_id or norm_id in an):
                r["智力指数"] = av
                break
    return result

# ── 场景与排序 ────────────────────────────────────────────────────────────

def detect_model_type(m):
    s = f'{m.get("id", "")} {m.get("name", "")}'.lower()
    if any(k in s for k in ("code", "coder", "codex", "coding")):
        return "coding"
    if any(k in s for k in ("agent", "agentic", "function")):
        return "agent"
    return "chat"

def resolve_scene(m, scene):
    if scene == "auto":
        typ = detect_model_type(m)
        key = SCENE_INDEX[typ]
    else:
        key = SCENE_INDEX[scene]
    return m.get(key), key

def tier_of(index):
    if index is None:
        return (4, "入门")
    for rank, name, threshold in TIER_DEFS:
        if index >= threshold:
            return (rank, name)
    return (4, "入门")

def value_score(index, cost_per_M):
    if index is None or cost_per_M is None:
        return None
    if cost_per_M <= 0:
        return round(index, 2)
    return round(index / (1 + math.log10(1 + cost_per_M)), 2)

def apply_scene_and_min_intel(result, scene, min_intel):
    out = []
    for m in result:
        idx, key = resolve_scene(m, scene)
        if min_intel is not None and (idx is None or idx < min_intel):
            continue
        m["scene_index"] = idx
        m["排序依据"] = key
        rank, name = tier_of(idx)
        m["档位"] = name
        m["_tier_rank"] = rank
        m["性价比评分"] = value_score(idx, m.get("综合单价_per_M"))
        out.append(m)
    return out

# ── DeepSeek Flash 基准 ──────────────────────────────────────────────────

def find_ds_flash_benchmark(deduped_models):
    flash_models = [m for m in deduped_models
                    if m["id"].lower().startswith(DS_FLASH_PREFIX) and not m["免费"]]
    if flash_models:
        costs = [m["综合单价_per_M"] for m in flash_models if m.get("综合单价_per_M") is not None]
        if costs:
            return min(costs)
    return DS_FLASH_FALLBACK_USD

# ── 便宜锚点 ──────────────────────────────────────────────────────────────

def compute_cheap_threshold(models):
    """便宜锚点 = DeepSeek V4 Pro 与 GPT-5.6 Luna 综合单价（官方vs平台取低后）中较贵者"""
    anchor_ids = ["deepseek/deepseek-v4-pro", "openai/gpt-5.6-luna"]
    costs = []
    by_id = {m["id"]: m for m in models}
    for aid in anchor_ids:
        m = by_id.get(aid)
        if m and m.get("综合单价_per_M") is not None:
            costs.append(m["综合单价_per_M"])
    if costs:
        return max(costs)
    return 0.16

# ── 显示工具 ──────────────────────────────────────────────────────────────

def human_readable_context(ctx):
    if ctx is None:
        return "—"
    ctx = int(ctx)
    if ctx >= 1_000_000:
        val = ctx / 1_000_000
        return f"{val:.1f}M".replace(".0M", "M")
    elif ctx >= 1_000:
        val = ctx / 1_000
        return f"{val:.0f}K"
    return str(ctx)

def context_grade_html(ctx):
    if ctx is None:
        return "—"
    ctx = int(ctx)
    s = human_readable_context(ctx)
    if ctx >= 1_000_000:
        return f'<span class="ctx-good">⭐{s}</span>'
    if ctx < 256_000:
        return f'<span class="ctx-warn">⚠️{s}</span>'
    return s

def price_cny_dual(val_usd, digits_for_yuan=2, digits_for_usd=4):
    if val_usd is None:
        return "—"
    rate = get_cny_per_usd()
    return f"¥{val_usd * rate:.{digits_for_yuan}f}（${val_usd:.{digits_for_usd}f}）"

def idx_html(val, active=False):
    cls = ' class="num active-idx"' if active else ' class="num"'
    if val is None:
        return f'<td{cls}>—</td>'
    v = float(val)
    if v >= 70:
        return f'<td{cls}><span class="idx-strong">💪{v:.1f}</span></td>'
    if v < 30:
        return f'<td{cls}><span class="idx-weak">⚠️{v:.1f}</span></td>'
    return f'<td{cls}>{v:.1f}</td>'

def dsx_html(ds_x, is_free):
    if is_free:
        return '<span class="dsx-cheap">免费</span>'
    if ds_x is None:
        return "—"
    if ds_x < 1:
        return f'<span class="dsx-cheap">💰≈{ds_x:.2f}×（比DS Flash便宜{(1-ds_x)*100:.0f}%）</span>'
    if ds_x <= 1.0:
        return f"≈{ds_x:.2f}×（与DS Flash持平）"
    return f"≈{ds_x:.1f}×DS Flash"

# ── HTML 渲染 ─────────────────────────────────────────────────────────────

def render_html(title, top_models, all_paid_cheap, all_free, params, scene="auto",
                min_intel=None, cheap_threshold=None, ds_flash_cost=None, total_count=0):
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    is_auto = scene == "auto"

    # 统计
    scene_desc = SCENE_LABEL.get(scene, scene)
    free_count = len(all_free)
    paid_cheap_count = len(all_paid_cheap)
    anchor_note = f"便宜锚点 ≤ ${cheap_threshold:.4f}/M" if cheap_threshold is not None else "全量"

    paid_cheap_sorted = sorted(
        [m for m in all_paid_cheap if not m.get("免费", False) and (m.get("综合单价_per_M") or 0) > 0],
        key=lambda x: x.get("综合单价_per_M") or 0
    )
    cheapest_paid = paid_cheap_sorted[0] if paid_cheap_sorted else None

    free_with_idx = [m for m in all_free if m.get("scene_index") is not None]
    best_free_intel = max(free_with_idx, key=lambda m: m["scene_index"]) if free_with_idx else None

    paid_with_score = [m for m in all_paid_cheap if not m.get("免费", False)
                       and m.get("scene_index") is not None and m.get("性价比评分") is not None]
    best_value = max(paid_with_score, key=lambda m: m["性价比评分"]) if paid_with_score else None

    longest_ctx_free = max(all_free, key=lambda m: m.get("context_length") or 0) if all_free else None

    stats = f"""<p>📌 排序依据：{scene_desc}{f' | 最低智力门槛：<strong>{min_intel}</strong>' if min_intel is not None else ''} | 本页共 <strong>{total_count}</strong> 个模型，免费 <strong>{free_count}</strong> 个，低价付费 <strong>{paid_cheap_count}</strong> 个。</p>"""
    if cheap_threshold is not None:
        stats += f"""<p>🎯 默认只搜免费或（输入价≤$1/M 且 综合单价≤{cheap_threshold:.4f}$/M）的模型。想看全量加 <strong>--all</strong>。</p>"""
    if cheapest_paid:
        stats += f"""<p>付费模型中单价最低：<strong>{cheapest_paid["id"]}</strong>（{price_cny_dual(cheapest_paid["综合单价_per_M"])}）</p>"""
    if best_free_intel:
        stats += f"""<p>🏆 最高智力免费模型：<strong>{best_free_intel["id"]}</strong>（{best_free_intel["排序依据"]} {best_free_intel["scene_index"]:.1f}）</p>"""
    if best_value:
        stats += f"""<p>💎 最高智力低价模型：<strong>{best_value["id"]}</strong>（指数 {best_value["scene_index"]:.1f}，{price_cny_dual(best_value["综合单价_per_M"])}，评分 {best_value["性价比评分"]:.2f}）</p>"""
    if longest_ctx_free:
        stats += f"""<p>免费模型中上下文最长：<strong>{longest_ctx_free["id"]}</strong>（{human_readable_context(longest_ctx_free.get("context_length"))}）</p>"""

    classify_table = """<table class="classify-table">
<tr><th>免费形态</th><th>说明</th><th>示例</th></tr>
<tr><td><strong>纯免费</strong></td><td>注册即用，无需付费</td><td>书生InternLM 9000万/月、智谱GLM-4-Flash（仅30并发）</td></tr>
<tr><td><strong>有额度免费</strong></td><td>注册赠送额度，用完后付费</td><td>DeepSeek 体验金100万token、阿里百炼100万/90天</td></tr>
<tr><td><strong>次数限制免费</strong></td><td>每日/每分钟限制请求次数</td><td>OpenRouter :free 50req/天、Cerebras 5RPM、Gemini免费层20req/天</td></tr>
<tr style="background-color:#fff3e0"><td><strong style="color:#e67e22">需充值才有免费额度</strong></td><td style="color:#e67e22">可能需要充值（如$10余额）才能访问完整功能/解除限流</td><td style="color:#e67e22">OpenRouter等平台的免费模型</td></tr>
<tr><td><strong>促销性免费</strong></td><td>限时/收集数据，可能被训练</td><td>Qwen Preview、OpenCode Zen</td></tr>
</table>"""

    summary = f"""<div class="summary-card">
<h2>📊 免费/低价现状简介</h2>
<div class="summary-stats">{stats}</div>
<div class="summary-classify">{classify_table}</div>
</div>"""

    def model_row(m, is_free_model, idx):
        bg = ' style="background-color:#d4edda"' if is_free_model else (' style="background-color:#f9f9f9"' if idx % 2 == 1 else "")
        link = get_api_link(m["id"])
        link_html = f'<a href="{link}" target="_blank" title="{link}">申请</a>'
        ctx = context_grade_html(m.get("context_length"))
        dsx = dsx_html(m.get("DS_Flash倍数"), is_free_model)
        p_in = price_cny_dual(m.get("prompt_per_M"))
        p_out = price_cny_dual(m.get("completion_per_M"))
        p_cache = price_cny_dual(m.get("cache_read_per_M"))
        p_comp = price_cny_dual(m.get("综合单价_per_M"))
        src_raw = m.get("价格来源", "OpenRouter价")
        # 价格来源高亮：官方价绿色、平台省X%橙色、其他灰色
        if "官方价" in src_raw:
            src_note = f'<br/><span class="src-official">🏛️ {src_raw}</span>'
        elif "省" in src_raw:
            src_note = f'<br/><span class="src-save">💰 {src_raw}</span>'
        else:
            src_note = f'<br/><span class="src-note">🌐 {src_raw}</span>'
        if is_auto:
            tier_cell = f'{m.get("档位", "—")}·{m.get("排序依据", "").replace("指数", "")}'
        else:
            tier_cell = m.get("档位", "—")
        free_tier = '<span style="color:green;font-weight:bold">免费</span>' if is_free_model else "—"

        vendor = get_vendor(m["id"])
        vendor_html = f'<br/><span class="src-note">📍 {vendor}</span>' if vendor else ""
        # 多模态标注
        mm_html = '<span class="mm-badge" title="多模态模型：支持图片/音视频输入，输入token通常更大">*多模态*</span>' if m.get("多模态") else ""
        return f"""<tr{bg}>
<td>{m["id"]}</td>
<td>{m["name"]}{mm_html}{vendor_html}</td>
<td>{ctx}</td>
<td class="num">{p_in}</td>
<td class="num">{p_out}</td>
<td class="num">{p_cache}</td>
<td class="num strong">{p_comp}<br/><span class="dsx">{dsx}</span>{src_note}</td>
{idx_html(m.get("智力指数"), not is_auto and scene == "chat")}
{idx_html(m.get("编程指数"), not is_auto and scene == "coding")}
{idx_html(m.get("Agent指数"), not is_auto and scene == "agent")}
<td class="num">{f"{m['性价比评分']:.2f}" if m.get("性价比评分") is not None else "—"}</td>
<td>{tier_cell}</td>
<td>{free_tier}</td>
<td>{link_html}</td>
</tr>"""

    all_free_sorted = sorted(all_free, key=lambda x: -(x.get("性价比评分") or 0))
    free_rows = "\n".join(model_row(m, True, i) for i, m in enumerate(all_free_sorted))
    paid_rows = "\n".join(model_row(m, False, i) for i, m in enumerate(all_paid_cheap) if not m.get("免费", False))

    col_headers = """<th>模型ID</th>
<th>名称</th>
<th>上下文长度</th>
<th class="num">输入价/M(¥)</th>
<th class="num">输出价/M(¥)</th>
<th class="num">缓存价/M(¥)</th>
<th class="num">综合单价/M（DS Flash倍数）</th>
<th class="num">智力指数</th>
<th class="num">编程指数</th>
<th class="num">Agent指数</th>
<th class="num">性价比评分</th>
<th>档位·排序依据</th>
<th>免费档位</th>
<th>官方申请链接</th>"""

    sort_note = f'排序：{scene_desc}｜算法：先按指数分档（旗舰≥55/主流45-55/轻量35-45/入门<35），档内按 性价比评分=指数/(1+log10(1+单价)) 降序'

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 20px; }}
h1 {{ font-size: 1.5em; margin-bottom: 5px; }}
.meta {{ color: #555; margin-bottom: 15px; font-size: 0.9em; }}
.table-wrap {{ overflow-x: auto; }}
table {{ min-width: 1400px; border-collapse: collapse; font-size: 0.85em; }}
th {{ background-color: #2c3e50; color: white; padding: 10px 8px; text-align: center; white-space: nowrap; }}
td {{ padding: 8px; border-bottom: 1px solid #ddd; }}
tr:nth-child(odd) td {{ background-color: #f5f5f5; }}
th:last-child, td:last-child {{ position: sticky; right: 0; z-index: 2; }}
th:last-child {{ background-color: #1a2a3a; }}
td:last-child {{ background-color: #fff; border-left: 2px solid #ddd; box-shadow: -2px 0 4px rgba(0,0,0,.08); }}
tr:nth-child(odd) td:last-child {{ background-color: #f5f5f5; }}
.num {{ text-align: right; font-family: "SF Mono", Monaco, Consolas, monospace; }}
.strong {{ font-weight: bold; color: #1a56db; }}
.dsx {{ font-size: 0.8em; color: #666; font-weight: normal; }}
.ctx-warn {{ color: #e67e22; }}
.ctx-good {{ color: #2e7d32; font-weight: bold; }}
.idx-strong {{ color: #1a8a4a; font-weight: bold; }}
.idx-weak {{ color: #d32f2f; }}
.src-note {{ font-size: 0.75em; color: #888; font-weight: normal; }}
.src-official {{ font-size: 0.75em; color: #1a8a4a; font-weight: bold; background-color: #e6f7e6; padding: 1px 4px; border-radius: 3px; }}
.src-save {{ font-size: 0.75em; color: #e67e22; font-weight: bold; background-color: #fff3e0; padding: 1px 4px; border-radius: 3px; }}
.mm-badge {{ font-size: 0.75em; color: #7b1fa2; font-weight: bold; margin-left: 4px; }}
.dsx-cheap {{ color: #1a8a4a; font-weight: bold; background-color: #e6f7e6; padding: 1px 4px; border-radius: 3px; }}
.active-idx {{ background-color: #e8f0fe !important; color: #1a56db; font-weight: bold; }}
th.active-idx {{ background-color: #1a56db !important; }}
a {{ color: #2980b9; text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
.summary-card {{ background-color: #f0f7ff; border: 1px solid #d0e3f5; border-radius: 8px; padding: 12px 16px; margin-bottom: 15px; }}
.summary-card h2 {{ font-size: 1.1em; margin: 0 0 8px 0; }}
.summary-stats p {{ margin: 4px 0; font-size: 0.9em; }}
.summary-classify {{ margin-top: 10px; }}
.classify-table {{ font-size: 0.8em; border-collapse: collapse; width: 100%; }}
.classify-table th, .classify-table td {{ position: static !important; box-shadow: none !important; border-left: none !important; }}
.classify-table th {{ background-color: #e8f0fe; color: #333; padding: 6px 8px; text-align: left; font-weight: bold; }}
.classify-table td {{ padding: 4px 8px; border-bottom: 1px solid #eee; }}
</style>
</head>
<body>
<h1>{title}</h1>
<div class="meta">生成时间：{now_str} | 参数：输入占比 {params["input_pct"]:.0%} / 输出占比 {params["output_pct"]:.0%} / 缓存命中 {params["cache_hit"]:.0%} | 汇率：1 USD ≈ {get_cny_per_usd():.4f} CNY（即期） | {sort_note}</div>
{summary}
<h2>🟢 完全免费区（{len(all_free_sorted)}个）</h2>
<p class="meta">免费形态见上方分类表；免费不等于好用，注意限流/智力/上下文短板。</p>
<div class="table-wrap">
<table>
<thead><tr>{col_headers}</tr></thead>
<tbody>
{free_rows}
</tbody>
</table>
</div>
<h2>💡 低价区（{paid_cheap_count}个，输入价 ≤ $1/M）</h2>
<p class="meta">价格为 <strong>OpenRouter 平台价</strong>，可能低于官方价（平台折扣/补贴），也可能高于官方促销价；最终以官方当天为准。</p>
<div class="table-wrap">
<table>
<thead><tr>{col_headers}</tr></thead>
<tbody>
{paid_rows}
</tbody>
</table>
</div>
</body>
</html>"""
    return html

# ── 主逻辑 ────────────────────────────────────────────────────────────────

def process_models(raw_models, input_pct, output_pct, cache_hit, scene="auto", min_intel=None):
    """通用处理管道：格式化→补指数→场景→排序。返回已排序的模型列表。"""
    # 跳过缺 id 的脏数据，避免下游 _strip_variant/_series_root 等对 None 崩溃
    result = [format_model(m, input_pct, output_pct, cache_hit) for m in raw_models if m.get("id")]
    result = enrich_missing_intel(result, raw_models)
    result = apply_scene_and_min_intel(result, scene, min_intel)
    result.sort(key=lambda x: (x["_tier_rank"], -(x["性价比评分"] or 0)))
    return result

def finalize_with_ds(deduped, ds_flash_cost):
    """给去重后的模型加 DS_Flash倍数。"""
    for m in deduped:
        if m["免费"]:
            m["DS_Flash倍数"] = None
        elif ds_flash_cost and ds_flash_cost > 0 and m.get("综合单价_per_M") is not None:
            m["DS_Flash倍数"] = round(m["综合单价_per_M"] / ds_flash_cost, 2)
        else:
            m["DS_Flash倍数"] = None
    return deduped

def get_free_models(all_processed):
    return [m for m in all_processed if m.get("免费", False)]

def main():
    args = sys.argv[1:]

    # 全局参数提取
    html_mode = "--html" in args
    args = [a for a in args if a != "--html"]
    show_all = "--all" in args
    args = [a for a in args if a != "--all"]

    scene = "auto"
    if "--scene" in args:
        idx = args.index("--scene")
        if idx + 1 >= len(args):
            print(json.dumps({"error": "--scene 缺少场景参数", "可选": ["auto"] + list(SCENE_INDEX.keys())},
                             ensure_ascii=False))
            return
        scene = args[idx + 1].lower()
        if scene not in SCENE_INDEX and scene != "auto":
            print(json.dumps({"error": f"未知场景 {scene}", "可选": ["auto"] + list(SCENE_INDEX.keys())},
                             ensure_ascii=False))
            return
        args = args[:idx] + args[idx + 2:]

    min_intel = None
    if "--min-intel" in args:
        idx = args.index("--min-intel")
        if idx + 1 >= len(args):
            print(json.dumps({"error": "--min-intel 缺少数值参数"}, ensure_ascii=False))
            return
        try:
            min_intel = float(args[idx + 1])
        except ValueError:
            print(json.dumps({"error": f"--min-intel 参数必须为数字，收到 {args[idx + 1]!r}"},
                             ensure_ascii=False))
            return
        args = args[:idx] + args[idx + 2:]

    input_pct, output_pct, cache_hit = SCENE_COST["chat" if scene == "auto" else scene]
    params = {"input_pct": input_pct, "output_pct": output_pct, "cache_hit": cache_hit}

    if not args or args[0] == "list":
        raw = fetch_models()
        processed = process_models(raw, input_pct, output_pct, cache_hit, scene, min_intel)
        ds_flash = find_ds_flash_benchmark(processed)
        finalize_with_ds(processed, ds_flash)
        if html_mode:
            all_free = get_free_models(processed)
            print(render_html("全量模型价格", [], [], all_free, params, scene, min_intel,
                              total_count=len(processed), ds_flash_cost=ds_flash))
        else:
            print(json.dumps({"count": len(processed), "models": processed}, ensure_ascii=False))

    elif args[0] == "search":
        if len(args) < 2:
            print(json.dumps({"error": "search 需要关键词参数", "usage": "search <关键词>"},
                             ensure_ascii=False))
            return
        kw = args[1].lower()
        raw = fetch_models()
        matched = [m for m in raw
                   if kw in (m.get("id") or "").lower() or kw in (m.get("name") or "").lower()]
        processed = process_models(matched, input_pct, output_pct, cache_hit, scene, min_intel)
        # 去重
        deduped = _merge_batch_free(processed)
        deduped = _dedupe_series(deduped)
        ds_flash = find_ds_flash_benchmark(deduped)
        finalize_with_ds(deduped, ds_flash)
        if html_mode:
            all_free = get_free_models(deduped)
            all_paid = [m for m in deduped if not m.get("免费", False)
                        and (m.get("prompt_per_M") is not None and m["prompt_per_M"] <= 1.0)]
            print(render_html(f"搜索结果：{kw}", [], all_paid, all_free, params, scene, min_intel,
                              total_count=len(deduped), ds_flash_cost=ds_flash))
        else:
            print(json.dumps({"count": len(deduped), "models": deduped}, ensure_ascii=False))

    elif args[0] == "free":
        raw = fetch_models()
        free_raw = [m for m in raw
                    if float((m.get("pricing") or {}).get("prompt") or 0) == 0
                    and float((m.get("pricing") or {}).get("completion") or 0) == 0]
        processed = process_models(free_raw, input_pct, output_pct, cache_hit, scene, min_intel)
        deduped = _merge_batch_free(processed)
        deduped = _dedupe_series(deduped)
        ds_flash = find_ds_flash_benchmark(deduped)
        finalize_with_ds(deduped, ds_flash)
        if html_mode:
            all_free = get_free_models(deduped)
            print(render_html("免费模型", [], [], all_free, params, scene, min_intel,
                              total_count=len(deduped), ds_flash_cost=ds_flash))
        else:
            print(json.dumps({"count": len(deduped), "models": deduped}, ensure_ascii=False))

    elif args[0] == "top":
        if len(args) > 1:
            try:
                n = int(args[1])
            except ValueError:
                print(json.dumps({"error": f"top 参数必须为数字，收到 {args[1]!r}", "usage": "top <N>"},
                                 ensure_ascii=False))
                return
        else:
            n = 5
        raw = fetch_models()
        # 第1步：格式化+补指数+场景+排序
        processed = process_models(raw, input_pct, output_pct, cache_hit, scene, min_intel)
        # 第2步：便宜锚点过滤（非 --all）
        if not show_all:
            cheap_threshold = compute_cheap_threshold(processed)
            processed = [m for m in processed
                         if m["免费"]
                         or (m.get("prompt_per_M") is not None and m["prompt_per_M"] <= 1.0
                             and m.get("综合单价_per_M") is not None and m["综合单价_per_M"] <= cheap_threshold)]
        else:
            cheap_threshold = compute_cheap_threshold(processed)
        # 第3步：去重
        deduped = _merge_batch_free(processed)
        deduped = _dedupe_series(deduped)
        # 第4步：DS Flash 基准
        ds_flash = find_ds_flash_benchmark(deduped)
        # 第5步：加倍数
        finalize_with_ds(deduped, ds_flash)
        # 第6步：Top N
        top_n = deduped[:n]

        sort_desc = ("先按场景智力指数分档（旗舰≥55/主流45-55/轻量35-45/入门<35），"
                     "档内按 性价比评分=智力指数/(1+log10(1+综合单价$/M)) 降序；免费模型评分=智力指数")

        if html_mode:
            # 免费区显示【全部】免费模型：用过滤后、去重前的 processed（避免 :free 变体被付费主模型吞掉）
            all_free = get_free_models(processed)
            if show_all:
                all_paid = [m for m in deduped if not m.get("免费", False)
                            and (m.get("prompt_per_M") is not None and m["prompt_per_M"] <= 1.0)]
            else:
                all_paid = [m for m in deduped if not m.get("免费", False)]
            print(render_html(f"综合性价比Top {n}", top_n, all_paid, all_free, params, scene,
                              min_intel, cheap_threshold, ds_flash, len(deduped)))
        else:
            # 便宜锚点信息
            anchor_ids = ["deepseek/deepseek-v4-pro", "openai/gpt-5.6-luna"]
            by_id = {m["id"]: m for m in deduped}
            anchor_costs = []
            for aid in anchor_ids:
                m = by_id.get(aid)
                if m and m.get("综合单价_per_M") is not None:
                    anchor_costs.append((aid, m["综合单价_per_M"]))
            anchors_note = "、".join(f"{aid} ${c:.4f}/M" for aid, c in anchor_costs) if anchor_costs else "（未找到锚点模型）"
            scope_note = f"便宜锚点以下（免费或综合单价 ≤ {cheap_threshold:.4f} $/M；锚点：{anchors_note}）"
            print(json.dumps({
                "场景": SCENE_LABEL[scene],
                "排序说明": sort_desc,
                "默认范围": scope_note + "；想看全量（含高端旗舰）用 --all",
                "提示": "默认只搜性价比高的免费/极低价模型；想看全量加 --all",
                "参数": {"输入占比": input_pct, "输出占比": output_pct, "缓存命中": cache_hit,
                         "最低智力门槛": min_intel, "DeepSeekFlash基准单价": ds_flash},
                "榜单TOP": top_n,
            }, ensure_ascii=False))

    elif args[0] == "compare":
        ids = args[1:]
        raw = fetch_models()
        by_id = {m.get("id"): m for m in raw}
        matched_raw = []
        for mid in ids:
            m = by_id.get(mid)
            if m:
                matched_raw.append(m)
        processed = process_models(matched_raw, input_pct, output_pct, cache_hit, scene, min_intel)
        deduped = _merge_batch_free(processed)
        deduped = _dedupe_series(deduped)
        ds_flash = find_ds_flash_benchmark(deduped)
        finalize_with_ds(deduped, ds_flash)
        if html_mode:
            all_free = get_free_models(processed)
            all_paid = [m for m in deduped if not m.get("免费", False)]
            print(render_html("模型对比", [], all_paid, all_free, params, scene, min_intel,
                              total_count=len(deduped), ds_flash_cost=ds_flash))
        else:
            print(json.dumps({"models": deduped}, ensure_ascii=False))

    else:
        msg = json.dumps({"error": "未知命令", "usage": "list|search|free|top|compare（可加 --scene/--min-intel/--all/--html）"},
                         ensure_ascii=False)
        if html_mode:
            print(f"<html><body><h1>错误</h1><p>{msg}</p></body></html>")
        else:
            print(msg)


if __name__ == "__main__":
    main()