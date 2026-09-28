"""
K线形态大师 — 核心形态检测库 (v5)
基于《股市操练大全》（第一册）+ Nison《日本蜡烛图技术》+ Pine Script 参考

v4 新增（约28种）：
  - 早晨/黄昏十字星、好友/淡友反攻、乌云盖顶、平顶/平底
  - 红三兵/三个白色武士、黑三兵/三只乌鸦
  - 两红夹一黑/两黑夹一红、升势停顿
  - 上升/下跌三部曲（自适应N字型，2~5根中间K线）
  - 多方尖兵/空方尖兵（含后续确认机制）
  - 倾盆大雨、纺锤线、长十字星、蜻蜓/墓碑十字星
  - T字线/倒T字线、徐缓上升/下降、高开出逃形、下探上涨形
  - 下降覆盖线、上涨二颗星、低位并排阳线

v5 新增（18种）：
  - 升势受阻、高位并排阳线、高位并排阴线、低位并排阴线
  - 下跌三颗星、连续跳空三阳线、连续跳空三阴线
  - 下档五阴线、分手线、一字线、跳空上扬形
  - 冉冉上升、绵绵阴跌形、稳步上涨、下跌不止形
  - 上升抵抗形、下降抵抗形（B类连续趋势，滑动窗口自适应）

v5 新增（18种）：
  - 升势受阻、高位并排阳线、高位并排阴线、低位并排阴线
  - 下跌三颗星、连续跳空三阳线、连续跳空三阴线
  - 下档五阴线、分手线、一字线、跳空上扬形
  - 冉冉上升、绵绵阴跌形、稳步上涨、下跌不止形
  - 上升抵抗形、下降抵抗形（B类连续趋势，滑动窗口自适应）

v3 保留（12种）：
  - 十字星、身怀六甲（看涨/看跌）、穿头破脚、旭日东升、曙光初现
  - 大阳线、流星线、锤头线、上吊线、黄昏之星、早晨之星

命名双标：中文名（《操练大全》优先）+ 括号英文名
分层判断：几何定义 → 趋势位置过滤 → 后续确认机制
无成交量：美股机构主导，成交量噪声高
"""

import pandas as pd
import numpy as np


# ═══════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════

def _trend_up(ohlc: pd.DataFrame, trend: int = 5) -> pd.Series:
    """过去 trend 根整体上涨"""
    return (ohlc['Close'].rolling(trend).mean() > 
            ohlc['Close'].shift(trend).rolling(trend).mean()).fillna(False)

def _trend_down(ohlc: pd.DataFrame, trend: int = 5) -> pd.Series:
    """过去 trend 根整体下跌"""
    return (ohlc['Close'].rolling(trend).mean() < 
            ohlc['Close'].shift(trend).rolling(trend).mean()).fillna(False)

def _avg_body(ohlc: pd.DataFrame, window: int = 20) -> pd.Series:
    """滚动窗口平均实体长度"""
    return (ohlc['Close'] - ohlc['Open']).abs().rolling(window, min_periods=5).mean().shift(1)

def _avg_span(ohlc: pd.DataFrame, window: int = 20) -> pd.Series:
    """滚动窗口平均振幅"""
    return (ohlc['High'] - ohlc['Low']).rolling(window, min_periods=5).mean().shift(1)

def _body(ohlc: pd.DataFrame) -> pd.Series:
    """实体绝对值"""
    return (ohlc['Close'] - ohlc['Open']).abs()

def _is_white(ohlc) -> 'pd.Series':
    """是否为阳线"""
    return ohlc['Close'] > ohlc['Open']

def _is_black(ohlc) -> 'pd.Series':
    """是否为阴线"""
    return ohlc['Close'] < ohlc['Open']

def _upper_shadow(ohlc):
    """上影线长度"""
    return ohlc['High'] - ohlc[['Open', 'Close']].max(axis=1)

def _lower_shadow(ohlc):
    """下影线长度"""
    return ohlc[['Open', 'Close']].min(axis=1) - ohlc['Low']

def _is_long_body(ohlc, window=20, multiplier=1.5):
    """是否为长实体（> 平均的 multiplier 倍）"""
    return _body(ohlc) > _avg_body(ohlc, window) * multiplier

def _is_small_body(ohlc, window=20, threshold=0.3):
    """是否为小实体（< 平均的 threshold 倍）"""
    return _body(ohlc) <= _avg_body(ohlc, window) * threshold


# ═══════════════════════════════════════════════
# 已实现 v3 形态 — 保留不变
# ═══════════════════════════════════════════════

# ── 1. 十字星 / 螺旋桨（Doji）— 自适应 ──

def detect_doji(ohlc: pd.DataFrame, doji_factor: float = 0.05,
                window: int = 20, **kwargs) -> pd.Series:
    body = (ohlc['Close'] - ohlc['Open']).abs()
    return body <= _avg_span(ohlc, window) * doji_factor


# ── 2~3. 身怀六甲（Harami）─

def detect_bearish_harami(ohlc: pd.DataFrame, trend: int = 5) -> pd.Series:
    pg = ohlc['Close'].shift(1) > ohlc['Open'].shift(1)
    cr = ohlc['Open'] > ohlc['Close']
    within = ((ohlc['Open'] <= ohlc['Close'].shift(1)) &
              (ohlc['Open'].shift(1) <= ohlc['Close']))
    smaller = ((ohlc['Open'] - ohlc['Close']) <
               (ohlc['Close'].shift(1) - ohlc['Open'].shift(1)))
    return pg & cr & within & smaller & _trend_up(ohlc, trend)

def detect_bullish_harami(ohlc: pd.DataFrame, trend: int = 5) -> pd.Series:
    pr = ohlc['Open'].shift(1) > ohlc['Close'].shift(1)
    cg = ohlc['Close'] > ohlc['Open']
    within = ((ohlc['Close'] <= ohlc['Open'].shift(1)) &
              (ohlc['Close'].shift(1) <= ohlc['Open']))
    smaller = ((ohlc['Close'] - ohlc['Open']) <
               (ohlc['Open'].shift(1) - ohlc['Close'].shift(1)))
    return pr & cg & within & smaller & _trend_down(ohlc, trend)


# ── 4~5. 穿头破脚 / 旭日东升（Engulfing）─

def detect_bearish_engulfing(ohlc: pd.DataFrame, trend: int = 5) -> pd.Series:
    pg = ohlc['Close'].shift(1) > ohlc['Open'].shift(1)
    cr = ohlc['Open'] > ohlc['Close']
    eng = ((ohlc['Open'] >= ohlc['Close'].shift(1)) &
           (ohlc['Open'].shift(1) >= ohlc['Close']))
    bigger = ((ohlc['Open'] - ohlc['Close']) >
              (ohlc['Close'].shift(1) - ohlc['Open'].shift(1)))
    return pg & cr & eng & bigger & _trend_up(ohlc, trend)

def detect_bullish_engulfing(ohlc: pd.DataFrame, trend: int = 5) -> pd.Series:
    pr = ohlc['Open'].shift(1) > ohlc['Close'].shift(1)
    cg = ohlc['Close'] > ohlc['Open']
    eng = ((ohlc['Close'] >= ohlc['Open'].shift(1)) &
           (ohlc['Close'].shift(1) >= ohlc['Open']))
    bigger = ((ohlc['Close'] - ohlc['Open']) >
              (ohlc['Open'].shift(1) - ohlc['Close'].shift(1)))
    return pr & cg & eng & bigger & _trend_down(ohlc, trend)


# ── 6. 曙光初现（Piercing）─

def detect_piercing(ohlc: pd.DataFrame, trend: int = 5) -> pd.Series:
    pr = ohlc['Close'].shift(1) < ohlc['Open'].shift(1)
    cg = ohlc['Close'] > ohlc['Open']
    gd = ohlc['Open'] < ohlc['Low'].shift(1)
    mid = ohlc['Close'].shift(1) + ((ohlc['Open'].shift(1) - ohlc['Close'].shift(1)) / 2)
    pierce = ohlc['Close'] > mid
    not_full = ohlc['Close'] < ohlc['Open'].shift(1)
    return pr & cg & gd & pierce & not_full & _trend_down(ohlc, trend)


# ── 7. 大阳线（捉腰带线 / Big White Candle）─

def detect_big_bullish(ohlc: pd.DataFrame, window: int = 20,
                       multiplier: float = 2.0,
                       shadow_ratio: float = 0.20,
                       trend: int = 5) -> pd.Series:
    cg = ohlc['Close'] > ohlc['Open']
    body = ohlc['Close'] - ohlc['Open']
    span = ohlc['High'] - ohlc['Low']
    big = body > _avg_body(ohlc, window) * multiplier
    sup = (ohlc['High'] - ohlc['Close']) <= span * shadow_ratio
    slo = (ohlc['Open'] - ohlc['Low']) <= span * shadow_ratio
    return cg & big & sup & slo & _trend_down(ohlc, trend)


# ── 8. 流星线（射击之星 / Shooting Star）— 出现即算 ──

def detect_shooting_star(ohlc: pd.DataFrame, **kwargs) -> pd.Series:
    body = (ohlc['Close'] - ohlc['Open']).abs()
    upper = ohlc['High'] - ohlc[['Open', 'Close']].max(axis=1)
    lower = ohlc[['Open', 'Close']].min(axis=1) - ohlc['Low']
    return (upper >= body * 3) & (lower <= body)


# ── 9. 锤头线（Hammer）— 后续N根不破低点确认 ──

def detect_hammer(ohlc: pd.DataFrame, trend: int = 5,
                  confirm_bars: int = 2) -> pd.Series:
    span = ohlc['High'] - ohlc['Low']
    body = (ohlc['Close'] - ohlc['Open']).abs()
    long_shadow = span > 4 * body
    close_top = (ohlc['Close'] - ohlc['Low']) / (span + 0.001) >= 0.75
    open_top = (ohlc['Open'] - ohlc['Low']) / (span + 0.001) >= 0.75
    prev_lows_above = (
        (ohlc['Low'].shift(1) > ohlc['Low']) &
        (ohlc['Low'].shift(2) > ohlc['Low'])
    )
    geo = long_shadow & close_top & open_top & _trend_down(ohlc, trend) & prev_lows_above
    confirmed = pd.Series(True, index=ohlc.index)
    for i in range(1, confirm_bars + 1):
        confirmed = confirmed & (ohlc['Low'].shift(-i) >= ohlc['Low'])
    return geo & confirmed


# ── 10. 上吊线（Hanging Man）— 下一根收低确认 ──

def detect_hanging_man(ohlc: pd.DataFrame, trend: int = 5,
                       confirm_bars: int = 1) -> pd.Series:
    span = ohlc['High'] - ohlc['Low']
    body = (ohlc['Close'] - ohlc['Open']).abs()
    long_shadow = span > 4 * body
    close_low = (ohlc['Close'] - ohlc['Low']) / (span + 0.001) >= 0.75
    open_low = (ohlc['Open'] - ohlc['Low']) / (span + 0.001) >= 0.75
    prev_highs_below = (
        (ohlc['High'].shift(1) < ohlc['Open']) &
        (ohlc['High'].shift(2) < ohlc['Open'])
    )
    geo = long_shadow & close_low & open_low & prev_highs_below & _trend_up(ohlc, trend)
    confirm = ohlc['Close'].shift(-1) <= ohlc[['Open', 'Close']].min(axis=1)
    return geo & confirm


# ── 11. 黄昏之星（Evening Star）— 三根完整 ──

def detect_evening_star(ohlc: pd.DataFrame, trend: int = 5) -> pd.Series:
    k1_green = ohlc['Close'].shift(2) > ohlc['Open'].shift(2)
    k2_body = (ohlc['Close'].shift(1) - ohlc['Open'].shift(1)).abs()
    k2_small = k2_body <= _avg_body(ohlc, 20) * 0.3
    k2_gap_up = (ohlc[['Open','Close']].shift(1).min(axis=1) > ohlc['Close'].shift(2))
    k3_red = ohlc['Open'] > ohlc['Close']
    k3_deep = ohlc['Close'] < (ohlc['Close'].shift(2) -
                                ((ohlc['Close'].shift(2) - ohlc['Open'].shift(2)) / 2))
    return k1_green & k2_small & k2_gap_up & k3_red & k3_deep


# ── 12. 早晨之星（Morning Star）— 三根完整 ──

def detect_morning_star(ohlc: pd.DataFrame, trend: int = 5) -> pd.Series:
    k1_red = ohlc['Open'].shift(2) > ohlc['Close'].shift(2)
    k2_body = (ohlc['Close'].shift(1) - ohlc['Open'].shift(1)).abs()
    k2_small = k2_body <= _avg_body(ohlc, 20) * 0.3
    k2_gap_down = (ohlc[['Open','Close']].shift(1).max(axis=1) < ohlc['Close'].shift(2))
    k3_green = ohlc['Close'] > ohlc['Open']
    k3_deep = ohlc['Close'] > (ohlc['Close'].shift(2) +
                                ((ohlc['Open'].shift(2) - ohlc['Close'].shift(2)) / 2))
    return k1_red & k2_small & k2_gap_down & k3_green & k3_deep


# ═══════════════════════════════════════════════
# v4 新增形态 — 看涨反转（续）
# ═══════════════════════════════════════════════

# ── 13. 早晨十字星（Morning Doji Star）
#     与早晨之星相同，但中间为十字星
# ──

