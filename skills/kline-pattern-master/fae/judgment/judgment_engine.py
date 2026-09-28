"""End-to-end orchestration for the FAE expert judgment layer."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import pandas as pd

from .case_knowledge import CaseKnowledgeBase
from .chart_patterns import ChartPatternDetector
from .conflict_resolver import ConflictResolver
from .context_interpreter import ContextInterpreter
from .evidence_extractor import EvidenceExtractor
from .rule_engine import RuleEngine
from .schemas import DetectedSignal
from .signal_lifecycle import SignalLifecycle


class JudgmentEngine:
    """Combine quantitative evidence, sparse charts, rules, and resolution."""

    def __init__(
        self,
        *,
        rule_engine: RuleEngine | None = None,
        chart_detector: ChartPatternDetector | None = None,
        case_knowledge: CaseKnowledgeBase | None = None,
    ) -> None:
        self.rule_engine = rule_engine or RuleEngine()
        self.chart_detector = chart_detector or ChartPatternDetector()
        self.extractor = EvidenceExtractor()
        self.lifecycle = SignalLifecycle()
        self.interpreter = ContextInterpreter()
        self.resolver = ConflictResolver(self.rule_engine.priority_matrix)
        self.case_knowledge = case_knowledge or CaseKnowledgeBase()

    def evaluate(
        self,
        data: pd.DataFrame,
        candlestick_signals: Sequence[DetectedSignal] = (),
        *,
        reference_levels: Mapping[str, float] | None = None,
        context: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Run the complete offline judgment pipeline on one OHLCV window."""
        chart_signals = self.chart_detector.detect(data)
        signals = [*candlestick_signals, *chart_signals]
        evidence = self.extractor.extract(
            data,
            reference_levels=reference_levels,
            detected_patterns=[signal.pattern for signal in signals],
        )
        evidence.update(
            {
                "breakout_confirmed": any(signal.confirmed for signal in chart_signals),
                "false_break": any(
                    bool(signal.metadata.get("false_break")) for signal in chart_signals
                ),
                "gap_pair_confirmed": any(
                    bool(signal.metadata.get("gap_pair_confirmed"))
                    for signal in chart_signals
                ),
            }
        )
        merged_context = {**evidence, **(context or {})}
        matches = self.rule_engine.match_rules(signals, evidence, merged_context)
        updated: list[DetectedSignal] = []
        lifecycle_reasons: list[str] = []
        for signal in signals:
            applicable = [
                match
                for match in matches
                if signal.pattern in match.rule.get("applies_to", [])
            ]
            signal_evidence = {
                **merged_context,
                "breakout_confirmed": signal.confirmed,
                "false_break": bool(signal.metadata.get("false_break")),
                "gap_pair_confirmed": bool(signal.metadata.get("gap_pair_confirmed")),
            }
            new_signal, reasons = self.lifecycle.update(
                signal, signal_evidence, applicable
            )
            updated.append(new_signal)
            lifecycle_reasons.extend(reasons)
        resolution = self.resolver.resolve(updated, matches, evidence)
        case_matches = self.case_knowledge.search(updated, evidence, merged_context)
        case_consensus = self.case_knowledge.consensus(case_matches)
        resolution = self.case_knowledge.apply_consensus(
            resolution,
            case_consensus,
        )
        interpretations = [
            self.interpreter.interpret(
                signal,
                trend=str(merged_context.get("trend", "range")),
                position_pct=float(merged_context.get("position_pct", 0.5)),
                ma_state=str(merged_context.get("ma_state", "unknown")),
            )
            for signal in updated
        ]
        return {
            "evidence": evidence,
            "signals": [signal.to_dict() for signal in updated],
            "matched_rules": [
                {
                    "rule_id": match.rule_id,
                    "priority": match.priority,
                    "score": match.score,
                    "reasons": match.reasons,
                }
                for match in matches
            ],
            "lifecycle_reasons": lifecycle_reasons,
            "interpretations": interpretations,
            "case_matches": [match.to_dict() for match in case_matches],
            "case_consensus": case_consensus,
            "resolution": resolution.to_dict(),
        }
