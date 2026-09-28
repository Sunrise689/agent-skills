"""Sparse, quantitative chart-pattern detection with adaptive geometry.

The detector intentionally returns few patterns. It uses swing points,
regression geometry, ATR-normalized amplitude, confirmation rules, overlap
suppression, and mutual exclusion between top and bottom interpretations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from scipy.signal import find_peaks

from .evidence_extractor import QuantitativeGate, normalize_ohlcv
from .schemas import (
    ArcGeometry,
    DetectedSignal,
    Direction,
    LineGeometry,
    PatternGeometry,
    PatternKind,
    SignalState,
    Timeframe,
)


@dataclass
class _Swings:
    peaks: np.ndarray
    troughs: np.ndarray


def _fit_line(points: np.ndarray, values: np.ndarray) -> tuple[float, float, float]:
    if len(points) < 2:
        return 0.0, float(values[-1]) if len(values) else 0.0, 0.0
    slope, intercept = np.polyfit(points, values, 1)
    fitted = slope * points + intercept
    total = float(np.sum((values - values.mean()) ** 2))
    r2 = 1.0 - float(np.sum((values - fitted) ** 2)) / total if total else 1.0
    return float(slope), float(intercept), max(0.0, min(1.0, r2))


def _similar(values: np.ndarray, tolerance: float = 0.07) -> bool:
    return bool(
        len(values)
        and (float(np.max(values)) - float(np.min(values)))
        / max(abs(float(np.mean(values))), 1e-12)
        <= tolerance
    )


class ChartPatternDetector:
    """Detect reversal and consolidation structures without label flooding."""

    def __init__(
        self,
        *,
        max_patterns_per_100: int = 3,
        min_window: int = 30,
        max_window: int = 120,
        timeframe: Timeframe = Timeframe.DAILY,
    ) -> None:
        self.min_window = min_window
        self.max_window = max_window
        self.timeframe = timeframe
        self.gate = QuantitativeGate(
            max_chart_patterns_per_100=max_patterns_per_100,
            min_chart_bars=max(20, min_window // 2),
        )

    @staticmethod
    def _atr(frame: pd.DataFrame) -> float:
        close = frame["close"].to_numpy(float)
        previous = np.r_[close[0], close[:-1]]
        tr = np.maximum.reduce(
            [
                frame["high"].to_numpy(float) - frame["low"].to_numpy(float),
                np.abs(frame["high"].to_numpy(float) - previous),
                np.abs(frame["low"].to_numpy(float) - previous),
            ]
        )
        return max(float(np.mean(tr[-min(14, len(tr)) :])), close[-1] * 0.002)

    def _swings(self, frame: pd.DataFrame, atr: float) -> _Swings:
        distance = max(3, len(frame) // 14)
        prominence = max(atr * 0.8, float(frame["close"].std()) * 0.12)
        peaks, _ = find_peaks(
            frame["high"].to_numpy(float),
            distance=distance,
            prominence=prominence,
        )
        troughs, _ = find_peaks(
            -frame["low"].to_numpy(float),
            distance=distance,
            prominence=prominence,
        )
        return _Swings(peaks=peaks, troughs=troughs)

    def _signal(
        self,
        pattern: str,
        direction: Direction,
        confidence: float,
        frame: pd.DataFrame,
        geometry: PatternGeometry,
        *,
        family: str,
        atr: float,
        confirmed: bool = False,
        measurement_height: float | None = None,
        breakout_level: float | None = None,
        false_break: bool = False,
        extra: dict[str, Any] | None = None,
    ) -> DetectedSignal:
        offset = int(frame.attrs.get("_offset", 0))
        if offset:
            shifted_lines = [
                LineGeometry(
                    line.role,
                    line.x1 + offset,
                    line.y1,
                    line.x2 + offset,
                    line.y2,
                    line.style,
                )
                for line in geometry.lines
            ]
            shifted_arcs: list[ArcGeometry] = []
            for arc in geometry.arcs:
                a, b, c = arc.coefficients
                shifted_arcs.append(
                    ArcGeometry(
                        arc.role,
                        arc.start + offset,
                        arc.end + offset,
                        (
                            a,
                            b - 2.0 * a * offset,
                            a * offset * offset - b * offset + c,
                        ),
                    )
                )
            geometry = PatternGeometry(
                lines=shifted_lines,
                arcs=shifted_arcs,
                pivots=[
                    (index + offset, value, role)
                    for index, value, role in geometry.pivots
                ],
            )
        height = float(
            measurement_height
            if measurement_height is not None
            else frame["high"].max() - frame["low"].min()
        )
        target = None
        if breakout_level is not None and direction != Direction.NEUTRAL:
            target = (
                breakout_level + height
                if direction == Direction.BULLISH
                else breakout_level - height
            )
        metadata: dict[str, Any] = {
            "family": family,
            "duration": len(frame),
            "amplitude_atr": height / max(atr, 1e-12),
            "pivot_count": len(geometry.pivots),
            "breakout_level": breakout_level,
            "measurement_height": height,
            "measurement_target": target,
            "measurement_is_reference_only": True,
            "false_break": false_break,
            "confirmation": (
                "收盘离开边界至少max(1%,0.5ATR)，并满足放量1.2倍或连续2日"
            ),
        }
        metadata.update(extra or {})
        return DetectedSignal(
            pattern=pattern,
            direction=direction,
            confidence=confidence,
            start=offset,
            end=offset + len(frame) - 1,
            kind=PatternKind.CHART,
            timeframe=self.timeframe,
            state=SignalState.CONFIRMED if confirmed else SignalState.CANDIDATE,
            confirmed=confirmed,
            geometry=geometry,
            metadata=metadata,
        )

    @staticmethod
    def _breakout(
        frame: pd.DataFrame,
        level: float,
        direction: Direction,
        atr: float,
    ) -> tuple[bool, bool]:
        close = frame["close"].to_numpy(float)
        margin = max(level * 0.01, atr * 0.5)
        if direction == Direction.BULLISH:
            outside = close > level + margin
            reclaimed = len(close) >= 2 and close[-2] > level and close[-1] <= level
        else:
            outside = close < level - margin
            reclaimed = len(close) >= 2 and close[-2] < level and close[-1] >= level
        days = 0
        for value in outside[::-1]:
            if value:
                days += 1
            else:
                break
        volume = frame["volume"].to_numpy(float)
        volume_ok = (
            volume[-1] >= np.mean(volume[-min(20, len(volume)) :]) * 1.2
            if np.mean(volume) > 0
            else False
        )
        return bool(days >= 2 or (outside[-1] and volume_ok)), bool(reclaimed)

    def _reversal_candidates(
        self,
        frame: pd.DataFrame,
        swings: _Swings,
        atr: float,
    ) -> list[DetectedSignal]:
        high = frame["high"].to_numpy(float)
        low = frame["low"].to_numpy(float)
        close = frame["close"].to_numpy(float)
        candidates: list[DetectedSignal] = []

        for indexes, values, direction, suffix in (
            (swings.peaks, high, Direction.BEARISH, "top"),
            (swings.troughs, low, Direction.BULLISH, "bottom"),
        ):
            if len(indexes) >= 2:
                pair = indexes[-2:]
                if _similar(values[pair], 0.06) and pair[1] - pair[0] >= 5:
                    between = (
                        np.min(low[pair[0] : pair[1] + 1])
                        if suffix == "top"
                        else np.max(high[pair[0] : pair[1] + 1])
                    )
                    confirmed, false_break = self._breakout(
                        frame, float(between), direction, atr
                    )
                    geometry = PatternGeometry(
                        lines=[
                            LineGeometry(
                                "neckline",
                                int(pair[0]),
                                float(between),
                                len(frame) - 1,
                                float(between),
                            )
                        ],
                        pivots=[
                            (int(index), float(values[index]), suffix) for index in pair
                        ],
                    )
                    candidates.append(
                        self._signal(
                            f"double_{suffix}",
                            direction,
                            0.68 + 0.12 * confirmed,
                            frame,
                            geometry,
                            family="multiple_top_bottom",
                            atr=atr,
                            confirmed=confirmed,
                            measurement_height=abs(
                                float(np.mean(values[pair])) - float(between)
                            ),
                            breakout_level=float(between),
                            false_break=false_break,
                        )
                    )
            if len(indexes) >= 3:
                triple = indexes[-3:]
                heights = values[triple]
                if _similar(heights, 0.08):
                    neckline = (
                        float(np.min(low[triple[0] : triple[-1] + 1]))
                        if suffix == "top"
                        else float(np.max(high[triple[0] : triple[-1] + 1]))
                    )
                    confirmed, false_break = self._breakout(
                        frame, neckline, direction, atr
                    )
                    geometry = PatternGeometry(
                        lines=[
                            LineGeometry(
                                "neckline",
                                int(triple[0]),
                                neckline,
                                len(frame) - 1,
                                neckline,
                            )
                        ],
                        pivots=[
                            (int(index), float(values[index]), suffix)
                            for index in triple
                        ],
                    )
                    candidates.append(
                        self._signal(
                            f"triple_{suffix}",
                            direction,
                            0.72 + 0.12 * confirmed,
                            frame,
                            geometry,
                            family="multiple_top_bottom",
                            atr=atr,
                            confirmed=confirmed,
                            measurement_height=abs(float(np.mean(heights)) - neckline),
                            breakout_level=neckline,
                            false_break=false_break,
                        )
                    )
                shoulder_tolerance = abs(heights[0] - heights[2]) / max(
                    abs(float(np.mean(heights[[0, 2]]))), 1e-12
                )
                middle_extreme = (
                    heights[1] > max(heights[0], heights[2]) * 1.03
                    if suffix == "top"
                    else heights[1] < min(heights[0], heights[2]) * 0.97
                )
                if shoulder_tolerance <= 0.09 and middle_extreme:
                    inner = sorted(
                        [
                            int(index)
                            for index in (
                                swings.troughs if suffix == "top" else swings.peaks
                            )
                            if triple[0] < index < triple[-1]
                        ]
                    )
                    if len(inner) >= 2:
                        inner = inner[-2:]
                        inner_values = low[inner] if suffix == "top" else high[inner]
                        slope, intercept, _ = _fit_line(np.asarray(inner), inner_values)
                        neckline = slope * (len(frame) - 1) + intercept
                        confirmed, false_break = self._breakout(
                            frame, float(neckline), direction, atr
                        )
                        geometry = PatternGeometry(
                            lines=[
                                LineGeometry(
                                    "neckline",
                                    inner[0],
                                    float(inner_values[0]),
                                    len(frame) - 1,
                                    float(neckline),
                                )
                            ],
                            pivots=[
                                (int(index), float(values[index]), suffix)
                                for index in triple
                            ],
                        )
                        compound = len(indexes) >= 5 and _similar(
                            values[indexes[-5:][[0, 1, 3, 4]]], 0.12
                        )
                        candidates.append(
                            self._signal(
                                f"{'compound_' if compound else ''}head_and_shoulders_{suffix}",
                                direction,
                                0.78 + 0.12 * confirmed,
                                frame,
                                geometry,
                                family="head_and_shoulders",
                                atr=atr,
                                confirmed=confirmed,
                                measurement_height=abs(
                                    float(heights[1]) - float(neckline)
                                ),
                                breakout_level=float(neckline),
                                false_break=false_break,
                            )
                        )

        x = np.arange(len(frame), dtype=float)
        normalized = (close - close.mean()) / max(close.std(), 1e-12)
        quadratic = np.polyfit(x / max(len(frame) - 1, 1), normalized, 2)
        fitted = np.polyval(quadratic, x / max(len(frame) - 1, 1))
        total = float(np.sum((normalized - normalized.mean()) ** 2))
        r2 = 1.0 - float(np.sum((normalized - fitted) ** 2)) / total if total else 0
        if abs(quadratic[0]) > 0.7 and r2 > 0.45:
            bottom = quadratic[0] > 0
            direction = Direction.BULLISH if bottom else Direction.BEARISH
            boundary = float(np.max(close) if bottom else np.min(close))
            confirmed, false_break = self._breakout(frame, boundary, direction, atr)
            geometry = PatternGeometry(
                arcs=[
                    ArcGeometry(
                        "rounding_bottom" if bottom else "rounding_top",
                        0,
                        len(frame) - 1,
                        tuple(float(value) for value in np.polyfit(x, close, 2)),
                    )
                ]
            )
            candidates.append(
                self._signal(
                    "rounding_bottom" if bottom else "rounding_top",
                    direction,
                    min(0.88, 0.55 + r2 * 0.3),
                    frame,
                    geometry,
                    family="rounding",
                    atr=atr,
                    confirmed=confirmed,
                    breakout_level=boundary,
                    false_break=false_break,
                )
            )

        extreme_bottom = int(np.argmin(low))
        extreme_top = int(np.argmax(high))
        for extreme, bottom in ((extreme_bottom, True), (extreme_top, False)):
            if len(frame) * 0.2 < extreme < len(frame) * 0.8:
                left = close[: extreme + 1]
                right = close[extreme:]
                left_slope, _, left_r2 = _fit_line(np.arange(len(left)), left)
                right_slope, _, right_r2 = _fit_line(np.arange(len(right)), right)
                correct = (
                    left_slope < 0 < right_slope
                    if bottom
                    else left_slope > 0 > right_slope
                )
                if correct and min(left_r2, right_r2) > 0.55:
                    geometry = PatternGeometry(
                        lines=[
                            LineGeometry(
                                "left_leg",
                                0,
                                float(close[0]),
                                extreme,
                                float(close[extreme]),
                            ),
                            LineGeometry(
                                "right_leg",
                                extreme,
                                float(close[extreme]),
                                len(frame) - 1,
                                float(close[-1]),
                            ),
                        ],
                        pivots=[(extreme, float(close[extreme]), "vertex")],
                    )
                    candidates.append(
                        self._signal(
                            "v_bottom" if bottom else "inverted_v_top",
                            Direction.BULLISH if bottom else Direction.BEARISH,
                            0.72,
                            frame,
                            geometry,
                            family="v_reversal",
                            atr=atr,
                            confirmed=True,
                        )
                    )

        gap_up = low[1:] > high[:-1] * 1.001
        gap_down = high[1:] < low[:-1] * 0.999
        up_indexes = np.flatnonzero(gap_up) + 1
        down_indexes = np.flatnonzero(gap_down) + 1
        if len(up_indexes) and len(down_indexes):
            pairs: list[tuple[int, int, bool]] = []
            for first in up_indexes:
                for second in down_indexes:
                    if first < second <= first + max(12, len(frame) // 3):
                        pairs.append((int(first), int(second), True))
            for first in down_indexes:
                for second in up_indexes:
                    if first < second <= first + max(12, len(frame) // 3):
                        pairs.append((int(first), int(second), False))
            for first, second, top in sorted(pairs, key=lambda item: item[1], reverse=True):
                island_high = float(np.max(high[first:second]))
                island_low = float(np.min(low[first:second]))
                if top:
                    separated = island_low > max(float(high[first - 1]), float(high[second])) * 1.001
                    followed_through = float(close[-1]) < island_low
                    invalidated = bool(np.any(close[second:] > island_high))
                else:
                    separated = island_high < min(float(low[first - 1]), float(low[second])) * 0.999
                    followed_through = float(close[-1]) > island_high
                    invalidated = bool(np.any(close[second:] < island_low))
                if not separated or not followed_through or invalidated:
                    continue
                geometry = PatternGeometry(
                    pivots=[
                        (first, float(close[first]), "island_start"),
                        (second, float(close[second]), "island_end"),
                    ]
                )
                candidates.append(
                    self._signal(
                        "island_reversal_top" if top else "island_reversal_bottom",
                        Direction.BEARISH if top else Direction.BULLISH,
                        0.84,
                        frame,
                        geometry,
                        family="island",
                        atr=atr,
                        confirmed=True,
                        extra={"gap_pair_confirmed": True},
                    )
                )
                break

        half = len(frame) // 2
        first_range = (
            frame["high"].iloc[:half].rolling(max(3, half // 4)).max()
            - frame["low"].iloc[:half].rolling(max(3, half // 4)).min()
        ).dropna()
        second_range = (
            frame["high"].iloc[half:].rolling(max(3, half // 4)).max()
            - frame["low"].iloc[half:].rolling(max(3, half // 4)).min()
        ).dropna()
        if (
            len(first_range) >= 2
            and len(second_range) >= 2
            and first_range.iloc[-1] > first_range.iloc[0] * 1.2
            and second_range.iloc[-1] < second_range.iloc[0] * 0.8
        ):
            candidates.append(
                self._signal(
                    "diamond",
                    Direction.BEARISH if close[-1] < close[half] else Direction.BULLISH,
                    0.62,
                    frame,
                    PatternGeometry(),
                    family="diamond",
                    atr=atr,
                    confirmed=False,
                    extra={"requires_breakout_direction": True},
                )
            )
        return candidates

    def _consolidation_candidates(
        self,
        frame: pd.DataFrame,
        swings: _Swings,
        atr: float,
    ) -> list[DetectedSignal]:
        if len(swings.peaks) < 2 or len(swings.troughs) < 2:
            return []
        high = frame["high"].to_numpy(float)
        low = frame["low"].to_numpy(float)
        close = frame["close"].to_numpy(float)
        p = swings.peaks[-min(4, len(swings.peaks)) :]
        t = swings.troughs[-min(4, len(swings.troughs)) :]
        upper_slope, upper_intercept, upper_r2 = _fit_line(p, high[p])
        lower_slope, lower_intercept, lower_r2 = _fit_line(t, low[t])
        upper_end = upper_slope * (len(frame) - 1) + upper_intercept
        lower_end = lower_slope * (len(frame) - 1) + lower_intercept
        start_width = (
            upper_slope * min(p[0], t[0])
            + upper_intercept
            - (lower_slope * min(p[0], t[0]) + lower_intercept)
        )
        end_width = upper_end - lower_end
        flat_tol = max(atr * 0.08, float(close.mean()) * 0.0005)
        boundary_span = max(1, len(frame) - min(int(p[0]), int(t[0])) - 1)
        boundary_move = max(abs(upper_slope), abs(lower_slope)) * boundary_span
        boundary_limit = max(atr * 1.5, float(close.mean()) * 0.04)
        geometry = PatternGeometry(
            lines=[
                LineGeometry(
                    "resistance",
                    int(p[0]),
                    float(high[p[0]]),
                    len(frame) - 1,
                    float(upper_end),
                ),
                LineGeometry(
                    "support",
                    int(t[0]),
                    float(low[t[0]]),
                    len(frame) - 1,
                    float(lower_end),
                ),
            ],
            pivots=[
                *[(int(index), float(high[index]), "peak") for index in p],
                *[(int(index), float(low[index]), "trough") for index in t],
            ],
        )
        candidates: list[DetectedSignal] = []
        pattern = ""
        direction = Direction.NEUTRAL
        if abs(upper_slope) <= flat_tol and lower_slope > flat_tol:
            pattern, direction = "ascending_triangle", Direction.BULLISH
        elif upper_slope < -flat_tol and abs(lower_slope) <= flat_tol:
            pattern, direction = "descending_triangle", Direction.BEARISH
        elif (
            upper_slope < -flat_tol
            and lower_slope > flat_tol
            and end_width < start_width
        ):
            pattern = "symmetrical_triangle"
            direction = (
                Direction.BULLISH
                if close[-1] > upper_end
                else Direction.BEARISH
                if close[-1] < lower_end
                else Direction.NEUTRAL
            )
        elif (
            upper_slope > flat_tol
            and lower_slope > flat_tol
            and end_width < start_width
        ):
            pattern, direction = "rising_wedge", Direction.BEARISH
        elif (
            upper_slope < -flat_tol
            and lower_slope < -flat_tol
            and end_width < start_width
        ):
            pattern, direction = "falling_wedge", Direction.BULLISH
        elif (
            abs(upper_slope) <= flat_tol
            and abs(lower_slope) <= flat_tol
            and boundary_move <= boundary_limit
            and min(upper_r2, lower_r2) >= 0.25
        ):
            pattern, direction = "rectangle", Direction.NEUTRAL
        elif end_width > start_width * 1.25:
            pattern, direction = "broadening_triangle", Direction.BEARISH
        if pattern:
            if direction == Direction.NEUTRAL:
                confirmed = close[-1] > upper_end + max(
                    atr * 0.5, upper_end * 0.01
                ) or close[-1] < lower_end - max(atr * 0.5, lower_end * 0.01)
                if confirmed:
                    direction = (
                        Direction.BULLISH
                        if close[-1] > upper_end
                        else Direction.BEARISH
                    )
                false_break = False
                breakout_level = (
                    upper_end if direction == Direction.BULLISH else lower_end
                )
            else:
                breakout_level = (
                    upper_end if direction == Direction.BULLISH else lower_end
                )
                confirmed, false_break = self._breakout(
                    frame, float(breakout_level), direction, atr
                )
            candidates.append(
                self._signal(
                    pattern,
                    direction,
                    0.56 + 0.16 * min(upper_r2, lower_r2) + 0.1 * confirmed,
                    frame,
                    geometry,
                    family="consolidation",
                    atr=atr,
                    confirmed=bool(confirmed),
                    measurement_height=max(start_width, end_width),
                    breakout_level=float(breakout_level),
                    false_break=bool(false_break),
                )
            )

        impulse_end = max(5, len(frame) // 4)
        impulse = close[impulse_end] - close[0]
        channel_slope, _, channel_r2 = _fit_line(
            np.arange(len(frame) - impulse_end),
            close[impulse_end:],
        )
        if abs(impulse) >= atr * 4 and channel_r2 >= 0.25:
            if (
                impulse > 0
                and channel_slope <= 0
                and abs(channel_slope) < abs(impulse) / len(frame)
            ):
                flag, direction = "ascending_flag", Direction.BULLISH
            elif (
                impulse < 0
                and channel_slope >= 0
                and abs(channel_slope) < abs(impulse) / len(frame)
            ):
                flag, direction = "descending_flag", Direction.BEARISH
            else:
                flag = ""
            if flag:
                level = float(
                    frame["high"].iloc[impulse_end:].max()
                    if direction == Direction.BULLISH
                    else frame["low"].iloc[impulse_end:].min()
                )
                confirmed, false_break = self._breakout(frame, level, direction, atr)
                candidates.append(
                    self._signal(
                        flag,
                        direction,
                        0.66 + 0.12 * confirmed,
                        frame,
                        geometry,
                        family="flag",
                        atr=atr,
                        confirmed=confirmed,
                        measurement_height=abs(float(impulse)),
                        breakout_level=level,
                        false_break=false_break,
                    )
                )
        return candidates

    def detect(self, data: pd.DataFrame) -> list[DetectedSignal]:
        """Detect at most a few non-overlapping chart patterns per 100 bars."""
        frame = normalize_ohlcv(data)
        if len(frame) < self.min_window:
            return []
        all_candidates: list[DetectedSignal] = []
        lengths = sorted(
            {
                self.min_window,
                min(45, self.max_window),
                min(60, self.max_window),
                min(80, self.max_window),
                min(100, self.max_window),
                min(len(frame), self.max_window),
            }
        )
        for length in lengths:
            if length > len(frame) or length < self.min_window:
                continue
            window = frame.iloc[-length:].copy()
            window.attrs["_offset"] = len(frame) - length
            atr = self._atr(window)
            swings = self._swings(window, atr)
            all_candidates.extend(self._reversal_candidates(window, swings, atr))
            all_candidates.extend(self._consolidation_candidates(window, swings, atr))
        return self.gate.filter_chart_signals(all_candidates, len(frame))


def plot_pattern_geometry(
    axes: Any,
    signal: DetectedSignal,
    *,
    color: str = "#8B1E3F",
) -> None:
    """Draw adaptive straight lines, arcs, and pivots on a Matplotlib axes."""
    geometry = signal.geometry
    if geometry is None:
        return
    for line in geometry.lines:
        axes.plot(
            [line.x1, line.x2],
            [line.y1, line.y2],
            color=color,
            linestyle="--" if line.style == "dashed" else "-",
            linewidth=1.4,
            alpha=0.9,
        )
    for arc in geometry.arcs:
        x = np.linspace(arc.start, arc.end, 80)
        y = np.polyval(np.asarray(arc.coefficients, dtype=float), x)
        axes.plot(x, y, color=color, linewidth=1.6, alpha=0.9)
    if geometry.pivots:
        axes.scatter(
            [item[0] for item in geometry.pivots],
            [item[1] for item in geometry.pivots],
            s=18,
            color=color,
            zorder=6,
        )