def detect_morning_doji_star(ohlc, trend=5):
    k1_red = ohlc['Open'].shift(2) > ohlc['Close'].shift(2)
    k2_doji = (ohlc['Close'].shift(1) - ohlc['Open'].shift(1)).abs() <= _avg_span(ohlc, 20) * 0.05
    k2_gap_down = (ohlc[['Open','Close']].shift(1).max(axis=1) < ohlc['Close'].shift(2))
    k3_green = ohlc['Close'] > ohlc['Open']
    k3_deep = ohlc['Close'] > (ohlc['Close'].shift(2) + ((ohlc['Open'].shift(2) - ohlc['Close'].shift(2)) / 2))
    return k1_red & k2_doji & k2_gap_down & k3_green & k3_deep


# ── 14. 黄昏十字星（Evening Doji Star）
#     与黄昏之星相同，但中间为十字星
# ──

def detect_evening_doji_star(ohlc, trend=5):
    k1_green = ohlc['Close'].shift(2) > ohlc['Open'].shift(2)
    k2_doji = (ohlc['Close'].shift(1) - ohlc['Open'].shift(1)).abs() <= _avg_span(ohlc, 20) * 0.05
    k2_gap_up = (ohlc[['Open','Close']].shift(1).min(axis=1) > ohlc['Close'].shift(2))
    k3_red = ohlc['Open'] > ohlc['Close']
    k3_deep = ohlc['Close'] < (ohlc['Close'].shift(2) - ((ohlc['Close'].shift(2) - ohlc['Open'].shift(2)) / 2))
    return k1_green & k2_doji & k2_gap_up & k3_red & k3_deep


# ── 15. 好友反攻（Bullish Counterattack Lines）
#     大阴+大阳，阳开盘≈阴收盘（刺透但未到50%）
# ──

def detect_bullish_counterattack(ohlc, trend=5, threshold=0.02):
    k1_black = ohlc['Open'].shift(1) > ohlc['Close'].shift(1)
    k1_long = (ohlc['Open'].shift(1) - ohlc['Close'].shift(1)) > _avg_body(ohlc, 20)
    k2_green = ohlc['Close'] > ohlc['Open']
    open_close = (ohlc['Open'] - ohlc['Close'].shift(1)).abs() <= _avg_span(ohlc, 20) * threshold
    close_close = (ohlc['Close'] - ohlc['Close'].shift(1)).abs() <= _avg_span(ohlc, 20) * threshold
    return k1_black & k1_long & k2_green & open_close & close_close & _trend_down(ohlc, trend)


# ── 16. 淡友反攻（Bearish Counterattack Lines）
#     大阳+大阴，阴开盘≈阳收盘（乌云但未到50%）
# ──

def detect_bearish_counterattack(ohlc, trend=5, threshold=0.02):
    k1_green = ohlc['Close'].shift(1) > ohlc['Open'].shift(1)
    k1_long = (ohlc['Close'].shift(1) - ohlc['Open'].shift(1)) > _avg_body(ohlc, 20)
    k2_black = ohlc['Open'] > ohlc['Close']
    open_close = (ohlc['Open'] - ohlc['Close'].shift(1)).abs() <= _avg_span(ohlc, 20) * threshold
    close_close = (ohlc['Close'] - ohlc['Close'].shift(1)).abs() <= _avg_span(ohlc, 20) * threshold
    return k1_green & k1_long & k2_black & open_close & close_close & _trend_up(ohlc, trend)


# ── 17. 乌云盖顶（Dark Cloud Cover）
#     大阳+大阴，阴开盘>前高，收盘切入阳实体>50%（刺透的看跌对称）
# ──

def detect_dark_cloud_cover(ohlc, trend=5):
    k1_green = ohlc['Close'].shift(1) > ohlc['Open'].shift(1)
    k1_long = (ohlc['Close'].shift(1) - ohlc['Open'].shift(1)) > _avg_body(ohlc, 20)
    k2_black = ohlc['Open'] > ohlc['Close']
    open_above_high = ohlc['Open'] > ohlc['High'].shift(1)
    mid = ohlc['Open'].shift(1) + ((ohlc['Close'].shift(1) - ohlc['Open'].shift(1)) / 2)
    pierce_down = ohlc['Close'] < mid
    not_full = ohlc['Close'] > ohlc['Open'].shift(1)
    return k1_green & k1_long & k2_black & open_above_high & pierce_down & not_full & _trend_up(ohlc, trend)


# ── 18. 倾盆大雨（Heavy Rain）
#     旭日东升的看跌对称：大阳+大阴，阴收盘<阳开盘（比乌云盖顶更狠）
# ──

def detect_heavy_rain(ohlc, trend=5):
    k1_green = ohlc['Close'].shift(1) > ohlc['Open'].shift(1)
    k1_long = (ohlc['Close'].shift(1) - ohlc['Open'].shift(1)) > _avg_body(ohlc, 20)
    k2_black = ohlc['Open'] > ohlc['Close']
    open_below_close = ohlc['Open'] < ohlc['Close'].shift(1)
    close_below_open = ohlc['Close'] < ohlc['Open'].shift(1)
    return k1_green & k1_long & k2_black & open_below_close & close_below_open & _trend_up(ohlc, trend)


# ── 19. 平底（Tweezer Bottom）
#     两根最低价相同/相近，第二根为阳线，下跌趋势中
# ──

def detect_tweezer_bottom(ohlc, trend=5, threshold=0.005):
    same_low = (ohlc['Low'] - ohlc['Low'].shift(1)).abs() <= _avg_span(ohlc, 20) * threshold
    second_green = ohlc['Close'] > ohlc['Open']
    return same_low & second_green & _trend_down(ohlc, trend)


# ── 20. 平顶（Tweezer Top）
#     两根最高价相同/相近，第二根为阴线，上涨趋势中
# ──

def detect_tweezer_top(ohlc, trend=5, threshold=0.005):
    same_high = (ohlc['High'] - ohlc['High'].shift(1)).abs() <= _avg_span(ohlc, 20) * threshold
    second_black = ohlc['Open'] > ohlc['Close']
    return same_high & second_black & _trend_up(ohlc, trend)


# ═══════════════════════════════════════════════
# v4 新增 — 三K线形态
# ═══════════════════════════════════════════════

# ── 21. 红三兵（Three Red Soldiers）
#     三连阳，逐日创高，开盘在前实体内，实体相近
# ──

def detect_red_three_soldiers(ohlc, trend=5, window=20):
    c1, c2, c3 = ohlc.shift(2), ohlc.shift(1), ohlc
    # 三根阳线
    all_green = (c1['Close'] > c1['Open']) & (c2['Close'] > c2['Open']) & (c3['Close'] > c3['Open'])
    # 逐日收盘创新高
    higher_close = (c2['Close'] > c1['Close']) & (c3['Close'] > c2['Close'])
    # 开盘在前实体内部
    open_in_body = (c2['Open'] <= c1['Close']) & (c2['Open'] >= c1['Open']) &                    (c3['Open'] <= c2['Close']) & (c3['Open'] >= c2['Open'])
    # 实体相近（最大/最小 < 1.5）
    b1 = c1['Close'] - c1['Open']
    b2 = c2['Close'] - c2['Open']
    b3 = c3['Close'] - c3['Open']
    bodies = [b1, b2, b3]
    body_ratio = pd.concat(bodies, axis=1).max(axis=1) / (pd.concat(bodies, axis=1).min(axis=1) + 0.001)
    similar = body_ratio <= 1.5
    # 短下影线
    short_lower = (_lower_shadow(c1) <= _body(c1)) & (_lower_shadow(c2) <= _body(c2)) & (_lower_shadow(c3) <= _body(c3))
    return all_green & higher_close & open_in_body & similar & short_lower & _trend_down(ohlc, trend)


# ── 22. 三个白色武士（Three Advancing White Soldiers）
#     红三兵变种：开盘在前阳实体中上部位+实体逐步放大+无上影
# ──

def detect_three_white_warriors(ohlc, trend=5):
    c1, c2, c3 = ohlc.shift(2), ohlc.shift(1), ohlc
    all_green = (c1['Close'] > c1['Open']) & (c2['Close'] > c2['Open']) & (c3['Close'] > c3['Open'])
    higher_close = (c2['Close'] > c1['Close']) & (c3['Close'] > c2['Close'])
    # 开盘在前阳实体中上部（> 前阳实体中点）
    mid1 = (c1['Close'] + c1['Open']) / 2
    mid2 = (c2['Close'] + c2['Open']) / 2
    open_upper = (c2['Open'] >= mid1) & (c3['Open'] >= mid2)
    # 实体逐步放大
    b1 = c1['Close'] - c1['Open']
    b2 = c2['Close'] - c2['Open']
    b3 = c3['Close'] - c3['Open']
    growing = (b2 >= b1 * 0.9) & (b3 >= b2 * 0.9)
    # 几乎无上影线
    no_upper = (_upper_shadow(c1) <= _body(c1) * 0.25) &                (_upper_shadow(c2) <= _body(c2) * 0.25) &                (_upper_shadow(c3) <= _body(c3) * 0.25)
    return all_green & higher_close & open_upper & growing & no_upper & _trend_down(ohlc, trend)


# ── 23. 黑三兵（Three Black Crows basic）
#     三连阴，逐日走低，开盘在前实体内，实体相近
# ──

def detect_black_three_soldiers(ohlc, trend=5):
    c1, c2, c3 = ohlc.shift(2), ohlc.shift(1), ohlc
    all_black = (c1['Open'] > c1['Close']) & (c2['Open'] > c2['Close']) & (c3['Open'] > c3['Close'])
    lower_close = (c2['Close'] < c1['Close']) & (c3['Close'] < c2['Close'])
    open_in_body = (c2['Open'] <= c1['Open']) & (c2['Open'] >= c1['Close']) &                    (c3['Open'] <= c2['Open']) & (c3['Open'] >= c2['Close'])
    b1 = c1['Open'] - c1['Close']
    b2 = c2['Open'] - c2['Close']
    b3 = c3['Open'] - c3['Close']
    bodies = [b1, b2, b3]
    body_ratio = pd.concat(bodies, axis=1).max(axis=1) / (pd.concat(bodies, axis=1).min(axis=1) + 0.001)
    similar = body_ratio <= 1.5
    short_upper = (_upper_shadow(c1) <= _body(c1)) & (_upper_shadow(c2) <= _body(c2)) & (_upper_shadow(c3) <= _body(c3))
    return all_black & lower_close & open_in_body & similar & short_upper & _trend_up(ohlc, trend)


# ── 24. 三只乌鸦（Three Black Crows）
#     黑三兵变种：开盘在前阴实体中下部位+实体饱满+无下影线
# ──

def detect_three_black_crows(ohlc, trend=5):
    c1, c2, c3 = ohlc.shift(2), ohlc.shift(1), ohlc
    all_black = (c1['Open'] > c1['Close']) & (c2['Open'] > c2['Close']) & (c3['Open'] > c3['Close'])
    lower_close = (c2['Close'] < c1['Close']) & (c3['Close'] < c2['Close'])
    # 开盘在前阴实体中下部（< 前阴实体中点）
    mid1 = (c1['Open'] + c1['Close']) / 2
    mid2 = (c2['Open'] + c2['Close']) / 2
    open_lower = (c2['Open'] <= mid1) & (c3['Open'] <= mid2)
    # 实体饱满（长阴）
    b1 = c1['Open'] - c1['Close']
    b2 = c2['Open'] - c2['Close']
    b3 = c3['Open'] - c3['Close']
    long_bodies = (b1 > _avg_body(ohlc, 20)) & (b2 > _avg_body(ohlc, 20)) & (b3 > _avg_body(ohlc, 20))
    # 几乎无下影线（空头无抵抗）
    no_lower = (_lower_shadow(c1) <= _body(c1) * 0.25) &                (_lower_shadow(c2) <= _body(c2) * 0.25) &                (_lower_shadow(c3) <= _body(c3) * 0.25)
    return all_black & lower_close & open_lower & long_bodies & no_lower & _trend_up(ohlc, trend)


# ── 25. 两红夹一黑（Bullish Sandwich / Two Reds with One Black）
#     阳-阴-阳，中阴不低于首阳低点，第三阳收>首阳收
# ──

def detect_bullish_sandwich(ohlc, trend=5):
    k1, k2, k3 = ohlc.shift(2), ohlc.shift(1), ohlc
    k1_yang = k1['Close'] > k1['Open']
    k2_yin = k2['Open'] > k2['Close']
    k3_yang = k3['Close'] > k3['Open']
    # 中阴在两阳实体内（至少不跌破首阳低点）
    k2_in_range = (k2['Close'] >= k1['Low']) & (k2['Open'] <= k1['High'])
    # 第三阳收盘>首阳收盘
    k3_higher = k3['Close'] > k1['Close']
    return k1_yang & k2_yin & k3_yang & k2_in_range & k3_higher & _trend_up(ohlc, trend)


# ── 26. 两黑夹一红（Bearish Sandwich / Two Blacks with One Red）
#     阴-阳-阴，中阳不高于首阴高点，第三阴收<首阴收
# ──

def detect_bearish_sandwich(ohlc, trend=5):
    k1, k2, k3 = ohlc.shift(2), ohlc.shift(1), ohlc
    k1_yin = k1['Open'] > k1['Close']
    k2_yang = k2['Close'] > k2['Open']
    k3_yin = k3['Open'] > k3['Close']
    k2_in_range = (k2['Close'] <= k1['High']) & (k2['Open'] >= k1['Low'])
    k3_lower = k3['Close'] < k1['Close']
    return k1_yin & k2_yang & k3_yin & k2_in_range & k3_lower & _trend_down(ohlc, trend)


