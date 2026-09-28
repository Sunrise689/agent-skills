---
name: kline-pattern-master
description: Generate and validate multi-timeframe K-line technical-analysis PDF reports for A-share and Hong Kong symbols. Use when asked to analyze monthly, weekly, and daily price structure; detect candlestick, combination, trend, gap, or chart patterns; regenerate report PNG/PDF artifacts; or debug the local pattern judgment pipeline and case library.
---

# K-line Pattern Master

Generate an evidence-based report from monthly, weekly, and daily bars. Keep internal engine names, raw scores, thresholds, and implementation details out of the PDF.

## Run

From the project root:

```powershell
python scripts/kline_pattern_report.py --symbol sh518880 --name 黄金ETF
```

Use Tencent-format symbols:

- Shanghai: `sh000001`, `sh518880`
- Shenzhen/Beijing: `sz000001`, `bj430047`
- Hong Kong: `hk00700`

Default artifacts are written to the project root:

- `{CODE}_K线形态报告.pdf`
- `{CODE}_m.png`
- `{CODE}_w.png`
- `{CODE}_d.png`
- `{CODE}_supertrend.png`
- `{CODE}_pivot.png`
- `{CODE}_action.png`

## Pipeline

Use this order:

1. Fetch and normalize daily OHLCV data.
2. Resample weekly and monthly bars.
3. Run `scripts/pattern_core_v7.py::detect_all()` for rule-based candidates.
4. Refine candidates by timeframe, position, confirmation, gap state, and mutual exclusion.
5. Convert candidates with `fae.judgment.from_v7_events()`.
6. Evaluate candidates with `fae.judgment.JudgmentEngine` and `fae/judgment/cases/compiled_cases.jsonl`.
7. Suppress invalid, expired, low-confidence, overlapping, or contradictory events.
8. Render charts and build the PDF.

Treat the judgment layer as an objective pattern validator. Determine trend direction, timeframe hierarchy, narrative, and risk language directly from the observed price structure.

If the judgment layer cannot load, use the report script's fallback path and state the degradation in console output only. A normal run must print:

```text
FAE状态：FAE判定引擎
```

## Timeframe Rules

- Monthly: set the primary direction and emphasize simple candlestick patterns.
- Weekly: describe medium-term strength and emphasize combination patterns.
- Daily: identify timing and emphasize trend patterns plus important gaps.
- Keep the three timeframes consistent. Describe an opposing weekly or daily move as a rebound, pullback, or consolidation under the monthly direction.
- Require location and later confirmation for reversal patterns.
- Do not force a named pattern when only basic candle features are present.
- Never output both sides of a mutually exclusive reversal interpretation for the same interval.

## Chart Rules

- Use a white background.
- Use `#26a69a` for rising candles and `#ef5350` for falling candles.
- Use a 250-day moving average for A-share symbols and a 200-day moving average otherwise.
- Draw trend events with thin directional lines, combination events with a box and arrow, and simple events with an ellipse.
- Draw support in green and resistance in red.
- Mark only important breakout gaps and filled gaps on daily and weekly charts.
- Do not discuss monthly gaps.

## Report Rules

- Start with the conclusion, then explain structure, location, and confirmation in plain language.
- Use one `长期趋势判断` chapter containing large-scale structure, support/resistance, multi-timeframe synthesis, and optional sourced market context.
- Keep period headings exactly `月线分析`, `周线分析`, and `日线分析`.
- Give the nearest support and resistance in long-, medium-, and short-horizon conclusions.
- Use conditional observation language. Do not issue direct trading orders.
- Include only patterns that actually appear in the appendix, at most six per page.
- Use SimSun for Chinese text and Times New Roman for Latin text and numbers.

## Validation

Run:

```powershell
python -m py_compile scripts/kline_pattern_report.py fae/judgment/adapters.py fae/judgment/chart_patterns.py
python -m unittest discover -s tests -v
python scripts/kline_pattern_report.py --symbol sh000001 --name 上证指数
```

Then:

1. Render every PDF page to PNG and inspect all pages.
2. Confirm PDF text is extractable and metadata contains the report title and author.
3. Search extracted text for internal engine terms, raw percentages used as confidence labels, obsolete section names, and duplicated shape names.
4. Confirm the monthly, weekly, and daily PNG files are readable and labels align with the intended bars.

Do not change `scripts/pattern_core_v7.py` unless a reproducible detector bug originates there. Prefer fixes in the adapter, judgment layer, conflict resolver, or report output when the core detector is correct.
