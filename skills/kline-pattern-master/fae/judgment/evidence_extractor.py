"""Extract objective evidence and enforce first-layer quantitative sanity."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
import pandas as pd

from .schemas import DetectedSignal, PatternKind


def normalize_ohlcv(data: pd.DataFrame) -> pd.DataFrame:
    """Return finite, ordered lower-case OHLCV data."""
    if not isinstance(data, pd.DataFrame):
        raise TypeError("data must be a pandas DataFrame")
    frame = data.rename(columns={column: str(column).lower() for column in data})
    required = ["open", "high", "low", "close"]
    missing = [column for column in required if column not in frame]
    if missing:
        raise ValueError(f"missing OHLC columns: {missing}")
    if "volume" not in frame:
        frame = frame.assign(volume=0.0)
    frame = frame[required + ["volume"]].apply(pd.to_numeric, errors="coerce")
    frame = frame.replace([np.inf, -np.inf], np.nan).dropna()
    valid = (
        (frame["close"] > 0)
        & (frame["high"] >= frame[["open", "close"]].max(axis=1))
        & (frame["low"] <= frame[["open", "close"]].min(axis=1))
    )
    return frame.loc[valid].sort_index()


def _consecutive(values: Sequence[bool], wanted: bool = True) -> int:
    count = 0
    for value in reversed(values):
        if bool(value) is wanted:
            count += 1
        else:
            break
    return count


class EvidenceExtractor:
    """Compute context, confirmation, gap, line-break, and density evidence."""

    def extract(
        self,
        data: pd.DataFrame,
        *,
        reference_levels: Mapping[str, float] | None = None,
        detected_patterns: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        """Extract evidence consumed by expert rules and chart validation."""
        frame = normalize_ohlcv(data)
        if len(frame) < 5:
            raise ValueError("at least five valid bars are required")
        levels = dict(reference_levels or {})
        close = frame["close"].to_numpy(float)
        high = frame["high"].to_numpy(float)
        low = frame["low"].to_numpy(float)
        open_ = frame["open"].to_numpy(float)
        volume = frame["volume"].to_numpy(float)
        previous = np.r_[close[0], close[:-1]]
        true_range = np.maximum.reduce(
            [high - low, np.abs(high - previous), np.abs(low - previous)]
        )
        atr = float(np.mean(true_range[-min(14, len(frame)) :]))
        x = np.arange(min(60, len(frame)), dtype=float)
        y = np.log(close[-len(x) :])
        slope, intercept = np.polyfit(x, y, 1)
        fitted = slope * x + intercept
        total = float(np.sum((y - y.mean()) ** 2))
        r_squared = 1.0 - float(np.sum((y - fitted) ** 2)) / total if total else 0.0
        annualized_slope = float(np.expm1(np.clip(slope * 252, -5, 5)))
        trend = (
            "up"
            if annualized_slope > 0.08 and r_squared > 0.25
            else "down"
            if annualized_slope < -0.08 and r_squared > 0.25
            else "range"
        )

        body_pct = np.abs(close - open_) / np.maximum(close, 1e-12) * 100
        returns = close / previous - 1.0
        recent_body_base = float(np.median(body_pct[-min(20, len(frame)) :]))
        big_threshold = max(2.5, recent_body_base * 2.5)
        gap_up = low[1:] > high[:-1] * 1.001
        gap_down = high[1:] < low[:-1] * 0.999
        gap_events: list[tuple[int, str, float]] = []
        for index in np.flatnonzero(gap_up):
            gap_events.append((int(index + 1), "up", float(high[index])))
        for index in np.flatnonzero(gap_down):
            gap_events.append((int(index + 1), "down", float(low[index])))
        gap_events.sort()
        last_gap_filled = False
        if gap_events:
            gap_index, gap_direction, fill_level = gap_events[-1]
            if gap_index < len(frame) - 1:
                last_gap_filled = bool(
                    np.min(low[gap_index + 1 :]) <= fill_level
                    if gap_direction == "up"
                    else np.max(high[gap_index + 1 :]) >= fill_level
                )
        avg_volume = float(np.mean(volume[-min(20, len(frame)) :]))
        volume_ratio = float(volume[-1] / avg_volume) if avg_volume > 0 else 1.0

        evidence: dict[str, Any] = {
            "bar_count": len(frame),
            "trend": trend,
            "trend_slope": annualized_slope,
            "trend_r2": r_squared,
            "position_pct": float(
                (close[-1] - np.min(close)) / max(np.max(close) - np.min(close), 1e-12)
            ),
            "atr": atr,
            "atr_pct": atr / close[-1] * 100.0,
            "volume_ratio": volume_ratio,
            "gap_count": int(gap_up.sum() + gap_down.sum()),
            "up_gap_count": int(gap_up.sum()),
            "down_gap_count": int(gap_down.sum()),
            "last_gap_direction": (
                "up"
                if len(gap_up) and gap_up[-1]
                else "down"
                if len(gap_down) and gap_down[-1]
                else "none"
            ),
            "last_gap_filled": last_gap_filled,
            "big_bullish_count_10": int(
                ((returns[-10:] > 0) & (body_pct[-10:] >= big_threshold)).sum()
            ),
            "big_bearish_count_10": int(
                ((returns[-10:] < 0) & (body_pct[-10:] >= big_threshold)).sum()
            ),
            "recent_return_pct": float(
                (close[-1] / close[-min(20, len(frame))] - 1) * 100
            ),
            "detected_patterns": list(detected_patterns or []),
        }
        for name, level in levels.items():
            level = float(level)
            if not np.isfinite(level) or level <= 0:
                continue
            below = close < level
            above = close > level
            evidence[f"days_below_{name}"] = _consecutive(below)
            evidence[f"days_above_{name}"] = _consecutive(above)
            evidence[f"break_distance_{name}_pct"] = float(
                abs(close[-1] - level) / level * 100
            )
            evidence[f"break_distance_{name}_atr"] = float(
                abs(close[-1] - level) / max(atr, 1e-12)
            )
            evidence[f"reclaim_{name}"] = bool(
                len(close) >= 2 and close[-2] < level <= close[-1]
            )
        if "neckline" in levels:
            evidence["days_below_neckline"] = evidence["days_below_neckline"]
            evidence["break_distance_pct"] = evidence["break_distance_neckline_pct"]
            evidence["break_distance_atr"] = evidence["break_distance_neckline_atr"]
            evidence["reclaim_neckline"] = evidence["reclaim_neckline"]
        if "trendline" in levels:
            evidence["days_below_trendline"] = evidence["days_below_trendline"]
            evidence["reclaim_trendline"] = evidence["reclaim_trendline"]
        return evidence


class QuantitativeGate:
    """Reject impossible or over-dense detections before expert judgment."""

    def __init__(
        self,
        *,
        max_chart_patterns_per_100: int = 3,
        min_chart_bars: int = 20,
        max_overlap_ratio: float = 0.65,
    ) -> None:
        self.max_chart_patterns_per_100 = max_chart_patterns_per_100
        self.min_chart_bars = min_chart_bars
        self.max_overlap_ratio = max_overlap_ratio

    def validate_signal(
        self,
        signal: DetectedSignal,
        evidence: Mapping[str, Any],
    ) -> tuple[bool, list[str]]:
        """Check one signal against basic statistical and logical constraints."""
        reasons: list[str] = []
        span = signal.end - signal.start + 1
        if signal.kind == PatternKind.CHART and span < self.min_chart_bars:
            reasons.append("技术图形持续长度不足")
        if not 0.0 <= signal.confidence <= 1.0:
            reasons.append("置信度不在[0,1]")
        if (
            signal.pattern in {"large_bullish", "大阳线"}
            and int(evidence.get("big_bullish_count_10", 0)) >= 5
        ):
            reasons.append("十根K线中大阳线过密，与第一层量化常识冲突")
        if (
            signal.pattern in {"large_bearish", "大阴线"}
            and int(evidence.get("big_bearish_count_10", 0)) >= 5
        ):
            reasons.append("十根K线中大阴线过密，与第一层量化常识冲突")
        if signal.kind == PatternKind.CHART:
            amplitude_atr = float(signal.metadata.get("amplitude_atr", 0.0))
            if amplitude_atr and amplitude_atr < 2.0:
                reasons.append("图形振幅不足两个ATR，可能只是市场噪声")
            pivot_count = int(signal.metadata.get("pivot_count", 0))
            if (
                pivot_count
                and pivot_count < 3
                and signal.metadata.get("family")
                not in {"v_reversal", "rounding", "island", "diamond"}
            ):
                reasons.append("有效摆动点不足，无法构成技术图形")
        return not reasons, reasons

    def filter_chart_signals(
        self,
        signals: Sequence[DetectedSignal],
        total_bars: int,
    ) -> list[DetectedSignal]:
        """Apply overlap, contradiction, spacing, and density suppression."""
        chart = [item for item in signals if item.kind == PatternKind.CHART]
        chart.sort(key=lambda item: item.confidence, reverse=True)
        kept: list[DetectedSignal] = []
        capacity = max(
            1,
            int(np.ceil(total_bars / 100)) * self.max_chart_patterns_per_100,
        )
        for candidate in chart:
            conflict = False
            for existing in kept:
                overlap = max(
                    0,
                    min(candidate.end, existing.end)
                    - max(candidate.start, existing.start)
                    + 1,
                )
                union = (
                    max(candidate.end, existing.end)
                    - min(candidate.start, existing.start)
                    + 1
                )
                ratio = overlap / max(union, 1)
                opposite = candidate.direction != existing.direction
                same_family = candidate.metadata.get("family") == existing.metadata.get(
                    "family"
                )
                if ratio > self.max_overlap_ratio and (opposite or same_family):
                    conflict = True
                    break
                if (
                    candidate.pattern == existing.pattern
                    and abs(candidate.end - existing.end) < 20
                ):
                    conflict = True
                    break
            if not conflict:
                kept.append(candidate)
            if len(kept) >= capacity:
                break
        return sorted(kept, key=lambda item: item.start)