# ── 27. 升势停顿（Rising Stall）
#     上涨中：大阳+小实体(阴/阳)+大阳，第三根创首阳新高
# ──

def detect_rising_stall(ohlc, trend=5):
    k1, k2, k3 = ohlc.shift(2), ohlc.shift(1), ohlc
    k1_big_yang = (k1['Close'] > k1['Open']) & ((k1['Close'] - k1['Open']) > _avg_body(ohlc, 20) * 1.5)
    k2_small = _is_small_body(k2, 20, 0.4)
    k3_yang = k3['Close'] > k3['Open']
    k3_new_high = k3['Close'] > k1['Close']
    return k1_big_yang & k2_small & k3_yang & k3_new_high & _trend_up(ohlc, trend)


print('  -> 3-K-line patterns (red/black soldiers, warriors, crows, sandwiches, rising stall) done')


# ═══════════════════════════════════════════════
# v4 新增 — 多K线形态（自适应N字型）
# ═══════════════════════════════════════════════

# ── 28. 上升三部曲（Rising Three Methods）— 自适应N字型
#     大阳→2~5根小阴（在首阳实体内）→大阳突破前高
# ──

def detect_rising_three_methods(ohlc, min_mid=2, max_mid=5, **kwargs):
    result = pd.Series(False, index=ohlc.index)
    for i in range(max_mid + 2, len(ohlc)):  # 至少需要 1 + 2 + 1 = 4根
        k1 = ohlc.iloc[i - max_mid - 2]  # 第1根大阳
        # 第1根：大阳线
        if not (k1['Close'] > k1['Open']):
            continue
        k1_body = k1['Close'] - k1['Open']
        avg_b = float(_avg_body(ohlc.iloc[:i], 20).iloc[-1]) if i > 5 else 0.001
        if k1_body <= avg_b * 1.2:
            continue
        
        # 尝试不同的中间K线数量
        found = False
        for m in range(min_mid, max_mid + 1):
            if i - m - 1 < 0:
                continue
            k_start = i - m - 1
            k_end = i - 1  # 最后1根是突破大阳
            
            k_last = ohlc.iloc[i]
            # 最后1根：大阳突破
            if not (k_last['Close'] > k_last['Open']):
                continue
            if not (k_last['Close'] > k1['Close']):  # 突破第1根高点
                continue
            if not (k_last['Close'] - k_last['Open'] > avg_b * 1.2):
                continue
            
            # 中间 m 根：在首阳实体内的小实体
            mid_ok = True
            for j in range(k_start, k_end + 1):
                mid_k = ohlc.iloc[j]
                # 小实体（阴线优先，但也接受阳）
                mid_body = abs(mid_k['Close'] - mid_k['Open'])
                if mid_body > k1_body * 0.6:
                    mid_ok = False
                    break
                # 在中阳实体内
                if mid_k['Close'] > k1['Close'] or mid_k['Open'] > k1['Close']:
                    mid_ok = False
                    break
                if mid_k['Close'] < k1['Open'] or mid_k['Open'] < k1['Open']:
                    mid_ok = False
                    break
            
            if mid_ok:
                found = True
                break
        
        result.iloc[i] = found
    return result


# ── 29. 下跌三部曲（Falling Three Methods）— 自适应N字型
#     大阴→2~5根小阳（在首阴实体内）→大阴跌破前低
# ──

def detect_falling_three_methods(ohlc, min_mid=2, max_mid=5, **kwargs):
    result = pd.Series(False, index=ohlc.index)
    for i in range(max_mid + 2, len(ohlc)):
        k1 = ohlc.iloc[i - max_mid - 2]
        if not (k1['Open'] > k1['Close']):
            continue
        k1_body = k1['Open'] - k1['Close']
        avg_b = float(_avg_body(ohlc.iloc[:i], 20).iloc[-1]) if i > 5 else 0.001
        if k1_body <= avg_b * 1.2:
            continue
        
        found = False
        for m in range(min_mid, max_mid + 1):
            if i - m - 1 < 0:
                continue
            k_start = i - m - 1
            k_end = i - 1
            
            k_last = ohlc.iloc[i]
            if not (k_last['Open'] > k_last['Close']):
                continue
            if not (k_last['Close'] < k1['Close']):
                continue
            if not (k_last['Open'] - k_last['Close'] > avg_b * 1.2):
                continue
            
            mid_ok = True
            for j in range(k_start, k_end + 1):
                mid_k = ohlc.iloc[j]
                mid_body = abs(mid_k['Close'] - mid_k['Open'])
                if mid_body > k1_body * 0.6:
                    mid_ok = False
                    break
                if mid_k['Close'] < k1['Close'] or mid_k['Open'] < k1['Close']:
                    mid_ok = False
                    break
                if mid_k['Close'] > k1['Open'] or mid_k['Open'] > k1['Open']:
                    mid_ok = False
                    break
            
            if mid_ok:
                found = True
                break
        
        result.iloc[i] = found
    return result


# ═══════════════════════════════════════════════
# v4 新增 — 尖兵形态（含后续确认）
# ═══════════════════════════════════════════════

# ── 30. 多方尖兵（Bullish Vanguard）
#     下跌趋势中长下影阳线 + 后续N根不跌破下影线低点
# ──

def detect_bullish_vanguard(ohlc, trend=5, confirm_bars=2):
    # 长下影阳线
    is_yang = ohlc['Close'] > ohlc['Open']
    lower = _lower_shadow(ohlc)
    body = _body(ohlc)
    long_shadow = lower > body * 2
    short_upper = _upper_shadow(ohlc) <= body
    
    geo = is_yang & long_shadow & short_upper & _trend_down(ohlc, trend)
    
    # 后续确认：后面 confirm_bars 根的低点 >= 下影线最低点
    confirmed = pd.Series(True, index=ohlc.index)
    for i in range(1, confirm_bars + 1):
        confirmed = confirmed & (ohlc['Low'].shift(-i) >= ohlc['Low'])
    
    return geo & confirmed


# ── 31. 空方尖兵（Bearish Vanguard）
#     上涨趋势中长上影阴线 + 后续N根不突破上影线高点
# ──

def detect_bearish_vanguard(ohlc, trend=5, confirm_bars=2):
    is_yin = ohlc['Open'] > ohlc['Close']
    upper = _upper_shadow(ohlc)
    body = _body(ohlc)
    long_shadow = upper > body * 2
    short_lower = _lower_shadow(ohlc) <= body
    
    geo = is_yin & long_shadow & short_lower & _trend_up(ohlc, trend)
    
    # 后续确认：后面 confirm_bars 根的高点 <= 上影线最高点
    confirmed = pd.Series(True, index=ohlc.index)
    for i in range(1, confirm_bars + 1):
        confirmed = confirmed & (ohlc['High'].shift(-i) <= ohlc['High'])
    
    return geo & confirmed


# ═══════════════════════════════════════════════
# v4 新增 — 单K线连续形态
# ═══════════════════════════════════════════════

# ── 32. 徐缓上升（Slowly Rising）
#     前几根小阳后拉大阳（5根内：小阳逐步放大→大阳确认）
# ──

def detect_slowly_rising(ohlc: pd.DataFrame, trend: int = 5) -> pd.Series:

    """

    检测「徐缓上升」K线形态。

    

    参数:

        ohlc: 包含列 'Open','High','Low','Close' 的DataFrame

        trend: 保留参数，暂未使用

    返回:

        pd.Series，长度与 ohlc 相同，True 表示该位置窗口满足徐缓上升条件

    """

    # 确保列存在

    required_cols = {'Open', 'High', 'Low', 'Close'}

    if not required_cols.issubset(ohlc.columns):

        raise ValueError(f"ohlc 必须包含列: {required_cols}")

    

    n = len(ohlc)

    open_ = ohlc['Open'].values

    high = ohlc['High'].values

    low = ohlc['Low'].values

    close = ohlc['Close'].values

    

    # 计算基础量

    entity = np.abs(close - open_)               # 实体

    upper_shadow = high - np.maximum(open_, close) # 上影线

    amplitude = high - low                        # 振幅

    is_bull = close > open_                       # 阳线

    

    # 滚动20日平均振幅（用于后续阈值）

    roll_amp20 = pd.Series(amplitude).rolling(window=20, min_periods=1).mean().values

    

    # 窗口大小自适应：默认15，数据不足则取全长

    win = 15 if n >= 15 else n

    

    result = pd.Series(False, index=ohlc.index)

    

    # 逐窗口判断

    for i in range(win - 1, n):

        start = i - win + 1

        end = i + 1  # slice 不含 end

        

        # 切片数据

        ent_win = entity[start:end]

        bull_win = is_bull[start:end]

        close_win = close[start:end]

        upper_win = upper_shadow[start:end]

        open_win = open_[start:end]

        

        # 条件1：阳线比例 >= 70%

        bull_ratio = np.mean(bull_win)

        if bull_ratio < 0.7:

            continue

        

        # 条件2：实体变异系数 CV < 0.5

        mean_ent = np.mean(ent_win)

        if mean_ent == 0:

            continue

        cv = np.std(ent_win) / mean_ent

        if cv >= 0.5:

            continue

        

        # 条件3：平均实体 < 最近20日平均振幅的40%

        avg_amp = roll_amp20[i]

        if mean_ent >= avg_amp * 0.4:

            continue

        

        # 条件4：线性回归斜率 0 < slope < avg_amp * 0.03

        x = np.arange(win)

        # 使用 polyfit 获取斜率

        slope = np.polyfit(x, close_win, 1)[0]

        if not (0 < slope < avg_amp * 0.03):

            continue

        

        # 条件5：不能有长上影线（上影线 > 实体 * 2）

        # 实体可能为0，此时上影线>0即满足条件，会被判为长上影

        if np.any(upper_win > ent_win * 2):

            continue

        

        # 条件6：不能有超过2根明显反向阴线

        # 阴线定义：close < open

        bearish = close_win < open_win

        # 明显反向：实体 > 平均实体 * 1.2

        big_bearish = bearish & (ent_win > mean_ent * 1.2)

        if np.sum(big_bearish) > 2:

            continue

        

        # 所有条件通过

        result.iloc[i] = True

    

    return result





def detect_slowly_falling(ohlc: pd.DataFrame, trend: int = 5) -> pd.Series:

    """

    检测「徐缓下降」K线形态。

    

    参数:

        ohlc: 包含列 'Open','High','Low','Close' 的DataFrame

        trend: 保留参数，暂未使用

    返回:

        pd.Series，长度与 ohlc 相同，True 表示该位置窗口满足徐缓下降条件

    """

    # 确保列存在

    required_cols = {'Open', 'High', 'Low', 'Close'}

    if not required_cols.issubset(ohlc.columns):

        raise ValueError(f"ohlc 必须包含列: {required_cols}")

    

    n = len(ohlc)

    open_ = ohlc['Open'].values

    high = ohlc['High'].values

    low = ohlc['Low'].values

    close = ohlc['Close'].values

    

    # 基础计算

    entity = np.abs(close - open_)               # 实体

    lower_shadow = np.minimum(open_, close) - low # 下影线

    amplitude = high - low                        # 振幅

    is_bear = close < open_                       # 阴线

    

    # 滚动20日平均振幅

    roll_amp20 = pd.Series(amplitude).rolling(window=20, min_periods=1).mean().values

    

    # 窗口大小自适应：默认15，数据不足则取全长

    win = 15 if n >= 15 else n

    

    result = pd.Series(False, index=ohlc.index)

    

    # 逐窗口检测

    for i in range(win - 1, n):

        start = i - win + 1

        end = i + 1

        

        ent_win = entity[start:end]

        bear_win = is_bear[start:end]

        close_win = close[start:end]

        lower_win = lower_shadow[start:end]

        open_win = open_[start:end]

        

        # 条件1：阴线比例 >= 70%

        bear_ratio = np.mean(bear_win)

        if bear_ratio < 0.7:

            continue

        

        # 条件2：实体变异系数 CV < 0.5

        mean_ent = np.mean(ent_win)

        if mean_ent == 0:

            continue

        cv = np.std(ent_win) / mean_ent

        if cv >= 0.5:

            continue

        

        # 条件3：平均实体 < 最近20日平均振幅的40%

        avg_amp = roll_amp20[i]

        if mean_ent >= avg_amp * 0.4:

            continue

        

        # 条件4：线性回归斜率 -avg_amp*0.03 < slope < 0

        x = np.arange(win)

        slope = np.polyfit(x, close_win, 1)[0]

        if not (-avg_amp * 0.03 < slope < 0):

            continue

        

        # 条件5：不能有长下影线（下影线 > 实体*2）

        if np.any(lower_win > ent_win * 2):

            continue

        

        # 条件6：不能有超过2根明显反向阳线

        # 阳线定义：close > open_

        bullish = close_win > open_win

        big_bullish = bullish & (ent_win > mean_ent * 1.2)

        if np.sum(big_bullish) > 2:

            continue

        

        result.iloc[i] = True

    

    return result



