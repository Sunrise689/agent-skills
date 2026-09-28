#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Best SMA Finder - 自动识别最优移动平均线
================================================
v2.1.0 - 智能路由数据源架构

模式:
  单均线 (--method single): 价格上穿SMA买入, 下穿卖出
  双均线交叉 (--method cross): fast上穿slow(金叉)买入, 下穿(死叉)卖出

策略: Long Only(默认) / Buy & Sell(多空都做)
评分: profit_factor × ln(trades) × √win_rate
KNN增强: 暴力枚举找全局Top, KNN选当前市场最适配
多周期对比 (--compare): 日/周/月三周期同时扫描

数据源: 智能路由模式 — 按市场类型自动选择最优数据源链
  A股: 腾讯财经 → 新浪财经 → baostock → 雪球(可选) → yfinance
  港股: 腾讯财经 → yfinance → 雪球(可选)
  全球: yfinance → 雪球(可选) → stooq(可选) → 自定义API(可选)
"""

import os
import urllib.parse
import argparse
import math
import sys
import json
import urllib.request
from datetime import datetime, timedelta
import numpy as np


# ──────────────────── 全局配置变量 ────────────────────
_XUEQIU_TOKEN = ""
_STOOQ_APIKEY = ""
_CUSTOM_API_URL = ""


# ──────────────────── 数据获取 ────────────────────

# ── 辅助函数 ──
def _get_a_share_prefix(code):
    """统一获取A股前缀: 5/6/9开头为沪市(sh), 其余为深市(sz)"""
    sym = code.strip().lower()
    if sym.startswith(("sh", "sz")):
        return sym[:2]
    if sym.startswith(("5", "6", "9")):
        return "sh"
    return "sz"


def _detect_market(symbol):
    """判断股票市场类型: 'a_share' / 'hk' / 'global'"""
    sym = symbol.strip().lower()
    if sym.startswith(("sh", "sz")) and len(sym) == 8 and sym[-6:].isdigit():
        return "a_share"
    if sym.isdigit() and len(sym) == 6:
        return "a_share"
    if sym.startswith("hk") and len(sym) >= 3 and sym[2:].isdigit():
        return "hk"
    if sym.isdigit() and len(sym) == 5:
        return "hk"
    return "global"


# ── baostock 辅助 ──
_BAOSTOCK_LOGGED_IN = False

def _bs_login():
    global _BAOSTOCK_LOGGED_IN
    if not _BAOSTOCK_LOGGED_IN:
        import baostock as bs
        lg = bs.login()
        if lg.error_code != "0":
            raise RuntimeError(f"baostock 登录失败: {lg.error_msg}")
        _BAOSTOCK_LOGGED_IN = True


def _bs_kline(symbol, period, count):
    """通过 baostock 获取日/周/月线 (A股), 返回 dict-list 或 None"""
    import baostock as bs
    _bs_login()

    # 代码格式: sh.600519 / sz.300059
    if symbol.lower().startswith(("sh", "sz")):
        bs_code = f"{symbol[:2].lower()}.{symbol[-6:]}"
    elif symbol.isdigit() and len(symbol) == 6:
        prefix = _get_a_share_prefix(symbol)
        bs_code = f"{prefix}.{symbol}"
    else:
        return None

    freq_map = {"daily": "d", "weekly": "w", "monthly": "m"}
    freq = freq_map.get(period, "d")

    # 倒推起始日期: 日线取 count 天, 周/月线乘系数
    end = datetime.now()
    day_mult = {"d": 1, "w": 7, "m": 30}
    start = end - timedelta(days=count * day_mult.get(freq, 1) + 60)
    start_str = start.strftime("%Y-%m-%d")
    end_str = end.strftime("%Y-%m-%d")

    rs = bs.query_history_k_data_plus(
        bs_code,
        "date,open,close,high,low,volume",
        start_date=start_str, end_date=end_str,
        frequency=freq, adjustflag="2"  # 前复权
    )
    if rs is None or rs.error_code != "0":
        return None

    rows = []
    while rs.next():
        d = rs.get_row_data()
        if d[0] is None:
            continue
        rows.append({
            "date": d[0],
            "open": float(d[1]), "close": float(d[2]),
            "high": float(d[3]), "low": float(d[4]),
            "volume": float(d[5]),
        })
    rows.sort(key=lambda x: x["date"])
    if not rows:
        return None
    return rows[-count:]


# ── 雪球 (xueqiu.com) ──
def _xueqiu_kline(symbol, period, count, token=""):
    """通过雪球API获取K线 (需xq_a_token), 返回 dict-list 或 None"""
    if not token:
        return None

    # symbol标准化
    sym = symbol.strip().lower()
    if sym.startswith(("sh", "sz")) and len(sym) == 8:
        xq_symbol = f"{sym[:2].upper()}{sym[-6:]}"
    elif sym.isdigit() and len(sym) == 6:
        xq_symbol = f"SH{sym}" if sym.startswith(("5", "6", "9")) else f"SZ{sym}"
    elif sym.startswith("hk") and len(sym) >= 3 and sym[2:].isdigit():
        xq_symbol = f"HK{sym[2:]}"
    elif sym.isdigit() and len(sym) == 5:
        xq_symbol = f"HK{sym}"
    else:
        xq_symbol = sym.upper()

    period_map = {"daily": "day", "weekly": "week", "monthly": "month"}
    xq_period = period_map.get(period, "day")

    url = (f"https://stock.xueqiu.com/v5/stock/chart/kline.json"
           f"?symbol={xq_symbol}&period={xq_period}&type=before"
           f"&count=-{count}&indicator=kline")

    try:
        # 先访问首页拿cookie session
        proxy_handler = urllib.request.ProxyHandler({})
        opener = urllib.request.build_opener(proxy_handler)
        req_home = urllib.request.Request(
            "https://xueqiu.com",
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
        )
        with opener.open(req_home, timeout=15) as resp_home:
            pass

        # 请求kline数据
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
                "Cookie": f"xq_a_token={token}",
                "Referer": "https://xueqiu.com/",
            }
        )
        with opener.open(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")

        j = json.loads(raw)
        items = j.get("data", {}).get("item", [])
        if not items:
            return None

        result = []
        for item in items:
            # item格式: [timestamp, open, close, high, low, volume, ...]
            ts = item[0] / 1000  # 毫秒转秒
            dt = datetime.fromtimestamp(ts)
            result.append({
                "date": dt.strftime("%Y-%m-%d"),
                "open": float(item[1]),
                "close": float(item[2]),
                "high": float(item[3]),
                "low": float(item[4]),
                "volume": float(item[5]),
            })
        result.sort(key=lambda x: x["date"])
        return result[-count:]
    except Exception:
        return None


# ── stooq.com ──
def _stooq_kline(symbol, period, count, apikey=""):
    """通过 stooq.com CSV API 获取K线, 返回 dict-list 或 None"""
    if not apikey:
        return None
    if period != "daily":
        return None  # stooq 只支持日线

    sym = symbol.strip().upper()
    # 去掉交易所前缀
    if sym.startswith(("SH.", "SZ.", "HK.")):
        sym = sym.split(".", 1)[1]
    url = f"https://stooq.com/q/d/l/?s={sym}.US&i=d&apikey={apikey}"

    try:
        proxy_handler = urllib.request.ProxyHandler({})
        opener = urllib.request.build_opener(proxy_handler)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with opener.open(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")

        lines = raw.strip().splitlines()
        if len(lines) < 2:
            return None

        result = []
        for line in lines[1:]:  # 跳过表头
            parts = line.split(",")
            if len(parts) < 6:
                continue
            try:
                result.append({
                    "date": parts[0].strip(),
                    "open": float(parts[1]),
                    "close": float(parts[4]),
                    "high": float(parts[2]),
                    "low": float(parts[3]),
                    "volume": float(parts[5]),
                })
            except (ValueError, IndexError):
                continue
        result.sort(key=lambda x: x["date"])
        return result[-count:]
    except Exception:
        return None


# ── 自定义API ──
def _custom_api_kline(symbol, period, count, url_template):
    """通过自定义API URL模板获取K线, 返回 dict-list 或 None"""
    if not url_template:
        return None

    sym = symbol.strip()
    period_map = {"daily": "day", "weekly": "week", "monthly": "month"}
    p = period_map.get(period, "day")
    url = url_template.replace("{symbol}", sym).replace("{period}", p).replace("{count}", str(count))

    try:
        proxy_handler = urllib.request.ProxyHandler({})
        opener = urllib.request.build_opener(proxy_handler)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with opener.open(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")

        j = json.loads(raw)
        # 尝试多种可能的JSON结构
        rows = None
        if isinstance(j, list):
            rows = j
        elif isinstance(j, dict):
            for key in ("data", "result", "records", "items", "values", "kline"):
                if key in j and isinstance(j[key], list):
                    rows = j[key]
                    break

        if not rows:
            return None

        result = []
        for r in rows:
            if isinstance(r, dict):
                d = {
                    "date": str(r.get("date", r.get("day", r.get("t", "")))),
                    "open": float(r.get("open", r.get("o", 0))),
                    "close": float(r.get("close", r.get("c", 0))),
                    "high": float(r.get("high", r.get("h", 0))),
                    "low": float(r.get("low", r.get("l", 0))),
                    "volume": float(r.get("volume", r.get("v", 0))),
                }
                result.append(d)
            elif isinstance(r, (list, tuple)) and len(r) >= 6:
                result.append({
                    "date": str(r[0]),
                    "open": float(r[1]),
                    "close": float(r[4]),
                    "high": float(r[2]),
                    "low": float(r[3]),
                    "volume": float(r[5]),
                })
        result.sort(key=lambda x: x["date"])
        return result[-count:]
    except Exception:
        return None


# ── yfinance (雅虎财经) 辅助 ──
def _yf_kline(symbol, period, count):
    """通过 yfinance (雅虎财经) 获取K线, 返回 dict-list 或 None
    覆盖: 美股 (SPY, AAPL), 大宗商品 (GC=F 黄金, CL=F 原油), 外汇, ETF, 加密货币等
    """
    try:
        import yfinance as yf
        yf_period_map = {"daily": "1d", "weekly": "1wk", "monthly": "1mo"}
        yf_interval = yf_period_map.get(period, "1d")
        day_mult = {"daily": 1, "weekly": 7, "monthly": 30}
        total_days = count * day_mult.get(period, 1) + 60
        start = datetime.now() - timedelta(days=total_days)
        start_str = start.strftime("%Y-%m-%d")
        ticker = yf.Ticker(symbol)
        df = ticker.history(start=start_str, interval=yf_interval)
        if df.empty:
            return None
        result = []
        for idx, row in df.iterrows():
            result.append({
                "date": idx.strftime("%Y-%m-%d"),
                "open": float(row["Open"]),
                "close": float(row["Close"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "volume": float(row["Volume"]),
            })
        result.sort(key=lambda x: x["date"])
        return result[-count:]
    except Exception:
        return None


def _http_get(url):
    """HTTP GET, 自动跳过系统代理"""
    proxy_handler = urllib.request.ProxyHandler({})
    opener = urllib.request.build_opener(proxy_handler)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with opener.open(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def fetch_kline(symbol, period="daily", count=1200):
    """获取历史K线, 返回 dict-list 或 raise
    智能路由 — 按市场类型自动选择最优数据源链

    A股路由: 腾讯财经 → 新浪财经 → baostock → 雪球(可选) → yfinance
    港股路由: 腾讯财经 → yfinance → 雪球(可选)
    全球路由: yfinance → 雪球(可选) → stooq(可选) → 自定义API(可选)
    """
    sym = symbol.strip()
    market = _detect_market(sym)
    period_map = {"daily": "day", "weekly": "week", "monthly": "month"}
    tp = period_map[period]
    failures = []

    # ──────────────────── A股路由 ────────────────────
    if market == "a_share":
        # 统一前缀
        if sym.lower().startswith(("sh", "sz")) and len(sym) == 8:
            prefix = sym[:2].lower()
            code = sym[-6:]
        elif sym.isdigit() and len(sym) == 6:
            prefix = _get_a_share_prefix(sym)
            code = sym
        else:
            raise RuntimeError(f"A股代码格式不支持: {symbol}。示例: 600519 / 300059 / sz300059")

        # 1. 腾讯API
        try:
            url = (f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
                   f"?param={prefix}{code},{tp},,,{count + 100},qfq")
            raw = _http_get(url)
            j = json.loads(raw)
            data_node = j.get("data", {})
            if isinstance(data_node, dict):
                data_node = data_node.get(f"{prefix}{code}", {})
                candidates = [f"qfq{tp}", tp, f"qfq{period_map[period]}", period_map[period]]
                rows = None
                for k in candidates:
                    rows = data_node.get(k)
                    if rows:
                        break
                if rows:
                    result = []
                    for r in rows:
                        result.append({
                            "date": r[0],
                            "open": float(r[1]), "close": float(r[2]),
                            "high": float(r[3]), "low": float(r[4]),
                            "volume": float(r[5]),
                        })
                    return result[-count:]
        except Exception as e:
            failures.append(f"腾讯API: {e}")

        # 2. 新浪API
        scale_map = {"daily": 240, "weekly": 1200, "monthly": 7200}
        scale = scale_map.get(period, 240)
        sina_url = (f"https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/"
                    f"CN_MarketData.getKLineData?symbol={prefix}{code}&scale={scale}&ma=no&datalen={count}")
        try:
            raw_sina = _http_get(sina_url)
            rows_sina = json.loads(raw_sina)
            if rows_sina and isinstance(rows_sina, list) and len(rows_sina) > 0:
                result = []
                for r in rows_sina:
                    result.append({
                        "date": r["day"],
                        "open": float(r["open"]),
                        "close": float(r["close"]),
                        "high": float(r["high"]),
                        "low": float(r["low"]),
                        "volume": float(r["volume"]),
                    })
                return result[-count:]
            raise RuntimeError("新浪行情数据为空")
        except Exception as e:
            failures.append(f"新浪API: {e}")

        # 3. baostock
        try:
            bs_rows = _bs_kline(sym, period, count)
            if bs_rows is not None and len(bs_rows) > 0:
                return bs_rows[-count:]
            failures.append("baostock: 返回空数据")
        except Exception as e:
            failures.append(f"baostock: {e}")

        # 4. 雪球 (可选, 需 --xueqiu-token)
        if _XUEQIU_TOKEN:
            try:
                xq_rows = _xueqiu_kline(sym, period, count, _XUEQIU_TOKEN)
                if xq_rows is not None and len(xq_rows) > 0:
                    return xq_rows[-count:]
                failures.append("雪球: 返回空数据")
            except Exception as e:
                failures.append(f"雪球: {e}")
        else:
            failures.append("雪球: 跳过(未配置 --xueqiu-token)")

        # 5. yfinance 兜底
        try:
            yf_rows = _yf_kline(sym, period, count)
            if yf_rows is not None and len(yf_rows) > 0:
                return yf_rows[-count:]
            failures.append("yfinance: 返回空数据")
        except Exception as e:
            failures.append(f"yfinance: {e}")

        raise RuntimeError(
            f"{symbol} {tp} A股数据获取失败, 路由链: {' → '.join(failures)}"
        )

    # ──────────────────── 港股路由 ────────────────────
    elif market == "hk":
        # 标准化: 去掉hk前缀或直接使用
        if sym.lower().startswith("hk") and len(sym) >= 3:
            hk_code = sym[2:]
        elif sym.isdigit() and len(sym) == 5:
            hk_code = sym
        else:
            hk_code = sym
        hk_sym = f"hk{hk_code}"

        # 1. 腾讯API (传hk前缀)
        try:
            url = (f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
                   f"?param={hk_sym},{tp},,,{count + 100},qfq")
            raw = _http_get(url)
            j = json.loads(raw)
            data_node = j.get("data", {})
            if isinstance(data_node, dict):
                data_node = data_node.get(hk_sym, {})
                candidates = [f"qfq{tp}", tp, f"qfq{period_map[period]}", period_map[period]]
                rows = None
                for k in candidates:
                    rows = data_node.get(k)
                    if rows:
                        break
                if rows:
                    result = []
                    for r in rows:
                        result.append({
                            "date": r[0],
                            "open": float(r[1]), "close": float(r[2]),
                            "high": float(r[3]), "low": float(r[4]),
                            "volume": float(r[5]),
                        })
                    return result[-count:]
        except Exception as e:
            failures.append(f"腾讯API(港股): {e}")

        # 2. yfinance (.HK后缀)
        try:
            yf_rows = _yf_kline(f"{hk_code}.HK", period, count)
            if yf_rows is not None and len(yf_rows) > 0:
                return yf_rows[-count:]
            failures.append("yfinance(港股): 返回空数据")
        except Exception as e:
            failures.append(f"yfinance(港股): {e}")

        # 3. 雪球 (可选, 需 --xueqiu-token)
        if _XUEQIU_TOKEN:
            try:
                xq_rows = _xueqiu_kline(f"hk{hk_code}", period, count, _XUEQIU_TOKEN)
                if xq_rows is not None and len(xq_rows) > 0:
                    return xq_rows[-count:]
                failures.append("雪球(港股): 返回空数据")
            except Exception as e:
                failures.append(f"雪球(港股): {e}")
        else:
            failures.append("雪球(港股): 跳过(未配置 --xueqiu-token)")

        raise RuntimeError(
            f"{symbol} {tp} 港股数据获取失败, 路由链: {' → '.join(failures)}"
        )

    # ──────────────────── 全球/美股路由 ────────────────────
    else:
        # 1. yfinance
        try:
            yf_rows = _yf_kline(sym, period, count)
            if yf_rows is not None and len(yf_rows) > 0:
                return yf_rows[-count:]
            failures.append("yfinance: 返回空数据")
        except Exception as e:
            failures.append(f"yfinance: {e}")

        # 2. 雪球 (可选, 需 --xueqiu-token)
        if _XUEQIU_TOKEN:
            try:
                xq_rows = _xueqiu_kline(sym, period, count, _XUEQIU_TOKEN)
                if xq_rows is not None and len(xq_rows) > 0:
                    return xq_rows[-count:]
                failures.append("雪球: 返回空数据")
            except Exception as e:
                failures.append(f"雪球: {e}")
        else:
            failures.append("雪球: 跳过(未配置 --xueqiu-token)")

        # 3. stooq (可选, 需 --stooq-apikey)
        if _STOOQ_APIKEY:
            try:
                st_rows = _stooq_kline(sym, period, count, _STOOQ_APIKEY)
                if st_rows is not None and len(st_rows) > 0:
                    return st_rows[-count:]
                failures.append("stooq: 返回空数据")
            except Exception as e:
                failures.append(f"stooq: {e}")
        else:
            failures.append("stooq: 跳过(未配置 --stooq-apikey)")

        # 4. 自定义API (可选, 需 --custom-api)
        if _CUSTOM_API_URL:
            try:
                ca_rows = _custom_api_kline(sym, period, count, _CUSTOM_API_URL)
                if ca_rows is not None and len(ca_rows) > 0:
                    return ca_rows[-count:]
                failures.append("自定义API: 返回空数据")
            except Exception as e:
                failures.append(f"自定义API: {e}")
        else:
            failures.append("自定义API: 跳过(未配置 --custom-api)")

        raise RuntimeError(
            f"{symbol} {tp} 全球数据获取失败, 路由链: {' → '.join(failures)}"
        )


# ──────────────────── 指标计算 ────────────────────

def calc_sma(close, length):
    """简单移动平均"""
    out = np.full(len(close), np.nan)
    if length > len(close):
        return out
    cs = np.cumsum(close)
    cs[length:] = cs[length:] - cs[:-length]
    out[length - 1:] = cs[length - 1:] / length
    return out


# ──────────────────── 回测引擎 ────────────────────

def backtest_single(close, ma_len, strategy="Long Only"):
    """单均线反转回测: 价格上穿SMA买入, 下穿卖出"""
    if ma_len >= len(close):
        return 0, 0.0, 0.0, -1e10
    xma = calc_sma(close, ma_len)
    total_trades = 0
    winning_trades = 0
    total_profit = 0.0
    total_loss = 0.0
    entry_long = np.nan
    entry_short = np.nan

    for i in range(1, len(close)):
        if np.isnan(xma[i]) or np.isnan(xma[i - 1]):
            continue
        cross_over = close[i - 1] <= xma[i - 1] and close[i] > xma[i]
        cross_under = close[i - 1] >= xma[i - 1] and close[i] < xma[i]

        if strategy == "Buy & Sell":
            if cross_over and np.isnan(entry_long) and np.isnan(entry_short):
                entry_long = close[i]; total_trades += 1
            elif cross_under and not np.isnan(entry_long):
                p = close[i] - entry_long
                if p > 0: total_profit += p; winning_trades += 1
                else: total_loss += -p
                entry_long = np.nan; entry_short = close[i]; total_trades += 1
            elif cross_under and np.isnan(entry_short) and np.isnan(entry_long):
                entry_short = close[i]; total_trades += 1
            elif cross_over and not np.isnan(entry_short):
                p = entry_short - close[i]
                if p > 0: total_profit += p; winning_trades += 1
                else: total_loss += -p
                entry_short = np.nan; entry_long = close[i]; total_trades += 1
        else:  # Long Only
            if np.isnan(entry_long) and cross_over:
                entry_long = close[i]; total_trades += 1
            elif not np.isnan(entry_long) and cross_under:
                p = close[i] - entry_long
                if p > 0: total_profit += p; winning_trades += 1
                else: total_loss += -p
                entry_long = np.nan

    if total_trades == 0:
        return 0, 0.0, 0.0, -1e10
    win_rate = winning_trades / total_trades
    pf = total_profit / total_loss if total_loss > 0 else (10000.0 if total_profit > 0 else 0.0)
    if total_trades >= 1 and not math.isnan(pf) and pf >= 0:
        robustness = pf * math.log(total_trades) * math.sqrt(win_rate)
    else:
        robustness = -1e10
    return total_trades, pf, win_rate, robustness


def backtest_cross(close, fast_len, slow_len, strategy="Long Only"):
    """双均线交叉回测: fast上穿slow(金叉)买入, 下穿(死叉)卖出"""
    if slow_len >= len(close):
        return 0, 0.0, 0.0, -1e10

    fast_ma = calc_sma(close, fast_len)
    slow_ma = calc_sma(close, slow_len)

    total_trades = 0
    winning_trades = 0
    total_profit = 0.0
    total_loss = 0.0
    entry_long = np.nan
    entry_short = np.nan

    for i in range(1, len(close)):
        if np.isnan(fast_ma[i]) or np.isnan(slow_ma[i]):
            continue
        if np.isnan(fast_ma[i - 1]) or np.isnan(slow_ma[i - 1]):
            continue

        # 金叉: fast上穿slow
        golden = fast_ma[i - 1] <= slow_ma[i - 1] and fast_ma[i] > slow_ma[i]
        # 死叉: fast下穿slow
        death = fast_ma[i - 1] >= slow_ma[i - 1] and fast_ma[i] < slow_ma[i]

        if strategy == "Buy & Sell":
            if golden and np.isnan(entry_long) and np.isnan(entry_short):
                entry_long = close[i]; total_trades += 1
            elif death and not np.isnan(entry_long):
                p = close[i] - entry_long
                if p > 0: total_profit += p; winning_trades += 1
                else: total_loss += -p
                entry_long = np.nan; entry_short = close[i]; total_trades += 1
            elif death and np.isnan(entry_short) and np.isnan(entry_long):
                entry_short = close[i]; total_trades += 1
            elif golden and not np.isnan(entry_short):
                p = entry_short - close[i]
                if p > 0: total_profit += p; winning_trades += 1
                else: total_loss += -p
                entry_short = np.nan; entry_long = close[i]; total_trades += 1
        else:  # Long Only
            if np.isnan(entry_long) and golden:
                entry_long = close[i]; total_trades += 1
            elif not np.isnan(entry_long) and death:
                p = close[i] - entry_long
                if p > 0: total_profit += p; winning_trades += 1
                else: total_loss += -p
                entry_long = np.nan

    if total_trades == 0:
        return 0, 0.0, 0.0, -1e10
    win_rate = winning_trades / total_trades
    pf = total_profit / total_loss if total_loss > 0 else (10000.0 if total_profit > 0 else 0.0)
    if total_trades >= 1 and not math.isnan(pf) and pf >= 0:
        robustness = pf * math.log(total_trades) * math.sqrt(win_rate)
    else:
        robustness = -1e10
    return total_trades, pf, win_rate, robustness


def backtest_pullback(close, ma_len, hold_bars=120):
    """回踩均线买入并长期持有:
    价格从均线上方回踩(触及或略微跌破均线后反弹)时买入,
    持有 hold_bars 根K线后卖出.
    """
    if ma_len >= len(close):
        return 0, 0.0, 0.0, -1e10
    xma = calc_sma(close, ma_len)
    trades = 0
    winning = 0
    total_profit = 0.0
    total_loss = 0.0

    for i in range(1, len(close)):
        if np.isnan(xma[i]) or np.isnan(xma[i - 1]):
            continue

        # 回踩条件: 前一根K线在均线附近或下方, 当前回到均线上方
        pullback = (close[i - 1] <= xma[i - 1] * 1.005 and close[i] > xma[i])

        if pullback:
            exit_idx = i + hold_bars
            if exit_idx >= len(close):
                break
            entry = close[i]
            exit_price = close[exit_idx]
            p = exit_price - entry
            if p > 0:
                total_profit += p
                winning += 1
            else:
                total_loss += -p
            trades += 1

    if trades == 0:
        return 0, 0.0, 0.0, -1e10
    win_rate = winning / trades
    pf = total_profit / total_loss if total_loss > 0 else (10000.0 if total_profit > 0 else 0.0)
    if trades >= 1 and not math.isnan(pf) and pf >= 0:
        robustness = pf * math.log(trades) * math.sqrt(win_rate)
    else:
        robustness = -1e10
    return trades, pf, win_rate, robustness


# ──────────────────── KNN 增强模块 ────────────────────

def extract_features(close, high, low, window=60):
    """提取当前市场状态特征向量"""
    n = len(close)
    if n < window + 20:
        return None
    recent = close[n - window:]
    rets = np.diff(recent) / recent[:-1]
    vol = np.std(rets) / (np.mean(np.abs(rets)) + 1e-10)
    mom = (close[-1] - close[-21]) / close[-21]
    trend = (recent[-1] - recent[0]) / recent[0]
    rng = np.mean(high[n - window:] - low[n - window:]) / (np.mean(recent) + 1e-10)
    return np.array([vol, mom, trend, rng])


def build_feature_matrix(close, high, low, window=60, step=20):
    """在历史序列上每隔 step 根提取一个特征向量"""
    n = len(close)
    features, indices = [], []
    for end in range(window + 20, n, step):
        f = extract_features(close[:end], high[:end], low[:end], window)
        if f is not None:
            features.append(f)
            indices.append(end)
    if not features:
        return None, None
    return np.array(features), indices


def knn_recommend(close, high, low, candidates, backtest_fn, k=7, window=60):
    """
    KNN 增强: 从 candidates 中找出"当前市场状态下最适配"的均线/均线对。
    backtest_fn: backtest_single 或 backtest_cross
    candidates: 单均线 [(sma_len, trades, pf, wr, rob), ...]
                双均线 [(fast, slow, trades, pf, wr, rob), ...]
    """
    current_feat = extract_features(close, high, low, window)
    if current_feat is None:
        return candidates[0]

    feat_matrix, feat_indices = build_feature_matrix(close, high, low, window, step=20)
    if feat_matrix is None or len(feat_matrix) < k:
        return candidates[0]

    feat_all = np.vstack([current_feat.reshape(1, -1), feat_matrix])
    mins = feat_all.min(axis=0)
    maxs = feat_all.max(axis=0)
    ranges = maxs - mins + 1e-10
    current_norm = (current_feat - mins) / ranges
    feat_norm = (feat_matrix - mins) / ranges

    dists = np.sqrt(np.sum((feat_norm - current_norm) ** 2, axis=1))
    knn_idx = np.argsort(dists)[:k]

    # 提取候选的key: 单均线用sma_len, 双均线用(fast,slow)
    cand_keys = []
    for c in candidates:
        if len(c) == 5:  # 单均线: (sma_len, trades, pf, wr, rob)
            cand_keys.append((c[0],))
        else:  # 双均线: (fast, slow, trades, pf, wr, rob)
            cand_keys.append((c[0], c[1]))

    candidate_scores = {k: 0.0 for k in cand_keys}
    candidate_counts = {k: 0 for k in cand_keys}

    for idx in knn_idx:
        center = feat_indices[idx]
        start = max(0, center - window)
        end = min(len(close), center + window)
        local_close = close[start:end]

        for ci, c in enumerate(candidates):
            key = cand_keys[ci]
            if len(key) == 1:  # 单均线
                _, pf_local, wr_local, _ = backtest_fn(local_close, key[0], "Long Only")
            else:  # 双均线
                _, pf_local, wr_local, _ = backtest_fn(local_close, key[0], key[1], "Long Only")
            if pf_local > 0:
                candidate_scores[key] += pf_local
                candidate_counts[key] += 1

    best_key = cand_keys[0]
    best_avg_pf = -1.0
    for k_ in cand_keys:
        cnt = candidate_counts[k_]
        if cnt > 0:
            avg_pf = candidate_scores[k_] / cnt
            if avg_pf > best_avg_pf:
                best_avg_pf = avg_pf
                best_key = k_

    for c in candidates:
        if len(c) == 5 and (c[0],) == best_key:
            return c
        if len(c) == 6 and (c[0], c[1]) == best_key:
            return c
    return candidates[0]


# ──────────────────── 智能周期转换 ────────────────────

def fmt_natural(sma_len, period):
    """日线SMA>=60自动换算等价周线"""
    if period == "daily" and sma_len >= 60:
        wk = round(sma_len / 5)
        return f"SMA {sma_len}（等价周线 SMA {wk}）"
    return f"SMA {sma_len}"


def fmt_pair(fast_len, slow_len, period):
    """双均线对的智能展示"""
    f = fmt_natural(fast_len, period)
    s = fmt_natural(slow_len, period)
    return f"{f} × {s}"


# ──────────────────── 扫描引擎 ────────────────────

def scan_single(close, args):
    """单均线暴力枚举扫描"""
    results = []
    total = len(range(args.start, args.end + 1, args.step))
    for idx, L in enumerate(range(args.start, args.end + 1, args.step)):
        tt, pf, wr, rob = backtest_single(close, L, args.strategy)
        if tt >= args.min_trades and rob > -1e9:
            results.append((L, tt, pf, wr, rob))
        if (idx + 1) % 20 == 0 or idx == total - 1:
            print(f"  进度 {idx + 1}/{total} ...", end="\r")
    print()
    return results


def scan_cross(close, args):
    """双均线交叉暴力枚举扫描"""
    results = []
    lengths = list(range(args.start, args.end + 1, args.step))
    total_pairs = sum(max(0, len(lengths) - i - 1) for i in range(len(lengths)))
    count = 0
    for i, fast_len in enumerate(lengths):
        for slow_len in lengths[i + 1:]:
            tt, pf, wr, rob = backtest_cross(close, fast_len, slow_len, args.strategy)
            if tt >= args.min_trades and rob > -1e9:
                results.append((fast_len, slow_len, tt, pf, wr, rob))
            count += 1
            if count % 50 == 0 or count == total_pairs:
                print(f"  进度 {count}/{total_pairs} ...", end="\r")
    print()
    return results


# ──────────────────── 输出渲染 ────────────────────

def scan_hold(close, args):
    """回踩均线长期持有扫描"""
    results = []
    hold_bars = args.hold_bars or 120
    total = len(range(args.start, args.end + 1, args.step))
    for idx, L in enumerate(range(args.start, args.end + 1, args.step)):
        tt, pf, wr, rob = backtest_pullback(close, L, hold_bars)
        if tt >= args.min_trades and rob > -1e9:
            results.append((L, tt, pf, wr, rob))
        if (idx + 1) % 20 == 0 or idx == total - 1:
            print(f"  进度 {idx + 1}/{total} ...", end="\r")
    print()
    return results


def print_single_results(results, args, top_n):
    """输出单均线结果"""
    if not results:
        print("  无满足条件的均线周期")
        return None
    results.sort(key=lambda x: x[4], reverse=True)
    top = results[:top_n]
    best = top[0]

    print(f"  [单均线] 最优 {fmt_natural(best[0], args.period)}")
    print(f"  交易次数={best[1]}  盈亏比(PF)={best[2]:.2f}  胜率={best[3]*100:.1f}%  得分={best[4]:.2f}")
    print(f"  {'─' * 56}")
    print(f"  Top {len(top)} 候选:")
    for r in top:
        marker = " ★" if r == best else ""
        pf_label = "盈利" if r[2] >= 1 else "亏损"
        print(f"    {fmt_natural(r[0], args.period):<25} | 交易={r[1]:>4} | 盈亏比={r[2]:6.2f} | 胜率={r[3]*100:5.1f}% | 得分={r[4]:7.2f}{marker} ({pf_label})")
    
    # 双维度推荐: 按胜率 vs 按盈亏比
    if len(results) >= 2:
        by_wr = sorted(results, key=lambda x: x[3], reverse=True)[0]
        by_pf = sorted(results, key=lambda x: x[2], reverse=True)[0]
        print(f"\n  选择参考（按自己的风格选 ↓）:")
        print(f"    按胜率最优: {fmt_natural(by_wr[0], args.period):<25} | 胜率={by_wr[3]*100:5.1f}% | 盈亏比(PF)={by_wr[2]:.2f} | 交易={by_wr[1]:>4}")
        print(f"    按盈亏比(PF)最优: {fmt_natural(by_pf[0], args.period):<25} | 盈亏比(PF)={by_pf[2]:.2f} | 胜率={by_pf[3]*100:5.1f}% | 交易={by_pf[1]:>4}")
        print(f"    ※ 盈亏比(PF)=总盈利÷总亏损, >1说明赚钱。高胜率≠赚钱, 低胜率高盈亏比也能赚。")
    
    return top


def print_cross_results(results, args, top_n):
    """输出双均线交叉结果"""
    if not results:
        print("  无满足条件的均线组合")
        return None
    results.sort(key=lambda x: x[4], reverse=True)
    top = results[:top_n]
    best = top[0]

    print(f"  [双均线交叉] 最优 {fmt_pair(best[0], best[1], args.period)}")
    print(f"  交易次数={best[2]}  盈亏比(PF)={best[3]:.2f}  胜率={best[4]*100:.1f}%  得分={best[5]:.2f}")
    print(f"  {'─' * 56}")
    print(f"  Top {len(top)} 候选:")
    for r in top:
        marker = " ★" if r == best else ""
        pf_label = "盈利" if r[3] >= 1 else "亏损"
        print(f"    {fmt_pair(r[0], r[1], args.period):<40} | 交易={r[2]:>4} | 盈亏比={r[3]:6.2f} | 胜率={r[4]*100:5.1f}% | 得分={r[5]:7.2f}{marker} ({pf_label})")
    
    # 双维度推荐: 按胜率 vs 按盈亏比
    if len(results) >= 2:
        by_wr = sorted(results, key=lambda x: x[4], reverse=True)[0]
        by_pf = sorted(results, key=lambda x: x[3], reverse=True)[0]
        print(f"\n  选择参考（按自己的风格选 ↓）:")
        print(f"    按胜率最优: {fmt_pair(by_wr[0], by_wr[1], args.period):<40} | 胜率={by_wr[4]*100:5.1f}% | 盈亏比(PF)={by_wr[3]:.2f} | 交易={by_wr[2]:>4}")
        print(f"    按盈亏比(PF)最优: {fmt_pair(by_pf[0], by_pf[1], args.period):<40} | 盈亏比(PF)={by_pf[3]:.2f} | 胜率={by_pf[4]*100:5.1f}% | 交易={by_pf[2]:>4}")
        print(f"    ※ 盈亏比(PF)=总盈利÷总亏损, >1说明赚钱。高胜率≠赚钱, 低胜率高盈亏比也能赚。")
    
    return top


def print_hold_results(results, args, hold_label, top_n):
    """输出回踩持有结果"""
    if not results:
        print("  无满足条件的均线周期")
        return None
    results.sort(key=lambda x: x[4], reverse=True)
    top = results[:top_n]
    best = top[0]

    print(f"  [回踩持有 {hold_label}] 最优 {fmt_natural(best[0], args.period)}")
    print(f"  交易次数={best[1]}  盈亏比(PF)={best[2]:.2f}  胜率={best[3]*100:.1f}%  得分={best[4]:.2f}")
    print(f"  {'─' * 56}")
    print(f"  Top {len(top)} 候选:")
    for r in top:
        marker = " ★" if r == best else ""
        pf_label = "盈利" if r[2] >= 1 else "亏损"
        print(f"    {fmt_natural(r[0], args.period):<25} | 交易={r[1]:>4} | 盈亏比={r[2]:6.2f} | 胜率={r[3]*100:5.1f}% | 得分={r[4]:7.2f}{marker} ({pf_label})")

    if len(results) >= 2:
        by_wr = sorted(results, key=lambda x: x[3], reverse=True)[0]
        by_pf = sorted(results, key=lambda x: x[2], reverse=True)[0]
        print(f"\n  选择参考（按自己的风格选 ↓）:")
        print(f"    按胜率最优: {fmt_natural(by_wr[0], args.period):<25} | 胜率={by_wr[3]*100:5.1f}% | 盈亏比(PF)={by_wr[2]:.2f} | 交易={by_wr[1]:>4}")
        print(f"    按盈亏比(PF)最优: {fmt_natural(by_pf[0], args.period):<25} | 盈亏比(PF)={by_pf[2]:.2f} | 胜率={by_pf[3]*100:5.1f}% | 交易={by_pf[1]:>4}")
        print(f"    ※ 盈亏比(PF)=总盈利÷总亏损, >1说明赚钱。高胜率≠赚钱, 低胜率高盈亏比也能赚。")

    return top


# ──────────────────── 无忧线模式（回踩买入·永久持有） ────────────────────

def backtest_eternal(close, ma_len, dates=None, period="daily"):
    """无忧线回测：价格回踩均线买入，持有至数据末尾。
    统计: 胜率、平均收益率、损益比、最大被套时长、最大浮亏深度
    """
    if ma_len >= len(close):
        return 0, 0.0, 0.0, 0.0, -1e10, 0, 0.0, 0, 0.0
    xma = calc_sma(close, ma_len)
    trades = 0
    winning = 0
    total_profit = 0.0
    total_loss = 0.0
    total_return_pct = 0.0
    last_close = close[-1]

    # 被套统计
    max_drawdown_bars = 0      # 最大被套时长(K线数)
    total_drawdown_bars = 0    # 所有交易被套时长总和
    max_drawdown_pct = 0.0     # 最大浮亏深度(%)
    total_drawdown_pct = 0.0   # 所有交易浮亏深度总和

    for i in range(ma_len + 1, len(close) - 1):
        if np.isnan(xma[i]) or np.isnan(xma[i - 1]):
            continue
        # 回踩条件: 前一根K线在均线附近或下方(≤1.005倍)，当前回到均线上方
        pullback = (close[i - 1] <= xma[i - 1] * 1.005 and close[i] > xma[i])
        if not pullback:
            continue

        entry = close[i]
        ret_pct = (last_close - entry) / entry * 100
        if ret_pct > 0:
            total_profit += ret_pct
            winning += 1
        else:
            total_loss += -ret_pct
        total_return_pct += ret_pct

        # 追踪被套情况：从买入点到数据末尾
        running_min = entry
        running_min_idx = i
        recovered = False
        recovery_bars = 0
        for j in range(i + 1, len(close)):
            if close[j] < running_min:
                running_min = close[j]
                running_min_idx = j
            if not recovered and close[j] >= entry:
                recovered = True
                recovery_bars = j - i

        drawdown_pct = (entry - running_min) / entry * 100
        drawdown_bars = running_min_idx - i

        if drawdown_bars > max_drawdown_bars:
            max_drawdown_bars = drawdown_bars
        if drawdown_pct > max_drawdown_pct:
            max_drawdown_pct = drawdown_pct
        total_drawdown_bars += drawdown_bars
        total_drawdown_pct += drawdown_pct
        trades += 1

    if trades == 0:
        return 0, 0.0, 0.0, 0.0, -1e10, 0, 0.0, 0, 0.0
    win_rate = winning / trades
    avg_return = total_return_pct / trades
    pf = total_profit / total_loss if total_loss > 0 else (10000.0 if total_profit > 0 else 0.0)
    avg_drawdown_bars = total_drawdown_bars / trades
    avg_drawdown_pct = total_drawdown_pct / trades
    # 评分: 侧重胜率(无忧感)和获利质量
    safety = win_rate * win_rate * math.sqrt(pf) if pf > 0 else -1e10
    return trades, pf, win_rate, avg_return, safety, max_drawdown_bars, max_drawdown_pct, avg_drawdown_bars, avg_drawdown_pct


def scan_eternal(close, args, dates=None):
    """无忧线暴力枚举扫描"""
    results = []
    total = len(range(args.start, args.end + 1, args.step))
    for idx, L in enumerate(range(args.start, args.end + 1, args.step)):
        tt, pf, wr, avg_ret, safety, mdb, mdp, adb, adp = backtest_eternal(close, L, dates, args.period)
        if tt >= args.min_trades and safety > -1e9:
            results.append((L, tt, pf, wr, avg_ret, safety, mdb, mdp, adb, adp))
        if (idx + 1) % 20 == 0 or idx == total - 1:
            print(f"  进度 {idx + 1}/{total} ...", end="\r")
    print()
    return results


def print_eternal_results(results, args, top_n):
    """输出无忧线结果（含被套时长/浮亏深度）"""
    if not results:
        print("  无满足条件的均线周期")
        return None

    # 把K线数转为"年/月"等可读时长
    def bars_to_readable(bars, period):
        if period == "daily":
            y = bars / 250
            if y >= 1: return f"{y:.1f}年"
            m = bars / 21
            return f"{m:.0f}个月"
        elif period == "weekly":
            y = bars / 50
            if y >= 1: return f"{y:.1f}年"
            m = bars / 4.3
            return f"{m:.0f}个月"
        else:  # monthly
            y = bars / 12
            return f"{y:.1f}年"

    results.sort(key=lambda x: x[5], reverse=True)
    top = results[:top_n]
    best = top[0]

    # 解包
    L, tt, pf, wr, avg_ret, safety, mdb, mdp, adb, adp = best

    print(f"  🛡️ 无忧线: {fmt_natural(L, args.period)}")
    print(f"  交易={tt:>3}次 | 胜率={wr*100:.1f}% | 盈亏比(PF)={pf:.2f} | 均收益={avg_ret:+.1f}% | 安全分={safety:.1f}")
    # 被套信息
    print(f"  最大被套⏱ {bars_to_readable(mdb, args.period)} | 平均被套 {bars_to_readable(adb, args.period)}")
    print(f"  最大浮亏📉 {mdp:.1f}% | 平均浮亏 {adp:.1f}%")
    print(f"  {'─' * 60}")
    print(f"  Top {len(top)} 候选（按安全分排序）:")
    for r in top:
        marker = " ★" if r == best else ""
        risk_note = "🟢无忧" if r[3] >= 0.9 else ("🟡安心" if r[3] >= 0.7 else "⚪参考")
        print(f"    {fmt_natural(r[0], args.period):<25} | 交易={r[1]:>3} | 胜率={r[3]*100:5.1f}% | PF={r[2]:6.2f} | 均收益={r[4]:+.1f}% | 被套最长{bars_to_readable(r[6], args.period)} {risk_note}{marker}")

    # 双维度推荐
    if len(results) >= 2:
        by_wr = sorted(results, key=lambda x: x[3], reverse=True)[0]
        by_pf = sorted(results, key=lambda x: x[2], reverse=True)[0]
        by_ret = sorted(results, key=lambda x: x[4], reverse=True)[0]
        # 考虑被套时长再推荐"性价比"
        by_comfort = sorted(results, key=lambda x: (x[3] * x[3] * math.sqrt(x[2])) / (1 + x[6] / max(1, x[1])), reverse=True)[0]
        print(f"\n  选择参考（按自己的偏好选 ↓）:")
        print(f"    最无忧(胜率最高): {fmt_natural(by_wr[0], args.period):<25} | 胜率={by_wr[3]*100:.1f}% | 均收益={by_wr[4]:+.1f}%")
        print(f"    盈利最强(盈亏比): {fmt_natural(by_pf[0], args.period):<25} | PF={by_pf[2]:.2f} | 胜率={by_pf[3]*100:.1f}%")
        print(f"    收益最高(平均):   {fmt_natural(by_ret[0], args.period):<25} | 均收益={by_ret[4]:+.1f}% | 胜率={by_ret[3]*100:.1f}%")
        print(f"    ※ 无忧线=回踩该均线买入并永久持有, 胜率越高说明越不会被套")
        print(f"    ※ 被套时长=买入到浮亏最深处的时长, 浮亏深度=期间最多亏百分之几")
        print(f"    ※ 以上为历史回测数据, 不代表未来收益, 不构成投资建议")

    return top


def print_trend_warning(all_pf_below_one):
    """趋势走坏提示"""
    if all_pf_below_one:
        print(f"\n  ⚠️  趋势判断: 所有周期PF均≤1, 该标的趋势走坏, 不建议买入")
        print(f"      含义: 无论用哪条均线, 历史回测都是亏的 → 趋势不成立")


# ──────────────────── 主入口 ────────────────────

def main():
    parser = argparse.ArgumentParser(description="Best SMA Finder v2.1.0")
    parser.add_argument("--symbol", required=True, help="股票代码: 600519 / 300059")
    parser.add_argument("--strategy", default="Long Only", choices=["Long Only", "Buy & Sell"])
    parser.add_argument("--min_trades", type=int, default=50)
    parser.add_argument("--start", type=int, default=10, help="SMA周期下界")
    parser.add_argument("--end", type=int, default=200, help="SMA周期上界")
    parser.add_argument("--step", type=int, default=5, help="周期步长")
    parser.add_argument("--period", default="daily", choices=["daily", "weekly", "monthly"])
    parser.add_argument("--bars", type=int, default=1200, help="回测K线数量")
    parser.add_argument("--compare", action="store_true",
                        help="同时跑日/周/月三周期, 对比选出最优")
    parser.add_argument("--method", default="single", choices=["single", "cross", "both", "hold", "eternal"],
                        help="single=单均线, cross=双均线交叉, both=同时跑两种, hold=回踩持有, eternal=无忧线(回踩买入永久持有)")
    parser.add_argument("--top", type=int, default=10, help="展示前N候选")
    parser.add_argument("--mode", default="brute", choices=["brute", "knn"],
                        help="brute=暴力枚举, knn=KNN增强")
    parser.add_argument("--knn_k", type=int, default=7, help="KNN近邻数")
    parser.add_argument("--hold_bars", type=int, default=0,
                        help="回踩持有模式的持有K线数, 默认日线120≈6个月, 周线48≈1年")
    parser.add_argument("--xueqiu-token", default="", help="雪球 xq_a_token（可选）")
    parser.add_argument("--stooq-apikey", default="", help="stooq.com API Key（可选）")
    parser.add_argument("--custom-api", default="", help="自定义数据源URL模板（可选），如 https://example.com/api?symbol={symbol}&period={period}&count={count}")
    args = parser.parse_args()

    global _XUEQIU_TOKEN, _STOOQ_APIKEY, _CUSTOM_API_URL
    _XUEQIU_TOKEN = args.xueqiu_token
    _STOOQ_APIKEY = args.stooq_apikey
    _CUSTOM_API_URL = args.custom_api

    # ──────────────────── 多周期对比模式 ────────────────────
    if args.compare:
        _run_compare(args)
        return

    # ──────────────────── 单周期模式 ────────────────────
    print(f"[Best SMA] 加载 {args.symbol} 历史K线 ...")
    try:
        data = fetch_kline(args.symbol, args.period, args.bars)
    except Exception as e:
        print(f"数据获取失败: {e}")
        sys.exit(3)

    close = np.array([d["close"] for d in data], dtype=float)
    high = np.array([d["high"] for d in data], dtype=float)
    low = np.array([d["low"] for d in data], dtype=float)
    print(f"[Best SMA] 已加载 {len(close)} 根K线 ({data[0]['date']} ~ {data[-1]['date']})")

    method_label = {"single": "单均线", "cross": "双均线交叉", "both": "单均线+双均线", "hold": "回踩持有", "eternal": "无忧线"}
    print(f"[Best SMA] 策略={args.strategy}, 方法={method_label[args.method]}, "
          f"扫描 {args.start}~{args.end} 步长{args.step}, mode={args.mode}")

    print(f"\n{'=' * 60}")

    any_pf_above_1 = False

    if args.method in ("single", "both"):
        print(f"  Best SMA Finder  |  {args.symbol}  |  {args.strategy}  |  单均线  |  {args.period}")
        print(f"{'=' * 60}")
        print(f"\n  [单均线] 扫描中 ...")
        results_s = scan_single(close, args)
        top_s = print_single_results(results_s, args, args.top)

        if top_s:
            any_pf_above_1 = any(r[2] > 1.0 for r in top_s)

        # KNN增强 (单均线)
        if args.mode == "knn" and top_s and len(top_s) >= 2:
            print(f"\n  [KNN 增强 · 单均线] 分析当前市场状态 ...")
            knn_best = knn_recommend(close, high, low, top_s, backtest_single, k=args.knn_k)
            print(f"  KNN 推荐 SMA = {fmt_natural(knn_best[0], args.period)}")
            print(f"  交易次数={knn_best[1]}  盈亏比(PF)={knn_best[2]:.2f}  胜率={knn_best[3]*100:.1f}%  得分={knn_best[4]:.2f}")
            if top_s and knn_best[0] != top_s[0][0]:
                print(f"  ⚡ KNN 推荐与暴力最优不同! 全局最优={top_s[0][0]}, KNN当前适配={knn_best[0]}")
            else:
                print(f"  ✅ KNN 与暴力枚举一致, SMA={knn_best[0]} 全局和当前均最优")

        print(f"{'=' * 60}")

    if args.method in ("cross", "both"):
        print(f"  Best SMA Finder  |  {args.symbol}  |  {args.strategy}  |  双均线交叉  |  {args.period}")
        print(f"{'=' * 60}")
        print(f"\n  [双均线交叉] 扫描中 ...")
        results_c = scan_cross(close, args)
        top_c = print_cross_results(results_c, args, args.top)

        if top_c:
            any_pf_above_1 = any(r[3] > 1.0 for r in top_c) or any_pf_above_1

        # KNN增强 (双均线)
        if args.mode == "knn" and top_c and len(top_c) >= 2:
            print(f"\n  [KNN 增强 · 双均线] 分析当前市场状态 ...")
            knn_best = knn_recommend(close, high, low, top_c, backtest_cross, k=args.knn_k)
            print(f"  KNN 推荐 {fmt_pair(knn_best[0], knn_best[1], args.period)}")
            print(f"  交易次数={knn_best[2]}  盈亏比(PF)={knn_best[3]:.2f}  胜率={knn_best[4]*100:.1f}%  得分={knn_best[5]:.2f}")
            if top_c and (knn_best[0], knn_best[1]) != (top_c[0][0], top_c[0][1]):
                print(f"  ⚡ KNN 推荐与暴力最优不同! 全局最优={top_c[0][0]}/{top_c[0][1]}, KNN当前适配={knn_best[0]}/{knn_best[1]}")
            else:
                print(f"  ✅ KNN 与暴力枚举一致, {knn_best[0]}/{knn_best[1]} 全局和当前均最优")

        print(f"{'=' * 60}")

    # 回踩持有模式: 同时跑多种持有期
    if args.method == "hold":
        hold_options = [(60, "持有3个月(60日)"),
                        (120, "持有6个月(120日)"),
                        (250, "持有1年(250日)")]
        if args.hold_bars > 0:
            hold_options = [(args.hold_bars, f"持有{args.hold_bars}日")]

        any_pf_above_1 = False
        for hbars, hlabel in hold_options:
            print(f"\n  Best SMA Finder  |  {args.symbol}  |  回踩持有  |  {args.period}  |  {hlabel}")
            print(f"  {'─' * 60}")
            print(f"  [回踩持有] 扫描中 ...")
            results_h = scan_hold(close, args)
            args.hold_bars = hbars  # 临时覆盖
            top_h = print_hold_results(results_h, args, hlabel, args.top)
            if top_h:
                any_pf_above_1 = any(r[2] > 1.0 for r in top_h) or any_pf_above_1

        print(f"{'=' * 60}")
        if not any_pf_above_1:
            print_trend_warning(True)
        print("⚠ 历史回测不代表未来收益, 结果仅供研究参考, 不构成投资建议")
        return

    # ── 无忧线模式（回踩买入·永久持有） ──
    if args.method == "eternal":
        method_label = "无忧线(回踩买入永久持有)"
        print(f"\n  {'=' * 60}")
        print(f"  Best SMA Finder  |  {args.symbol}  |  {method_label}  |  {args.period}")
        print(f"  {'=' * 60}")
        print(f"  【无忧线】价格回踩均线买入，持有至最新K线，永不卖出")
        print(f"  扫描 SMA {args.start}~{args.end} 步长{args.step} ...")
        results_e = scan_eternal(close, args)
        top_e = print_eternal_results(results_e, args, args.top)
        if top_e:
            any_pf_above_1 = any(r[2] > 1.0 for r in top_e)
        print(f"{'=' * 60}")
        if not any_pf_above_1:
            print(f"\n  ⚠️  该周期下未找到真正的无忧线——所有买入点最终仍有人亏钱")
        print("⚠ 历史回测不代表未来收益, 结果仅供研究参考, 不构成投资建议")
        return

    if not any_pf_above_1:
        print_trend_warning(True)

    print("⚠ 历史回测不代表未来收益, 结果仅供研究参考, 不构成投资建议")


def _run_compare(args):
    """多周期对比模式"""
    periods = [("daily", 1200), ("weekly", 300), ("monthly", 150)]
    period_names = {"daily": "日线", "weekly": "周线", "monthly": "月线"}

    method_label = {"single": "单均线", "cross": "双均线交叉", "both": "单+双"}
    print(f"\n{'=' * 60}")
    print(f"  Best SMA Finder v2.1.0  |  {args.symbol}  |  {args.strategy}")
    print(f"  【多周期对比】日线 · 周线 · 月线 · {method_label[args.method]}")
    print(f"{'=' * 60}")

    all_pf_below_1 = True

    for pk, pbars in periods:
        print(f"\n  ── {period_names[pk]} ──")
        try:
            pdata = fetch_kline(args.symbol, pk, pbars)
        except Exception as e:
            print(f"  {period_names[pk]} 数据获取失败: {e}")
            continue

        pclose = np.array([d["close"] for d in pdata], dtype=float)
        phigh = np.array([d["high"] for d in pdata], dtype=float)
        plow = np.array([d["low"] for d in pdata], dtype=float)

        if args.method in ("single", "both"):
            print(f"  [单均线] 扫描中 ...")
            pr_s = []
            for L in range(args.start, args.end + 1, args.step):
                tt, pf, wr, rob = backtest_single(pclose, L, args.strategy)
                if tt >= args.min_trades and rob > -1e9:
                    pr_s.append((L, tt, pf, wr, rob))
            pr_s.sort(key=lambda x: x[4], reverse=True)

            if pr_s:
                best_s = pr_s[0]
                mark = " ★" if best_s[2] > 1 else ""
                pf_label = "盈利" if best_s[2] >= 1 else "亏损"
                sma_str = fmt_natural(best_s[0], pk)
                print(f"  单均线最优: {sma_str} | 交易={best_s[1]} | 盈亏比(PF)={best_s[2]:.2f} | 胜率={best_s[3]*100:.1f}% {mark} ({pf_label})")
                if best_s[2] > 1:
                    all_pf_below_1 = False
            else:
                print(f"  单均线: 无满足条件的周期")

        if args.method in ("cross", "both"):
            print(f"  [双均线交叉] 扫描中 ...")
            pr_c = []
            lengths = list(range(args.start, args.end + 1, args.step))
            for i, fast_len in enumerate(lengths):
                for slow_len in lengths[i + 1:]:
                    tt, pf, wr, rob = backtest_cross(pclose, fast_len, slow_len, args.strategy)
                    if tt >= args.min_trades and rob > -1e9:
                        pr_c.append((fast_len, slow_len, tt, pf, wr, rob))
            pr_c.sort(key=lambda x: x[4], reverse=True)

            if pr_c:
                best_c = pr_c[0]
                mark = " ★" if best_c[3] > 1 else ""
                pf_label = "盈利" if best_c[3] >= 1 else "亏损"
                pair_str = fmt_pair(best_c[0], best_c[1], pk)
                print(f"  双均线最优: {pair_str} | 交易={best_c[2]} | 盈亏比(PF)={best_c[3]:.2f} | 胜率={best_c[4]*100:.1f}% {mark} ({pf_label})")
                if best_c[3] > 1:
                    all_pf_below_1 = False
            else:
                print(f"  双均线: 无满足条件的组合")

        print(f"  最后K线: {pdata[-1]['date']}")

    print(f"\n  {'─' * 56}")
    if all_pf_below_1:
        print_trend_warning(True)
    else:
        print(f"  ✅ 存在PF>1的周期组合, 该标的存在可捕捉的趋势信号")

    print(f"{'=' * 60}")
    print("⚠ 历史回测不代表未来收益, 结果仅供研究参考, 不构成投资建议")


if __name__ == "__main__":
    main()
