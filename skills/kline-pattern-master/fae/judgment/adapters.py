"""Adapters from the existing pattern_core_v7 event format."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .schemas import (
    DetectedSignal,
    Direction,
    PatternKind,
    SignalState,
    Timeframe,
)

_ALIASES = {
    "大阳线": "large_bullish",
    "大阴线": "large_bearish",
    "小阳线": "small_bullish",
    "小阴线": "small_bearish",
    "十字星": "doji",
    "长十字星": "long_legged_doji",
    "红三兵": "red_three_soldiers",
    "三个白色武士": "three_white_soldiers",
    "三只乌鸦": "three_black_crows",
    "下跌三连阴": "three_falling_candles",
    "倒三阳": "three_reverse_bullish",
    "锤头线": "hammer",
    "倒锤头": "inverted_hammer",
    "吊颈线": "hanging_man",
    "射击之星": "shooting_star",
    "流星线": "shooting_star",
    "纺锤线": "spinning_top",
    "旋转陀螺": "spinning_top",
    "一字线": "one_price_line",
    "早晨之星": "morning_star",
    "黄昏之星": "evening_star",
    "早晨十字星": "morning_doji_star",
    "黄昏十字星": "evening_doji_star",
    "阳包阴": "bullish_engulfing",
    "阴包阳": "bearish_engulfing",
    "看涨吞没": "bullish_engulfing",
    "看跌吞没": "bearish_engulfing",
    "底部穿头破脚": "bullish_engulfing",
    "顶部穿头破脚": "bearish_engulfing",
    "穿头破脚": "engulfing",
    "刺透形态": "piercing_pattern",
    "乌云盖顶": "dark_cloud_cover",
    "孕线": "harami",
    "上升三法": "rising_three_methods",
    "下降三法": "falling_three_methods",
    "塔形顶": "tower_top",
    "塔形底": "tower_bottom",
    "岛形顶": "island_reversal_top",
    "岛形底": "island_reversal_bottom",
    "圆顶": "rounding_top",
    "圆底": "rounding_bottom",
    "双顶": "double_top",
    "双底": "double_bottom",
    "头肩顶": "head_and_shoulders_top",
    "头肩底": "head_and_shoulders_bottom",
    "V形顶": "v_top",
    "V形底": "v_bottom",
    "倒V形顶": "inverted_v_top",
    "上升三角形": "ascending_triangle",
    "下降三角形": "descending_triangle",
    "对称三角形": "symmetrical_triangle",
    "矩形整理": "rectangle",
    "高位并排阳线": "high_parallel_bullish",
    "多方尖兵": "multi_party_pioneer",
    "空方尖兵": "short_party_pioneer",
    "加速上升": "acceleration_line",
    "加速下跌": "acceleration_line",
    "绵绵阴跌": "continuous_decline",
    "稳步上涨": "steady_rise",
    "冉冉上升": "gradual_rise",
    "缓慢爬升": "slow_rise",
    "升势受阻": "rise_blocked",
    "上升抵抗": "rising_resistance",
    "下降抵抗": "falling_resistance",
}

_GAP_ALIASES = {
    "突破缺口": "breakaway_gap",
    "中继缺口": "continuation_gap",
    "衰竭缺口": "exhaustion_gap",
}


def _canonical_name(event: Mapping[str, Any], original_name: str) -> str:
    base_name = original_name.split("·", 1)[0].strip()
    if str(event.get("category", "")).lower() == "gap":
        gap_kind = str(event.get("gap_kind", "")).strip()
        if gap_kind in _GAP_ALIASES:
            return _GAP_ALIASES[gap_kind]
        return (
            "rising_window"
            if str(event.get("gap_direction", "")).lower() == "up"
            else "falling_window"
        )
    return _ALIASES.get(base_name, base_name)


def from_v7_events(
    events: Sequence[Mapping[str, Any]],
    *,
    timeframe: Timeframe = Timeframe.DAILY,
) -> list[DetectedSignal]:
    """Convert ``pattern_core_v7.detect_all`` results into judgment signals."""
    directions = {
        "bull": Direction.BULLISH,
        "bullish": Direction.BULLISH,
        "bear": Direction.BEARISH,
        "bearish": Direction.BEARISH,
        "neutral": Direction.NEUTRAL,
    }
    kinds = {
        "simple": PatternKind.SIMPLE,
        "composite": PatternKind.COMBINATION,
        "combination": PatternKind.COMBINATION,
        "trend": PatternKind.TREND,
        "gap": PatternKind.COMBINATION,
    }
    converted: list[DetectedSignal] = []
    for event in events:
        original_name = str(event.get("name", "")).strip()
        if not original_name:
            continue
        converted.append(
            DetectedSignal(
                pattern=_canonical_name(event, original_name),
                direction=directions.get(
                    str(event.get("direction", "neutral")).lower(),
                    Direction.NEUTRAL,
                ),
                confidence=float(event.get("confidence", 0.5)),
                start=int(event.get("start", event.get("idx", 0))),
                end=int(event.get("end", event.get("idx", 0))),
                kind=kinds.get(
                    str(event.get("category", "simple")).lower(),
                    PatternKind.SIMPLE,
                ),
                timeframe=timeframe,
                state=SignalState.DETECTED,
                metadata={
                    "original_name": original_name,
                    "source": "pattern_core_v7.detect_all",
                    "note": str(event.get("note", "")),
                    "category": str(event.get("category", "simple")),
                    "gap_kind": str(event.get("gap_kind", "")),
                    "gap_direction": str(event.get("gap_direction", "")),
                    "filled": bool(event.get("filled", False)),
                },
            )
        )
    return converted