def detect_falling_cover(ohlc, trend=5):
    k1, k2, k3 = ohlc.shift(2), ohlc.shift(1), ohlc
    k1_yang = k1['Close'] > k1['Open']
    k2_yin = k2['Open'] > k2['Close']
    k3_yin = k3['Open'] > k3['Close']
    # K2低开，收盘在K1实体内
    k2_low_open = k2['Open'] < k1['Close']
    k2_close_in = k2['Close'] < k1['Close']
    # K3收盘 < K1开盘（完全覆盖）
    k3_cover = k3['Close'] < k1['Open']
    return k1_yang & k2_yin & k3_yin & k2_low_open & k2_close_in & k3_cover & _trend_up(ohlc, trend)


print('  -> Multi-K, vanguard, slowly rising/falling, falling cover done')


# ═══════════════════════════════════════════════
# v4 新增 — 单K线中性形态
# ═══════════════════════════════════════════════

# ── 35. 纺锤线（Spinning Top）
#     小实体+较长上下影线（比十字星实体稍大）
# ──

def detect_spinning_top(ohlc, window=20, body_threshold=0.3,
                        shadow_min=1.0, **kwargs):
    body = _body(ohlc)
    span = ohlc['High'] - ohlc['Low']
    upper = _upper_shadow(ohlc)
    lower = _lower_shadow(ohlc)
    small_body = body <= _avg_body(ohlc, window) * body_threshold
    # 上下影线都比实体长
    long_shadows = (upper >= body * shadow_min) & (lower >= body * shadow_min)
    return small_body & long_shadows


# ── 36. 长十字星（Long-legged Doji / 黄包车夫）
#     十字星 + 长上下影线（振幅 > 平均的2倍）
# ──

def detect_long_doji(ohlc, window=20, doji_factor=0.05,
                     span_multiplier=1.5, **kwargs):
    body = _body(ohlc)
    span = ohlc['High'] - ohlc['Low']
    is_doji = body <= _avg_span(ohlc, window) * doji_factor
    long_span = span > _avg_span(ohlc, window) * span_multiplier
    return is_doji & long_span


# ── 37. 蜻蜓十字星（Dragonfly Doji）
#     十字星+无上影+长下影
# ──

def detect_dragonfly_doji(ohlc, window=20, doji_factor=0.05, **kwargs):
    body = _body(ohlc)
    upper = _upper_shadow(ohlc)
    lower = _lower_shadow(ohlc)
    is_doji = body <= _avg_span(ohlc, window) * doji_factor
    no_upper = upper <= body * 0.1
    long_lower = lower > body * 3
    return is_doji & no_upper & long_lower


# ── 38. 墓碑十字星（Gravestone Doji）
#     十字星+长上影+无下影
# ──

def detect_gravestone_doji(ohlc, window=20, doji_factor=0.05, **kwargs):
    body = _body(ohlc)
    upper = _upper_shadow(ohlc)
    lower = _lower_shadow(ohlc)
    is_doji = body <= _avg_span(ohlc, window) * doji_factor
    no_lower = lower <= body * 0.1
    long_upper = upper > body * 3
    return is_doji & long_upper & no_lower


# ── 39. T字线（T-shaped Line / 锤头放宽版）
#     开收=高价（或极近），长下影线，无上影
# ──

def detect_t_shape(ohlc, window=20, threshold=0.02, **kwargs):
    span = ohlc['High'] - ohlc['Low']
    body = _body(ohlc)
    upper = _upper_shadow(ohlc)
    lower = _lower_shadow(ohlc)
    # 开收在最高价附近（小实体在高位）
    close_at_high = (ohlc['High'] - ohlc['Close']) <= span * threshold
    open_at_high = (ohlc['High'] - ohlc['Open']) <= span * threshold
    long_lower = lower > body * 3
    no_upper = upper <= span * threshold
    return close_at_high & open_at_high & long_lower & no_upper


# ── 40. 倒T字线（Inverted T-shaped Line / 流星放宽版）
#     开收=低价（或极近），长上影线，无下影
# ──

def detect_inverted_t_shape(ohlc, window=20, threshold=0.02, **kwargs):
    span = ohlc['High'] - ohlc['Low']
    body = _body(ohlc)
    upper = _upper_shadow(ohlc)
    lower = _lower_shadow(ohlc)
    close_at_low = (ohlc['Close'] - ohlc['Low']) <= span * threshold
    open_at_low = (ohlc['Open'] - ohlc['Low']) <= span * threshold
    long_upper = upper > body * 3
    no_lower = lower <= span * threshold
    return close_at_low & open_at_low & long_upper & no_lower


# ── 41. 高开出逃形（High-open Escape）
#     高位高开低走大阴线，开盘=最高价
# ──

def detect_high_open_escape(ohlc, window=20, trend=5):
    big_black = (ohlc['Open'] > ohlc['Close'])
    big_body = (ohlc['Open'] - ohlc['Close']) > _avg_body(ohlc, window) * 1.5
    open_is_high = ohlc['Open'] >= ohlc['High'] * 0.998
    return big_black & big_body & open_is_high & _trend_up(ohlc, trend)


# ── 42. 下探上涨形（Low-probe Rise）
#     低位低开高走大阳线，收盘=最高价
# ──

def detect_low_probe_rise(ohlc, window=20, trend=5):
    big_green = (ohlc['Close'] > ohlc['Open'])
    big_body = (ohlc['Close'] - ohlc['Open']) > _avg_body(ohlc, window) * 1.5
    close_is_high = ohlc['Close'] >= ohlc['High'] * 0.998
    return big_green & big_body & close_is_high & _trend_down(ohlc, trend)


# ── 43. 上涨二颗星（Two Stars Before Rise）
#     大阳+向上跳空小实体+第三根大阳（或十字星确认）
# ──

def detect_two_stars_before_rise(ohlc, trend=5):
    k1, k2, k3 = ohlc.shift(2), ohlc.shift(1), ohlc
    k1_yang = k1['Close'] > k1['Open']
    # K1大阳
    k1_big = (k1['Close'] - k1['Open']) > _avg_body(ohlc, 20) * 1.5
    # K2跳空高开小实体
    k2_gap = (k2['Open'] > k1['Close']) & (k2['Close'] > k1['Close'])
    k2_small = _is_small_body(k2, 20, 0.4)
    # K3阳线并高于K1收盘
    k3_yang = k3['Close'] > k3['Open']
    k3_higher = k3['Close'] > k1['Close']
    return k1_yang & k1_big & k2_gap & k2_small & k3_yang & k3_higher & _trend_up(ohlc, trend)


# ── 44. 低位并排阳线（Low Parallel Yang Lines）
#     下跌末端两根阳线，低点相近，收盘相近
# ──

def detect_low_parallel_yang(ohlc, trend=5, threshold=0.01):
    k1, k2 = ohlc.shift(1), ohlc
    both_yang = (k1['Close'] > k1['Open']) & (k2['Close'] > k2['Open'])
    low_close = (k1['Low'] - k2['Low']).abs() <= _avg_span(ohlc, 20) * threshold
    close_close = (k1['Close'] - k2['Close']).abs() <= _avg_span(ohlc, 20) * threshold
    return both_yang & low_close & close_close & _trend_down(ohlc, trend)


print('  -> Single-candle neutral patterns done')


# ═══════════════════════════════════════════════
# v5 新增 — A类离散形态（12种）
# ═══════════════════════════════════════════════

# ── 45. 升势受阻（Rising Stall / Stalled Pattern, #14）
#     上涨中：大阳 + 小实体（十字/小阴/小阳）+ 第三根阳线未创新高
#     与升势停顿区别：升势停顿第三根创新高，升势受阻第三根没创新高
# ──

def detect_rising_stalled(ohlc, trend=5, **kwargs):
    k1, k2, k3 = ohlc.shift(2), ohlc.shift(1), ohlc
    k1_big_yang = (k1['Close'] > k1['Open']) & ((k1['Close'] - k1['Open']) > _avg_body(ohlc, 20) * 1.5)
    k2_small = _is_small_body(k2, 20, 0.4)
    k3_yang = k3['Close'] > k3['Open']
    # 关键区别：第三根未创新高（即收盘 <= 第一根收盘）
    k3_no_new_high = k3['Close'] <= k1['Close']
    return k1_big_yang & k2_small & k3_yang & k3_no_new_high & _trend_up(ohlc, trend)


# ── 46. 高位并排阳线（High Parallel Yang Lines, #18）
#     上涨中两根高开高走阳线，高点相近
# ──

def detect_high_parallel_yang(ohlc, trend=5, threshold=0.01, **kwargs):
    k1, k2 = ohlc.shift(1), ohlc
    both_yang = (k1['Close'] > k1['Open']) & (k2['Close'] > k2['Open'])
    # 高开
    gap_up = (k1['Open'] > k1['Close'].shift(1)) & (k2['Open'] > k2['Close'].shift(1))
    # 高点相近
    high_close = (k1['High'] - k2['High']).abs() <= _avg_span(ohlc, 20) * threshold
    return both_yang & gap_up & high_close & _trend_up(ohlc, trend)


# ── 47. 高位并排阴线（High Parallel Yin Lines, #52）
#     高位两根阴线高点相近
# ──

def detect_high_parallel_yin(ohlc, trend=5, threshold=0.01, **kwargs):
    k1, k2 = ohlc.shift(1), ohlc
    both_yin = (k1['Open'] > k1['Close']) & (k2['Open'] > k2['Close'])
    high_close = (k1['High'] - k2['High']).abs() <= _avg_span(ohlc, 20) * threshold
    return both_yin & high_close & _trend_up(ohlc, trend)


# ── 48. 低位并排阴线（Low Parallel Yin Lines, #53）
#     低位两根阴线低点相近
# ──

def detect_low_parallel_yin(ohlc, trend=5, threshold=0.01, **kwargs):
    k1, k2 = ohlc.shift(1), ohlc
    both_yin = (k1['Open'] > k1['Close']) & (k2['Open'] > k2['Close'])
    low_close = (k1['Low'] - k2['Low']).abs() <= _avg_span(ohlc, 20) * threshold
    return both_yin & low_close & _trend_down(ohlc, trend)


# ── 49. 下跌三颗星（Three Stars Falling, #42）
#     大阴 + 向下跳空小实体（十字/小阴/小阳）+ 第三根不确定（可阴可阳）
# ──

def detect_three_stars_falling(ohlc, trend=5, **kwargs):
    k1, k2, k3 = ohlc.shift(2), ohlc.shift(1), ohlc
    k1_big_yin = (k1['Open'] > k1['Close']) & ((k1['Open'] - k1['Close']) > _avg_body(ohlc, 20) * 1.5)
    # 第二根：向下跳空小实体
    k2_gap_down = k2[['Open', 'Close']].max(axis=1) < k1['Close']
    k2_small = _is_small_body(k2, 20, 0.4)
    # 第三根：可阴可阳，不限制
    return k1_big_yin & k2_gap_down & k2_small & _trend_down(ohlc, trend)


# ── 50. 连续跳空三阳线（Three Gapping Up, #26）
#     三连阳且每日向上跳空（当日Low > 前日High）
# ──

def detect_three_gapping_up(ohlc, trend=5, **kwargs):
    k1, k2, k3 = ohlc.shift(2), ohlc.shift(1), ohlc
    all_yang = (k1['Close'] > k1['Open']) & (k2['Close'] > k2['Open']) & (k3['Close'] > k3['Open'])
    gap1 = k2['Low'] > k1['High']
    gap2 = k3['Low'] > k2['High']
    return all_yang & gap1 & gap2


# ── 51. 连续跳空三阴线（Three Gapping Down, #43）
#     三连阴且每日向下跳空（当日High < 前日Low）
# ──

def detect_three_gapping_down(ohlc, trend=5, **kwargs):
    k1, k2, k3 = ohlc.shift(2), ohlc.shift(1), ohlc
    all_yin = (k1['Open'] > k1['Close']) & (k2['Open'] > k2['Close']) & (k3['Open'] > k3['Close'])
    gap1 = k2['High'] < k1['Low']
    gap2 = k3['High'] < k2['Low']
    return all_yin & gap1 & gap2


# ── 52. 下档五阴线（Five Yin Below, #46）
#     大阳 + 5连阴（小阴为主），5根阴线在大阳实体内或略微超出
# ──

def detect_five_yin_below(ohlc, trend=5, **kwargs):
    result = pd.Series(False, index=ohlc.index)
    for i in range(6, len(ohlc)):
        k0 = ohlc.iloc[i - 6]  # 第1根大阳
        if not (k0['Close'] > k0['Open']):
            continue
        k0_body = k0['Close'] - k0['Open']
        avg_b = float(_avg_body(ohlc.iloc[:i], 20).iloc[-1]) if i > 5 else 0.001
        if k0_body <= avg_b * 1.2:
            continue
        
        # 后续5根：阴线为主（至少4根阴线），小实体
        yin_count = 0
        all_in_range = True
        for j in range(1, 6):
            k = ohlc.iloc[i - 5 + j - 1]  # i-5, i-4, i-3, i-2, i-1
            if k['Open'] > k['Close']:
                yin_count += 1
            # 在大阳实体内或略微超出（允许超出不超过20%的实体）
            k_body = abs(k['Close'] - k['Open'])
            body_ok = k_body <= k0_body * 0.8
            # 价格范围在大阳高低点范围内或略微超出
            price_ok = (k['High'] <= k0['High'] + k0_body * 0.2) and (k['Low'] >= k0['Low'] - k0_body * 0.2)
            if not (body_ok and price_ok):
                all_in_range = False
                break
        
        if yin_count >= 4 and all_in_range:
            result.iloc[i] = True
    return result


# ── 53. 分手线（Separating Lines, #69）
#     开盘价相同，一阴一阳，方向相反
#     注意：和好友反攻/淡友反攻的区别——分手线是相同开盘价，方向分叉
# ──

def detect_separating_lines(ohlc, trend=5, threshold=0.02, **kwargs):
    k1, k2 = ohlc.shift(1), ohlc
    # 方向相反
    k1_black = k1['Open'] > k1['Close']
    k2_green = k2['Close'] > k2['Open']
    # 相同开盘价
    same_open = (k2['Open'] - k1['Open']).abs() <= _avg_span(ohlc, 20) * threshold
    # 或者反向：第一根阳第二根阴
    k1_green = k1['Close'] > k1['Open']
    k2_black = k2['Open'] > k2['Close']
    same_open2 = (k2['Open'] - k1['Open']).abs() <= _avg_span(ohlc, 20) * threshold
    case1 = k1_black & k2_green & same_open
    case2 = k1_green & k2_black & same_open2
    return (case1 | case2)


# ── 54. 一字线（One Line, #62）
#     开高低收完全相同（或极接近，容差 < 0.1% 振幅）
# ──

def detect_one_line(ohlc, **kwargs):
    span = ohlc['High'] - ohlc['Low']
    body = (ohlc['Close'] - ohlc['Open']).abs()
    # 价格极接近：振幅 < 0.1% * 价格
    threshold = ohlc['Close'] * 0.001
    open_close_eq = body <= threshold
    high_low_eq = span <= threshold
    open_high_eq = (ohlc['Open'] - ohlc['High']).abs() <= threshold
    close_low_eq = (ohlc['Close'] - ohlc['Low']).abs() <= threshold
    return open_close_eq & high_low_eq & open_high_eq & close_low_eq


# ── 55. 跳空上扬形（Upside Gap Rising, #27）
#     向上跳空缺口 + 阳线（跳空高开高走）
# ──

def detect_upside_gap_rising(ohlc, trend=5, **kwargs):
    k1, k2 = ohlc.shift(1), ohlc
    # 缺口：K2最低价 > K1最高价（向上跳空）
    gap_up = k2['Low'] > k1['High']
    # K2为阳线
    yang = k2['Close'] > k2['Open']
    return gap_up & yang & _trend_up(ohlc, trend)


print('  -> v5 A-class discrete patterns (12 new) done')


# ═══════════════════════════════════════════════
# v5 新增 — B类连续趋势形态（6种，滑动窗口自适应）
# ═══════════════════════════════════════════════


# ═══════════════════════════════════════════════
# v6 重写 — L1连续趋势形态（8种独立检测函数）
# ═══════════════════════════════════════════════
# 由 DeepSeek 专家模式生成，独立检测函数替代统一滑动窗口。
# 每段连续区间仅标记最终形态确认位置，降低误报率。
# 去重优先级：徐缓 > 抵抗 > 稳步/下跌不止 > 冉冉/绵绵
# ═══════════════════════════════════════════════

def detect_slowly_rising(ohlc: pd.DataFrame, trend: int = 5) -> pd.Series:

    """

    检测「徐缓上升」K线形态。

    

    参数:

        ohlc: 包含列 'Open','High','Low','Close' 的DataFrame

        trend: 保留参数，暂未使用

    返回:

        pd.Series，长度与 ohlc 相同，True 表示该位置窗口满足徐缓上升条件

    """

    # 确保列存在

    required_cols = {'Open', 'High', 'Low', 'Close'}

    if not required_cols.issubset(ohlc.columns):

        raise ValueError(f"ohlc 必须包含列: {required_cols}")

    

    n = len(ohlc)

    open_ = ohlc['Open'].values

    high = ohlc['High'].values

    low = ohlc['Low'].values

    close = ohlc['Close'].values

    

    # 计算基础量

    entity = np.abs(close - open_)               # 实体

    upper_shadow = high - np.maximum(open_, close) # 上影线

    amplitude = high - low                        # 振幅

    is_bull = close > open_                       # 阳线

    

    # 滚动20日平均振幅（用于后续阈值）

    roll_amp20 = pd.Series(amplitude).rolling(window=20, min_periods=1).mean().values

    

    # 窗口大小自适应：默认15，数据不足则取全长

    win = 15 if n >= 15 else n

    

    result = pd.Series(False, index=ohlc.index)

    

    # 逐窗口判断

    for i in range(win - 1, n):

        start = i - win + 1

        end = i + 1  # slice 不含 end

        

        # 切片数据

        ent_win = entity[start:end]

        bull_win = is_bull[start:end]

        close_win = close[start:end]

        upper_win = upper_shadow[start:end]

        open_win = open_[start:end]

        

        # 条件1：阳线比例 >= 70%

        bull_ratio = np.mean(bull_win)

        if bull_ratio < 0.7:

            continue

        

        # 条件2：实体变异系数 CV < 0.5

        mean_ent = np.mean(ent_win)

        if mean_ent == 0:

            continue

        cv = np.std(ent_win) / mean_ent

        if cv >= 0.5:

            continue

        

        # 条件3：平均实体 < 最近20日平均振幅的40%

        avg_amp = roll_amp20[i]

        if mean_ent >= avg_amp * 0.4:

            continue

        

        # 条件4：线性回归斜率 0 < slope < avg_amp * 0.03

        x = np.arange(win)

        # 使用 polyfit 获取斜率

        slope = np.polyfit(x, close_win, 1)[0]

        if not (0 < slope < avg_amp * 0.03):

            continue

        

        # 条件5：不能有长上影线（上影线 > 实体 * 2）

        # 实体可能为0，此时上影线>0即满足条件，会被判为长上影

        if np.any(upper_win > ent_win * 2):

            continue

        

        # 条件6：不能有超过2根明显反向阴线

        # 阴线定义：close < open

        bearish = close_win < open_win

        # 明显反向：实体 > 平均实体 * 1.2

        big_bearish = bearish & (ent_win > mean_ent * 1.2)

        if np.sum(big_bearish) > 2:

            continue

        

        # 所有条件通过

        result.iloc[i] = True

    

    return result

def detect_slowly_falling(ohlc: pd.DataFrame, trend: int = 5) -> pd.Series:

    """

    检测「徐缓下降」K线形态。

    

    参数:

        ohlc: 包含列 'Open','High','Low','Close' 的DataFrame

        trend: 保留参数，暂未使用

    返回:

        pd.Series，长度与 ohlc 相同，True 表示该位置窗口满足徐缓下降条件

    """

    # 确保列存在

    required_cols = {'Open', 'High', 'Low', 'Close'}

    if not required_cols.issubset(ohlc.columns):

        raise ValueError(f"ohlc 必须包含列: {required_cols}")

    

    n = len(ohlc)

    open_ = ohlc['Open'].values

    high = ohlc['High'].values

    low = ohlc['Low'].values

    close = ohlc['Close'].values

    

    # 基础计算

    entity = np.abs(close - open_)               # 实体

    lower_shadow = np.minimum(open_, close) - low # 下影线

    amplitude = high - low                        # 振幅

    is_bear = close < open_                       # 阴线

    

    # 滚动20日平均振幅

    roll_amp20 = pd.Series(amplitude).rolling(window=20, min_periods=1).mean().values

    

    # 窗口大小自适应：默认15，数据不足则取全长

    win = 15 if n >= 15 else n

    

    result = pd.Series(False, index=ohlc.index)

    

    # 逐窗口检测

    for i in range(win - 1, n):

        start = i - win + 1

        end = i + 1

        

        ent_win = entity[start:end]

        bear_win = is_bear[start:end]

        close_win = close[start:end]

        lower_win = lower_shadow[start:end]

        open_win = open_[start:end]

        

        # 条件1：阴线比例 >= 70%

        bear_ratio = np.mean(bear_win)

        if bear_ratio < 0.7:

            continue

        

        # 条件2：实体变异系数 CV < 0.5

        mean_ent = np.mean(ent_win)

        if mean_ent == 0:

            continue

        cv = np.std(ent_win) / mean_ent

        if cv >= 0.5:

            continue

        

        # 条件3：平均实体 < 最近20日平均振幅的40%

        avg_amp = roll_amp20[i]

        if mean_ent >= avg_amp * 0.4:

            continue

        

        # 条件4：线性回归斜率 -avg_amp*0.03 < slope < 0

        x = np.arange(win)

        slope = np.polyfit(x, close_win, 1)[0]

        if not (-avg_amp * 0.03 < slope < 0):

            continue

        

        # 条件5：不能有长下影线（下影线 > 实体*2）

        if np.any(lower_win > ent_win * 2):

            continue

        

        # 条件6：不能有超过2根明显反向阳线

        # 阳线定义：close > open_

        bullish = close_win > open_win

        big_bullish = bullish & (ent_win > mean_ent * 1.2)

        if np.sum(big_bullish) > 2:

            continue

        

        result.iloc[i] = True

    

    return result


def detect_rising_gradually(ohlc: pd.DataFrame, trend: int = 5) -> pd.Series:

    """

    检测「冉冉上升」K线形态。

    

    与徐缓上升相比，冉冉上升更微幅、更均匀、上影线极少。

    

    参数:

        ohlc: 包含列 'Open','High','Low','Close' 的DataFrame

        trend: 保留参数，暂未使用

    返回:

        pd.Series，长度与 ohlc 相同，True 表示该位置窗口满足冉冉上升条件

    """

    required_cols = {'Open', 'High', 'Low', 'Close'}

    if not required_cols.issubset(ohlc.columns):

        raise ValueError(f"ohlc 必须包含列: {required_cols}")

    

    n = len(ohlc)

    open_ = ohlc['Open'].values

    high = ohlc['High'].values

    low = ohlc['Low'].values

    close = ohlc['Close'].values

    

    # 基础计算

    entity = np.abs(close - open_)

    upper_shadow = high - np.maximum(open_, close)   # 上影线

    amplitude = high - low

    is_bull = close > open_

    

    # 滚动20日平均振幅

    roll_amp20 = pd.Series(amplitude).rolling(window=20, min_periods=1).mean().values

    

    # 窗口大小：默认15，数据不足则取全长

    win = 15 if n >= 15 else n

    

    result = pd.Series(False, index=ohlc.index)

    

    for i in range(win - 1, n):

        start = i - win + 1

        end = i + 1

        

        ent_win = entity[start:end]

        bull_win = is_bull[start:end]

        close_win = close[start:end]

        upper_win = upper_shadow[start:end]

        

        # 条件1：阳线比例 >= 75%

        bull_ratio = np.mean(bull_win)

        if bull_ratio < 0.75:

            continue

        

        # 条件2：平均实体 < 最近20日平均振幅的 25%

        mean_ent = np.mean(ent_win)

        avg_amp = roll_amp20[i]

        if mean_ent >= avg_amp * 0.25:

            continue

        

        # 条件3：实体变异系数 CV < 0.4

        if mean_ent == 0:

            continue

        cv = np.std(ent_win) / mean_ent

        if cv >= 0.4:

            continue

        

        # 条件4：斜率轻微向上 0 < slope < avg_amp * 0.015

        x = np.arange(win)

        slope = np.polyfit(x, close_win, 1)[0]

        if not (0 < slope < avg_amp * 0.015):

            continue

        

        # 条件5：反向K线（阴线） ≤ 1根

        bear_count = np.sum(~bull_win)   # close <= open 也算反向

        if bear_count > 1:

            continue

        

        # 条件6：几乎没有上影线：平均上影线 < 平均振幅 * 0.15

        mean_upper = np.mean(upper_win)

        if mean_upper >= avg_amp * 0.15:

            continue

        

        result.iloc[i] = True

    

    return result



def detect_drizzling_falling(ohlc: pd.DataFrame, trend: int = 5) -> pd.Series:

    """

    检测「绵绵阴跌形」K线形态。

    

    与冉冉上升对称：一连串小阴线几乎水平地缓慢下跌，如同绵绵细雨。

    

    参数:

        ohlc: 包含列 'Open','High','Low','Close' 的DataFrame

        trend: 保留参数，暂未使用

    返回:

        pd.Series，长度与 ohlc 相同，True 表示该位置窗口满足绵绵阴跌条件

    """

    required_cols = {'Open', 'High', 'Low', 'Close'}

    if not required_cols.issubset(ohlc.columns):

        raise ValueError(f"ohlc 必须包含列: {required_cols}")

    

    n = len(ohlc)

    open_ = ohlc['Open'].values

    high = ohlc['High'].values

    low = ohlc['Low'].values

    close = ohlc['Close'].values

    

    # 基础计算

    entity = np.abs(close - open_)                    # 实体

    lower_shadow = np.minimum(open_, close) - low     # 下影线

    amplitude = high - low                            # 振幅

    is_bear = close < open_                           # 阴线

    

    # 滚动20日平均振幅

    roll_amp20 = pd.Series(amplitude).rolling(window=20, min_periods=1).mean().values

    

    # 窗口大小：默认15，数据不足则取全长

    win = 15 if n >= 15 else n

    

    result = pd.Series(False, index=ohlc.index)

    

    for i in range(win - 1, n):

        start = i - win + 1

        end = i + 1

        

        ent_win = entity[start:end]

        bear_win = is_bear[start:end]

        close_win = close[start:end]

        lower_win = lower_shadow[start:end]

        

        # 条件1：阴线比例 >= 75%

        bear_ratio = np.mean(bear_win)

        if bear_ratio < 0.75:

            continue

        

        # 条件2：平均实体 < 最近20日平均振幅的 25%

        mean_ent = np.mean(ent_win)

        avg_amp = roll_amp20[i]

        if mean_ent >= avg_amp * 0.25:

            continue

        

        # 条件3：实体变异系数 CV < 0.4

        if mean_ent == 0:

            continue

        cv = np.std(ent_win) / mean_ent

        if cv >= 0.4:

            continue

        

        # 条件4：斜率轻微向下 -avg_amp*0.015 < slope < 0

        x = np.arange(win)

        slope = np.polyfit(x, close_win, 1)[0]

        if not (-avg_amp * 0.015 < slope < 0):

            continue

        

        # 条件5：反向K线（阳线） ≤ 1根

        bull_count = np.sum(~bear_win)   # close >= open 也算反向

        if bull_count > 1:

            continue

        

        # 条件6：几乎没有下影线：平均下影线 < 平均振幅 * 0.15

        mean_lower = np.mean(lower_win)

        if mean_lower >= avg_amp * 0.15:

            continue

        

        result.iloc[i] = True

    

    return result









def detect_steady_rising(ohlc: pd.DataFrame, trend: int = 5) -> pd.Series:

    """

    检测「稳步上涨」K线形态。

    

    特征：窗口内阳线为主，允许少量阴线，实体大小不限，整体斜率向上。

    与徐缓上升(小实体)和冉冉上升(极小实体)的区别在于不限制实体大小。

    

    参数:

        ohlc: 包含列 'Open','High','Low','Close' 的DataFrame

        trend: 保留参数，暂未使用

    返回:

        pd.Series，长度与 ohlc 相同，True 表示该位置窗口满足稳步上涨条件

    """

    required_cols = {'Open', 'High', 'Low', 'Close'}

    if not required_cols.issubset(ohlc.columns):

        raise ValueError(f"ohlc 必须包含列: {required_cols}")

    

    n = len(ohlc)

    open_ = ohlc['Open'].values

    close = ohlc['Close'].values

    

    # 基础计算

    entity = np.abs(close - open_)          # 实体

    is_bull = close > open_                 # 阳线

    is_bear = close < open_                 # 阴线

    

    # 窗口大小：默认15，数据不足取全长

    win = 15 if n >= 15 else n

    

    result = pd.Series(False, index=ohlc.index)

    

    for i in range(win - 1, n):

        start = i - win + 1

        end = i + 1

        

        ent_win = entity[start:end]

        bull_win = is_bull[start:end]

        bear_win = is_bear[start:end]

        close_win = close[start:end]

        

        # 条件1：阳线比例 > 65%

        bull_ratio = np.mean(bull_win)

        if bull_ratio <= 0.65:

            continue

        

        # 条件2：整体向上，斜率 > 0

        x = np.arange(win)

        slope = np.polyfit(x, close_win, 1)[0]

        if slope <= 0:

            continue

        

        # 条件3：明显阴线不能超过3根

        mean_ent = np.mean(ent_win)

        if mean_ent == 0:

            continue   # 全十字星，无意义

        # 明显阴线：阴线且实体 > 平均实体 * 0.8

        obvious_bear = bear_win & (ent_win > mean_ent * 0.8)

        if np.sum(obvious_bear) > 3:

            continue

        

        # 条件4：阴线实体总和 <= 阳线实体总和的 40%

        bull_ent_sum = np.sum(ent_win[bull_win])

        bear_ent_sum = np.sum(ent_win[bear_win])

        if bull_ent_sum == 0 or bear_ent_sum > bull_ent_sum * 0.4:

            continue

        

        result.iloc[i] = True

    

    return result






def detect_endless_falling(ohlc: pd.DataFrame, trend: int = 5) -> pd.Series:

    """

    检测「下跌不止形」K线形态。

    

    特征：窗口内阴线为主，允许少量阳线，实体大小不限，整体斜率向下。

    与稳步上涨对称。

    

    参数:

        ohlc: 包含列 'Open','High','Low','Close' 的DataFrame

        trend: 保留参数，暂未使用

    返回:

        pd.Series，长度与 ohlc 相同，True 表示该位置窗口满足下跌不止形条件

    """

    required_cols = {'Open', 'High', 'Low', 'Close'}

    if not required_cols.issubset(ohlc.columns):

        raise ValueError(f"ohlc 必须包含列: {required_cols}")

    

    n = len(ohlc)

    open_ = ohlc['Open'].values

    close = ohlc['Close'].values

    

    # 基础计算

    entity = np.abs(close - open_)          # 实体

    is_bull = close > open_                 # 阳线

    is_bear = close < open_                 # 阴线

    

    # 窗口大小：默认15，数据不足取全长

    win = 15 if n >= 15 else n

    

    result = pd.Series(False, index=ohlc.index)

    

    for i in range(win - 1, n):

        start = i - win + 1

        end = i + 1

        

        ent_win = entity[start:end]

        bull_win = is_bull[start:end]

        bear_win = is_bear[start:end]

        close_win = close[start:end]

        

        # 条件1：阴线比例 > 65%

        bear_ratio = np.mean(bear_win)

        if bear_ratio <= 0.65:

            continue

        

        # 条件2：整体向下，斜率 < 0

        x = np.arange(win)

        slope = np.polyfit(x, close_win, 1)[0]

        if slope >= 0:

            continue

        

        # 条件3：明显阳线不能超过3根

        mean_ent = np.mean(ent_win)

        if mean_ent == 0:

            continue   # 全十字星，无意义

        # 明显阳线：阳线且实体 > 平均实体 * 0.8

        obvious_bull = bull_win & (ent_win > mean_ent * 0.8)

        if np.sum(obvious_bull) > 3:

            continue

        

        # 条件4：阳线实体总和 <= 阴线实体总和的 40%

        bull_ent_sum = np.sum(ent_win[bull_win])

        bear_ent_sum = np.sum(ent_win[bear_win])

        if bear_ent_sum == 0 or bull_ent_sum > bear_ent_sum * 0.4:

            continue

        

        result.iloc[i] = True

    

    return result
















def detect_rising_resistance(ohlc: pd.DataFrame, trend: int = 5) -> pd.Series:

    """

    检测「上升抵抗形」K线形态。

    

    特征：窗口内整体向上，但出现多根明显阴线（≥3根），

    多方依然主导，阴线只是阻击而非反转。

    

    参数:

        ohlc: 包含列 'Open','High','Low','Close' 的DataFrame

        trend: 保留参数，暂未使用

    返回:

        pd.Series，长度与 ohlc 相同，True 表示该位置窗口满足上升抵抗形条件

    """

    required_cols = {'Open', 'High', 'Low', 'Close'}

    if not required_cols.issubset(ohlc.columns):

        raise ValueError(f"ohlc 必须包含列: {required_cols}")

    

    n = len(ohlc)

    open_ = ohlc['Open'].values

    close = ohlc['Close'].values

    

    # 基础计算

    entity = np.abs(close - open_)          # 实体

    is_bear = close < open_                 # 阴线

    

    # 窗口大小：默认15，数据不足取全长

    win = 15 if n >= 15 else n

    

    result = pd.Series(False, index=ohlc.index)

    

    for i in range(win - 1, n):

        start = i - win + 1

        end = i + 1

        

        ent_win = entity[start:end]

        bear_win = is_bear[start:end]

        close_win = close[start:end]

        

        # 条件1：整体向上，斜率 > 0

        x = np.arange(win)

        slope = np.polyfit(x, close_win, 1)[0]

        if slope <= 0:

            continue

        

        # 平均实体

        mean_ent = np.mean(ent_win)

        if mean_ent == 0:

            continue   # 全十字星，无意义

        

        # 条件2：明显阴线 ≥ 3根（实体 > 平均实体 * 0.8）

        obvious_bear = bear_win & (ent_win > mean_ent * 0.8)

        if np.sum(obvious_bear) < 3:

            continue

        

        # 条件3：上涨实体总和 > 下跌实体总和 * 1.5

        bull_ent_sum = np.sum(ent_win[~bear_win])   # close >= open 的实体

        bear_ent_sum = np.sum(ent_win[bear_win])

        if bull_ent_sum <= bear_ent_sum * 1.5:

            continue

        

        result.iloc[i] = True

    

    return result







def detect_falling_resistance(ohlc: pd.DataFrame, trend: int = 5) -> pd.Series:

    """

    检测「下降抵抗形」K线形态。

    

    特征：窗口内整体向下，但出现多根明显阳线（≥3根），

    空方依然主导，阳线只是抵抗而非反转。

    

    参数:

        ohlc: 包含列 'Open','High','Low','Close' 的DataFrame

        trend: 保留参数，暂未使用

    返回:

        pd.Series，长度与 ohlc 相同，True 表示该位置窗口满足下降抵抗形条件

    """

    required_cols = {'Open', 'High', 'Low', 'Close'}

    if not required_cols.issubset(ohlc.columns):

        raise ValueError(f"ohlc 必须包含列: {required_cols}")

    

    n = len(ohlc)

    open_ = ohlc['Open'].values

    close = ohlc['Close'].values

    

    # 基础计算

    entity = np.abs(close - open_)          # 实体

    is_bull = close > open_                 # 阳线

    

    # 窗口大小：默认15，数据不足取全长

    win = 15 if n >= 15 else n

    

    result = pd.Series(False, index=ohlc.index)

    

    for i in range(win - 1, n):

        start = i - win + 1

        end = i + 1

        

        ent_win = entity[start:end]

        bull_win = is_bull[start:end]

        close_win = close[start:end]

        

        # 条件1：整体向下，斜率 < 0

        x = np.arange(win)

        slope = np.polyfit(x, close_win, 1)[0]

        if slope >= 0:

            continue

        

        # 平均实体

        mean_ent = np.mean(ent_win)

        if mean_ent == 0:

            continue   # 全十字星，无意义

        

        # 条件2：明显阳线 ≥ 3根（实体 > 平均实体 * 0.8）

        obvious_bull = bull_win & (ent_win > mean_ent * 0.8)

        if np.sum(obvious_bull) < 3:

            continue

        

        # 条件3：下跌实体总和 > 上涨实体总和 * 1.5

        bear_ent_sum = np.sum(ent_win[~bull_win])   # close <= open 的实体

        bull_ent_sum = np.sum(ent_win[bull_win])

        if bear_ent_sum <= bull_ent_sum * 1.5:

            continue

        

        result.iloc[i] = True

    

    return result


def detect_tower_top(ohlc, trend=5):
    """
    塔形顶（Tower Top）反转形态。
    逐步上升(3+) → 高位平台(1-3根小实体) → 逐步下降(3+)，形成宝塔状。
    """
    required_cols = {'Open', 'High', 'Low', 'Close'}
    if not required_cols.issubset(ohlc.columns):
        raise ValueError(f'缺少必要列: {required_cols - set(ohlc.columns)}')

    n = len(ohlc)
    open_ = ohlc['Open'].values
    close = ohlc['Close'].values
    high = ohlc['High'].values
    low = ohlc['Low'].values
    entity = np.abs(close - open_)
    
    result = pd.Series(False, index=ohlc.index)
    mean_ent_all = np.mean(entity) if np.mean(entity) > 0 else 0.001

    # 总窗口至少9根K线：上升3+平台1-3下降3+
    for i in range(8, n):
        # 下降段（当前位置i往前3-8根，逐步下跌）
        for decline_len in range(3, 9):
            d_start = i - decline_len + 1
            if d_start < 0:
                continue
            decline_close = close[d_start:i+1]
            if not all(decline_close[j] < decline_close[j-1] for j in range(1, len(decline_close))):
                continue
            decline_entity = entity[d_start:i+1]
            if np.mean(decline_entity) < mean_ent_all * 0.3:
                continue

            # 平台区（d_start前1-3根，小实体窄幅波动）
            for plat_len in range(1, 4):
                p_start = d_start - plat_len
                if p_start < 3:
                    continue
                plat_entity = entity[p_start:d_start]
                if np.mean(plat_entity) > mean_ent_all * 0.5:
                    continue
                plat_high = high[p_start:d_start]
                plat_low = low[p_start:d_start]
                plat_range = np.max(plat_high) - np.min(plat_low)
                total_range = np.max(high[max(0, p_start-3):i+1]) - np.min(low[max(0, p_start-3):i+1])
                if total_range > 0 and plat_range / total_range > 0.3:
                    continue

                # 上升段（p_start往前3-10根，逐步上升）
                for rise_len in range(3, 11):
                    r_start = p_start - rise_len
                    if r_start < 0:
                        continue
                    rise_close = close[r_start:p_start]
                    if not all(rise_close[j] > rise_close[j-1] for j in range(1, len(rise_close))):
                        continue
                    rise_entity = entity[r_start:p_start]
                    if np.mean(rise_entity) < mean_ent_all * 0.3:
                        continue

                    result.iloc[i] = True
                    break
                if result.iloc[i]:
                    break
            if result.iloc[i]:
                break

    return result


def detect_tower_bottom(ohlc, trend=5):
    """
    塔形底（Tower Bottom）反转形态。
    逐步下降(3+) → 低位平台(1-3根小实体) → 逐步上升(3+)，形成倒宝塔状。
    """
    required_cols = {'Open', 'High', 'Low', 'Close'}
    if not required_cols.issubset(ohlc.columns):
        raise ValueError(f'缺少必要列: {required_cols - set(ohlc.columns)}')

    n = len(ohlc)
    open_ = ohlc['Open'].values
    close = ohlc['Close'].values
    high = ohlc['High'].values
    low = ohlc['Low'].values
    entity = np.abs(close - open_)
    
    result = pd.Series(False, index=ohlc.index)
    mean_ent_all = np.mean(entity) if np.mean(entity) > 0 else 0.001

    # 总窗口至少9根K线：下降3+平台1-3上升3+
    for i in range(8, n):
        # 上升段（当前位置i往前3-8根，逐步上升）
        for rise_len in range(3, 9):
            r_start = i - rise_len + 1
            if r_start < 0:
                continue
            rise_close = close[r_start:i+1]
            if not all(rise_close[j] > rise_close[j-1] for j in range(1, len(rise_close))):
                continue
            rise_entity = entity[r_start:i+1]
            if np.mean(rise_entity) < mean_ent_all * 0.3:
                continue

            # 平台区（r_start前1-3根，小实体窄幅波动）
            for plat_len in range(1, 4):
                p_start = r_start - plat_len
                if p_start < 3:
                    continue
                plat_entity = entity[p_start:r_start]
                if np.mean(plat_entity) > mean_ent_all * 0.5:
                    continue
                plat_high = high[p_start:r_start]
                plat_low = low[p_start:r_start]
                plat_range = np.max(plat_high) - np.min(plat_low)
                total_range = np.max(high[max(0, p_start-3):i+1]) - np.min(low[max(0, p_start-3):i+1])
                if total_range > 0 and plat_range / total_range > 0.3:
                    continue

                # 下降段（p_start往前3-10根，逐步下跌）
                for decline_len in range(3, 11):
                    d_start = p_start - decline_len
                    if d_start < 0:
                        continue
                    decline_close = close[d_start:p_start]
                    if not all(decline_close[j] < decline_close[j-1] for j in range(1, len(decline_close))):
                        continue
                    decline_entity = entity[d_start:p_start]
                    if np.mean(decline_entity) < mean_ent_all * 0.3:
                        continue

                    result.iloc[i] = True
                    break
                if result.iloc[i]:
                    break
            if result.iloc[i]:
                break

    return result


def detect_island_top(ohlc, trend=5):
    """
    岛形顶（Island Top）反转形态。
    向上跳空缺口 → 岛屿(1-3根小K线) → 向下跳空缺口。
    通常出现在上涨趋势末端。
    """
    required_cols = {'Open', 'High', 'Low', 'Close'}
    if not required_cols.issubset(ohlc.columns):
        raise ValueError(f'缺少必要列: {required_cols - set(ohlc.columns)}')

    n = len(ohlc)
    open_ = ohlc['Open'].values
    close = ohlc['Close'].values
    high = ohlc['High'].values
    low = ohlc['Low'].values
    entity = np.abs(close - open_)
    
    result = pd.Series(False, index=ohlc.index)
    mean_ent_all = np.mean(entity) if np.mean(entity) > 0 else 0.001

    # 至少需要5根K线：缺口1+岛1-3+缺口1
    for i in range(4, n):
        # 寻找第一个向下跳空缺口（今日high < 昨日low）
        # gap_down 发生在 i 位置
        if not (high[i] < low[i-1]):
            continue

        # 岛区：gap_down 前1-3根K线（小实体，窄幅）
        for island_len in range(1, 4):
            island_end = i - 1
            island_start = i - island_len
            if island_start < 1:
                continue

            # 检查岛区K线——小实体
            island_entity = entity[island_start:island_end+1]
            if np.mean(island_entity) > mean_ent_all * 0.7:
                continue

            # 检查岛区价格范围——窄幅
            island_high = high[island_start:island_end+1]
            island_low = low[island_start:island_end+1]
            island_range = np.max(island_high) - np.min(island_low)
            wider_range = np.max(high[max(0, island_start-1):i+1]) - np.min(low[max(0, island_start-1):i+1])
            if wider_range > 0 and island_range / wider_range > 0.4:
                continue

            # gap_up：岛区前一根K线处（island_start-1位置）
            gap_pos = island_start - 1
            if gap_pos < 1:
                continue
            # 向上跳空：low[gap_pos] > high[gap_pos-1]
            if not (low[gap_pos] > high[gap_pos-1]):
                continue

            # 检查gap_up前5根K线重心是否上移
            lookback_start = max(0, gap_pos - 6)
            pre_close = close[lookback_start:gap_pos+1]
            if len(pre_close) >= 3:
                if not (close[gap_pos] > close[max(gap_pos-3, lookback_start)]):
                    continue

            result.iloc[i] = True
            break

    return result


def detect_island_bottom(ohlc, trend=5):
    """
    岛形底（Island Bottom）反转形态。
    向下跳空缺口 → 岛屿(1-3根小K线) → 向上跳空缺口。
    通常出现在下跌趋势末端。
    """
    required_cols = {'Open', 'High', 'Low', 'Close'}
    if not required_cols.issubset(ohlc.columns):
        raise ValueError(f'缺少必要列: {required_cols - set(ohlc.columns)}')

    n = len(ohlc)
    open_ = ohlc['Open'].values
    close = ohlc['Close'].values
    high = ohlc['High'].values
    low = ohlc['Low'].values
    entity = np.abs(close - open_)
    
    result = pd.Series(False, index=ohlc.index)
    mean_ent_all = np.mean(entity) if np.mean(entity) > 0 else 0.001

    # 至少需要5根K线：缺口1+岛1-3+缺口1
    for i in range(4, n):
        # 寻找第一个向上跳空缺口（今日low > 昨日high）
        # gap_up 发生在 i 位置
        if not (low[i] > high[i-1]):
            continue

        # 岛区：gap_up 前1-3根K线（小实体，窄幅）
        for island_len in range(1, 4):
            island_end = i - 1
            island_start = i - island_len
            if island_start < 1:
                continue

            # 检查岛区K线——小实体
            island_entity = entity[island_start:island_end+1]
            if np.mean(island_entity) > mean_ent_all * 0.7:
                continue

            # 检查岛区价格范围——窄幅
            island_high = high[island_start:island_end+1]
            island_low = low[island_start:island_end+1]
            island_range = np.max(island_high) - np.min(island_low)
            wider_range = np.max(high[max(0, island_start-1):i+1]) - np.min(low[max(0, island_start-1):i+1])
            if wider_range > 0 and island_range / wider_range > 0.4:
                continue

            # gap_down：岛区前一根K线处（island_start-1位置）
            gap_pos = island_start - 1
            if gap_pos < 1:
                continue
            # 向下跳空：high[gap_pos] < low[gap_pos-1]
            if not (high[gap_pos] < low[gap_pos-1]):
                continue

            # 检查gap_down前5根K线重心是否下移
            lookback_start = max(0, gap_pos - 6)
            pre_close = close[lookback_start:gap_pos+1]
            if len(pre_close) >= 3:
                if not (close[gap_pos] < close[max(gap_pos-3, lookback_start)]):
                    continue

            result.iloc[i] = True
            break

    return result


print('  -> v6 L1 sustained trend patterns (8 standalone functions) done')





DETECTORS_L1 = {
    # ── 连续趋势形态（8种，v6独立检测函数）──
    'slowly_rising':        ('徐缓上升', detect_slowly_rising, {}),
    'slowly_falling':       ('徐缓下降', detect_slowly_falling, {}),
    'rising_resistance':    ('上升抵抗形', detect_rising_resistance, {}),
    'falling_resistance':   ('下降抵抗形', detect_falling_resistance, {}),
    'steady_rising':        ('稳步上涨', detect_steady_rising, {}),
    'endless_falling':      ('下跌不止形', detect_endless_falling, {}),
    'rising_gradually':     ('冉冉上升', detect_rising_gradually, {}),
    'drizzling_falling':    ('绵绵阴跌形', detect_drizzling_falling, {}),
}

DETECTORS_L2 = {
    # ── 多K线形态（12种）──
    'rising_three_methods': ('上升三部曲（Rising Three Methods）', detect_rising_three_methods, {}),
    'falling_three_methods': ('下跌三部曲（Falling Three Methods）', detect_falling_three_methods, {}),
    'red_three_soldiers':   ('红三兵', detect_red_three_soldiers, {}),
    'three_white_warriors': ('三个白色武士', detect_three_white_warriors, {}),
    'black_three_soldiers': ('黑三兵', detect_black_three_soldiers, {}),
    'three_black_crows':    ('三只乌鸦（Three Black Crows）', detect_three_black_crows, {}),
    'three_gapping_up':     ('连续跳空三阳线', detect_three_gapping_up, {}),
    'three_gapping_down':   ('连续跳空三阴线', detect_three_gapping_down, {}),
    'five_yin_below':       ('下档五阴线', detect_five_yin_below, {}),
    'two_stars_before_rise':('上涨二颗星', detect_two_stars_before_rise, {}),
    'bullish_sandwich':     ('两红夹一黑', detect_bullish_sandwich, {}),
    'bearish_sandwich':     ('两黑夹一红', detect_bearish_sandwich, {}),
    'rising_stall':         ('升势停顿', detect_rising_stall, {}),
    'rising_stalled':       ('升势受阻', detect_rising_stalled, {}),
    'falling_cover':        ('下降覆盖线', detect_falling_cover, {}),
    'upside_gap_rising':    ('跳空上扬形', detect_upside_gap_rising, {}),
    # ── 塔形/岛形反转形态（4种，v6新增）──
    'tower_top':            ('塔形顶（Tower Top）', detect_tower_top, {}),
    'tower_bottom':         ('塔形底（Tower Bottom）', detect_tower_bottom, {}),
    'island_top':           ('岛形顶（Island Top）', detect_island_top, {}),
    'island_bottom':        ('岛形底（Island Bottom）', detect_island_bottom, {}),
}

DETECTORS_L3 = {
    # ── 2-3K线离散形态（20种）──
    'bearish_engulfing':    ('穿头破脚-看跌', detect_bearish_engulfing, {}),
    'bullish_engulfing':    ('旭日东升', detect_bullish_engulfing, {}),
    'piercing':             ('曙光初现', detect_piercing, {}),
    'bearish_harami':       ('身怀六甲-看跌', detect_bearish_harami, {}),
    'bullish_harami':       ('身怀六甲-看涨', detect_bullish_harami, {}),
    'dark_cloud_cover':     ('乌云盖顶（Dark Cloud Cover）', detect_dark_cloud_cover, {}),
    'heavy_rain':           ('倾盆大雨', detect_heavy_rain, {}),
    'bullish_counterattack':('好友反攻', detect_bullish_counterattack, {}),
    'bearish_counterattack':('淡友反攻', detect_bearish_counterattack, {}),
    'tweezer_bottom':       ('平底（Tweezer Bottom）', detect_tweezer_bottom, {}),
    'tweezer_top':          ('平顶（Tweezer Top）', detect_tweezer_top, {}),
    'evening_star':         ('黄昏之星（Evening Star）', detect_evening_star, {}),
    'morning_star':         ('早晨之星（Morning Star）', detect_morning_star, {}),
    'evening_doji_star':    ('黄昏十字星（Evening Doji Star）', detect_evening_doji_star, {}),
    'morning_doji_star':    ('早晨十字星（Morning Doji Star）', detect_morning_doji_star, {}),
    'low_parallel_yang':    ('低位并排阳线', detect_low_parallel_yang, {}),
    'high_parallel_yang':   ('高位并排阳线', detect_high_parallel_yang, {}),
    'high_parallel_yin':    ('高位并排阴线', detect_high_parallel_yin, {}),
    'low_parallel_yin':     ('低位并排阴线', detect_low_parallel_yin, {}),
    'three_stars_falling':  ('下跌三颗星', detect_three_stars_falling, {}),
    'separating_lines':     ('分手线', detect_separating_lines, {}),
    'bullish_vanguard':     ('多方尖兵（含确认）', detect_bullish_vanguard, {}),
    'bearish_vanguard':     ('空方尖兵（含确认）', detect_bearish_vanguard, {}),
}

DETECTORS_L4 = {
    # ── 单K线形态（14种）──
    'doji':                 ('十字星（Doji/螺旋桨）', detect_doji, {}),
    'big_bullish':          ('大阳线（捉腰带线）', detect_big_bullish, {}),
    'shooting_star':        ('流星线（射击之星）', detect_shooting_star, {}),
    'spinning_top':         ('纺锤线（Spinning Top）', detect_spinning_top, {}),
    'long_doji':            ('长十字星（黄包车夫）', detect_long_doji, {}),
    'dragonfly_doji':       ('蜻蜓十字星（Dragonfly Doji）', detect_dragonfly_doji, {}),
    'gravestone_doji':      ('墓碑十字星（Gravestone Doji）', detect_gravestone_doji, {}),
    't_shape':              ('T字线（T-shaped）', detect_t_shape, {}),
    'inverted_t_shape':     ('倒T字线（Inverted T-shaped）', detect_inverted_t_shape, {}),
    'high_open_escape':     ('高开出逃形', detect_high_open_escape, {}),
    'low_probe_rise':       ('下探上涨形', detect_low_probe_rise, {}),
    'hammer':               ('锤头线（Hammer，含确认）', detect_hammer, {}),
    'hanging_man':          ('上吊线（Hanging Man，含确认）', detect_hanging_man, {}),
    'one_line':             ('一字线', detect_one_line, {}),
}

# 合并所有层级到 DETECTORS（用于兼容旧代码）
DETECTORS = {}
for d in [DETECTORS_L1, DETECTORS_L2, DETECTORS_L3, DETECTORS_L4]:
    DETECTORS.update(d)

# 按层级排序的列表（用于层级检测）
DETECTOR_LEVELS = [
    ('L1', DETECTORS_L1),
    ('L2', DETECTORS_L2),
    ('L3', DETECTORS_L3),
    ('L4', DETECTORS_L4),
]


# ═══════════════════════════════════════════════
# 批量检测入口（层级优先级去重）
# ═══════════════════════════════════════════════

def detect_all(ohlc, **kwargs) -> dict:
    """
    检测所有已注册的K线形态（层级优先级去重）。
    
    每根K线最多只返回最高优先级的那个形态。
    检测顺序：L1（连续趋势）→ L2（多K线）→ L3（2-3K线）→ L4（单K线）
    
    Parameters
    ----------
    ohlc : pd.DataFrame
        包含 Open, High, Low, Close 列的K线数据
    **kwargs : dict
        透传给各检测函数的参数（如 trend, window 等）
    
    Returns
    -------
    dict : {pattern_key: {'name': str, 'signal': pd.Series, 'level': str}}
        signal 为布尔型 Series，True = 该位置触发形态（已去重）
    """
    results = {}
    default_trend = kwargs.get('trend', 5)
    n = len(ohlc)
    
    # 已占用的K线索引（被高优先级形态命中的位置）
    occupied = pd.Series(False, index=ohlc.index)
    
    for level_name, level_dict in DETECTOR_LEVELS:
        for key, (name, func, _) in level_dict.items():
            try:
                if func is not None:
                    # 普通函数检测
                    sig = func(ohlc, trend=default_trend)
                else:
                    sig = pd.Series(False, index=ohlc.index)
                
                # 层级去重：占用位置不能被低优先级形态使用
                sig = sig & ~occupied
                
                # 更新占用标记
                occupied = occupied | sig
                
                results[key] = {'name': name, 'signal': sig, 'level': level_name}
                
            except Exception as e:
                print(f"[WARN] {name} 检测失败: {e}")
                results[key] = {'name': name, 'signal': pd.Series(False, index=ohlc.index), 'level': level_name}
    
    return results


# ═══════════════════════════════════════════════
# 快速查看支持的形态列表
# ═══════════════════════════════════════════════

def list_patterns():
    """返回所有已注册形态的名称列表（按层级分组）"""
    for level_name, level_dict in DETECTOR_LEVELS:
        print(f"\n── {level_name} ──")
        for key, (name, _, _) in level_dict.items():
            print(f"  {key:35s} → {name}")
    print(f"\n总计：{len(DETECTORS)} 种形态")


# ═══════════════════════════════════════════════
# 便捷入口：多时间框架分析
# ═══════════════════════════════════════════════

def analyze(daily_df, trend=5):
    """
    多时间框架K线分析便捷入口。
    
    调用 multi_tf_analyzer 模块进行三级分析并生成报告。
    如果 multi_tf_analyzer 未加载，则只做日K级别检测。
    
    Parameters
    ----------
    daily_df : pd.DataFrame
        日K数据，含 Open, High, Low, Close 列
    trend : int
        趋势判断周期参数，默认5
    
    Returns
    -------
    str : 分析报告
    """
    try:
        from multi_tf_analyzer import generate_report
        return generate_report(daily_df, trend=trend)
    except ImportError:
        # 回退：只做日K检测
        res = detect_all(daily_df, trend=trend)
        lines = [f"=== K线形态分析报告 ===",
                 f"数据范围：{daily_df.index[0]} ~ {daily_df.index[-1]}" if hasattr(daily_df, 'index') else "",
                 f"数据量：{len(daily_df)} 根K线",
                 f"检测形态：{len(res)} 种"]
        active = [(k, v) for k, v in res.items() if v['signal'].any()]
        if active:
            lines.append("\n检测到的形态：")
            for k, v in active:
                cnt = v['signal'].sum()
                lines.append(f"  {v['name']} ({v.get('level','?')}) — {cnt}次触发")
        else:
            lines.append("\n未检测到任何形态。")
        return "\n".join(lines)


# ═══════════════════════════════════════════════
# v6 新增 — 补充分析函数（DeepSeek生成）
# ═══════════════════════════════════════════════

def big_yang_position_analysis(df: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    """
    大阳线位置分析。判断大阳线出现在低位、中位还是高位，
    以及是否连续高位大阳线（诱多预警）。
    """
    required_cols = {'Open', 'High', 'Low', 'Close'}
    if not required_cols.issubset(df.columns):
        raise ValueError(f"必须包含列: {required_cols}")

    n = len(df)
    if n == 0:
        return df.assign(big_yang=False, position='', warning=False)

    open_ = df['Open'].values
    high = df['High'].values
    low = df['Low'].values
    close = df['Close'].values

    body = np.abs(close - open_)
    avg_body = pd.Series(body).shift(1).rolling(window=window, min_periods=1).mean().values

    big_yang = (body > avg_body * 1.5) & (close > open_)

    roll_high = pd.Series(high).rolling(window=60, min_periods=1).max().values
    roll_low = pd.Series(low).rolling(window=60, min_periods=1).min().values
    price_range = roll_high - roll_low

    position = np.full(n, '中位', dtype=object)
    low_zone = roll_low + price_range * 0.1
    high_zone = roll_high - price_range * 0.1

    for i in range(n):
        if close[i] <= low_zone[i]:
            position[i] = '低位'
        elif close[i] >= high_zone[i]:
            position[i] = '高位'

    warning = np.zeros(n, dtype=bool)
    consecutive = 0
    for i in range(n):
        if big_yang[i] and position[i] == '高位':
            consecutive += 1
        else:
            consecutive = 0
        if consecutive >= 3:
            warning[i] = True

    result = df.copy()
    result['big_yang'] = big_yang
    result['position'] = position
    result['warning'] = warning
    return result


def shadow_density_analysis(df: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    """
    影线密度 / 尖刺篱笆检测。
    检测异常长上影线或下影线的密集区域（均值+2σ），
    最近10根中异常占比>30%则标记密集。
    """
    required_cols = {'Open', 'High', 'Low', 'Close'}
    if not required_cols.issubset(df.columns):
        raise ValueError(f"必须包含列: {required_cols}")

    n = len(df)
    if n == 0:
        return df.assign(upper_ratio=0.0, lower_ratio=0.0,
                         upper_anomaly=False, lower_anomaly=False,
                         upper_dense=False, lower_dense=False)

    open_ = df['Open'].values
    high = df['High'].values
    low = df['Low'].values
    close = df['Close'].values

    upper_shadow = high - np.maximum(open_, close)
    lower_shadow = np.minimum(open_, close) - low
    amplitude = high - low

    with np.errstate(divide='ignore', invalid='ignore'):
        upper_ratio = np.where(amplitude > 0, upper_shadow / amplitude, 0.0)
        lower_ratio = np.where(amplitude > 0, lower_shadow / amplitude, 0.0)

    upper_series = pd.Series(upper_ratio, index=df.index)
    lower_series = pd.Series(lower_ratio, index=df.index)

    roll_upper_mean = upper_series.shift(1).rolling(window=window, min_periods=1).mean()
    roll_upper_std = upper_series.shift(1).rolling(window=window, min_periods=1).std(ddof=1)
    roll_lower_mean = lower_series.shift(1).rolling(window=window, min_periods=1).mean()
    roll_lower_std = lower_series.shift(1).rolling(window=window, min_periods=1).std(ddof=1)

    upper_anomaly = pd.Series(upper_ratio > (roll_upper_mean.values + 2 * roll_upper_std.values), index=df.index)
    lower_anomaly = pd.Series(lower_ratio > (roll_lower_mean.values + 2 * roll_lower_std.values), index=df.index)

    upper_dense = upper_anomaly.rolling(window=10, min_periods=1).mean() > 0.3
    lower_dense = lower_anomaly.rolling(window=10, min_periods=1).mean() > 0.3

    result = df.copy()
    result['upper_ratio'] = upper_ratio
    result['lower_ratio'] = lower_ratio
    result['upper_anomaly'] = upper_anomaly
    result['lower_anomaly'] = lower_anomaly
    result['upper_dense'] = upper_dense
    result['lower_dense'] = lower_dense
    return result


def gap_analysis(df: pd.DataFrame, lookback: int = 30) -> pd.DataFrame:
    """
    缺口性质分析：检测跳空缺口并分类为突破、中继或衰竭缺口。
    """
    required_cols = {'Open', 'High', 'Low', 'Close'}
    if not required_cols.issubset(df.columns):
        raise ValueError(f"必须包含列: {required_cols}")

    n = len(df)
    if n == 0:
        return df.assign(gap=False, gap_dir='', gap_type='')

    open_ = df['Open'].values
    high = df['High'].values
    low = df['Low'].values
    close = df['Close'].values
    volume = df['Volume'].values if 'Volume' in df.columns else None

    body = np.abs(close - open_)
    is_gap = np.zeros(n, dtype=bool)
    gap_dir = np.full(n, '', dtype=object)
    gap_type = np.full(n, '', dtype=object)

    for i in range(1, n):
        prev_close = close[i-1]
        curr_open = open_[i]
        gap = curr_open - prev_close
        prev_body = body[i-1]

        if prev_body == 0:
            if abs(gap) <= 0.001:
                continue
            threshold = 0.001
        else:
            threshold = prev_body * 0.15
            if abs(gap) <= threshold:
                continue

        direction = 'up' if gap > 0 else 'down'
        is_gap[i] = True
        gap_dir[i] = direction

        # 回补检测
        filled = False
        check_end = min(i + 3, n - 1)
        if direction == 'up':
            for j in range(i, check_end + 1):
                if low[j] <= prev_close:
                    filled = True
                    break
        else:
            for j in range(i, check_end + 1):
                if high[j] >= prev_close:
                    filled = True
                    break

        if filled:
            gap_type[i] = '衰竭缺口'
        else:
            gap_type[i] = '突破缺口'  # 默认突破，调用方可按需细分

    result = df.copy()
    result['gap'] = is_gap
    result['gap_dir'] = gap_dir
    result['gap_type'] = gap_type
    return result


def judge_trend_state(df: pd.DataFrame, lookback: int = 20) -> dict:
    """
    趋势状态判断：返回趋势方向和强度。
    数据充足时使用ADX(14)，不足时用线性回归斜率+R²。
    """
    required_cols = {'High', 'Low', 'Close'}
    if not required_cols.issubset(df.columns):
        raise ValueError("必须包含列: High, Low, Close")

    n = len(df)
    if n == 0:
        return {"trend": "range", "strength": 0}

    high = df['High'].astype(float).values
    low = df['Low'].astype(float).values
    close = df['Close'].astype(float).values

    if n >= 14:
        period = 14
        tr = np.maximum(high[1:] - low[1:],
                        np.maximum(
                            np.abs(high[1:] - close[:-1]),
                            np.abs(low[1:] - close[:-1])
                        ))
        up_move = high[1:] - high[:-1]
        down_move = low[:-1] - low[1:]
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

        atr = np.zeros(n)
        atr[period] = np.mean(tr[:period])
        plus_di = np.zeros(n)
        minus_di = np.zeros(n)
        adx = np.zeros(n)

        tr_sum = np.sum(tr[:period])
        plus_dm_sum = np.sum(plus_dm[:period])
        minus_dm_sum = np.sum(minus_dm[:period])

        for i in range(period, n-1):
            atr[i] = (atr[i-1] * (period - 1) + tr[i]) / period
            plus_dm_sum = (plus_dm_sum * (period - 1) + plus_dm[i]) / period
            minus_dm_sum = (minus_dm_sum * (period - 1) + minus_dm[i]) / period
            if atr[i] > 0:
                plus_di[i] = 100 * plus_dm_sum / atr[i]
                minus_di[i] = 100 * minus_dm_sum / atr[i]
            dx = 100 * np.abs(plus_di[i] - minus_di[i]) / (plus_di[i] + minus_di[i] + 1e-10)
            adx[i] = (adx[i-1] * (period - 1) + dx) / period

        current_adx = adx[-1]
        di_diff = plus_di[-1] - minus_di[-1]

        if current_adx < 20:
            trend = "range"
        else:
            if di_diff > 5:
                trend = "up"
            elif di_diff < -5:
                trend = "down"
            else:
                trend = "range"
        return {"trend": trend, "strength": round(min(current_adx, 100), 2)}

    else:
        win = min(lookback, n)
        x = np.arange(win)
        y = close[-win:]
        if win < 2:
            return {"trend": "range", "strength": 0}
        coeffs = np.polyfit(x, y, 1)
        slope = coeffs[0]
        y_pred = np.polyval(coeffs, x)
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        avg_price = np.mean(y)
        norm_slope = (slope / avg_price) * 1000 if avg_price != 0 else 0
        strength = min(abs(norm_slope) * r_squared * 100, 100)
        if strength < 10:
            trend = "range"
        elif slope > 1e-6:
            trend = "up"
        elif slope < -1e-6:
            trend = "down"
        else:
            trend = "range"
        return {"trend": trend, "strength": round(strength, 2)}


print('  -> v6 supplementary analysis functions (4 new) done')


if __name__ == '__main__':
    print(f"K线形态大师 v6 — 已注册 {len(DETECTORS)} 种形态（4级层级）+ 4项补充分析\n")
