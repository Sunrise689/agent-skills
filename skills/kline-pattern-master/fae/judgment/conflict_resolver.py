"""Resolve simultaneous FAE signals with rules, timeframe, and confirmation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any

from .evidence_extractor import QuantitativeGate
from .schemas import (
    DetectedSignal,
    PatternKind,
    Resolution,
    RuleMatch,
    SignalState,
)


class ConflictResolver:
    """Apply quantitative vetoes before expert and structural priorities."""

    def __init__(
        self,
        priority_matrix: Mapping[str, Any],
        quantitative_gate: QuantitativeGate | None = None,
    ) -> None:
        self.matrix = dict(priority_matrix)
        self.gate = quantitative_gate or QuantitativeGate()

    def _base_score(self, signal: DetectedSignal) -> float:
        kind = self.matrix.get("kind_weight", {})
        timeframe = self.matrix.get("timeframe_weight", {})
        state = self.matrix.get("state_weight", {})
        score = signal.confidence * 100.0
        score += float(kind.get(signal.kind.value, 0))
        score += float(timeframe.get(signal.timeframe.value, 0))
        score += float(state.get(signal.state.value, 0))
        if signal.confirmed:
            score += float(self.matrix.get("confirmed_bonus", 15))
        return score

    def resolve(
        self,
        signals: Sequence[DetectedSignal],
        matched_rules: Sequence[RuleMatch],
        evidence: Mapping[str, Any],
    ) -> Resolution:
        """Return an explainable winner after gate, rule, and hierarchy checks."""
        valid: list[DetectedSignal] = []
        reasons: list[str] = []
        for signal in signals:
            accepted, rejected = self.gate.validate_signal(signal, evidence)
            if accepted:
                valid.append(deepcopy(signal))
            else:
                reasons.append(
                    f"{signal.pattern} 被量化门控否决: {'；'.join(rejected)}"
                )
        if not valid:
            return Resolution(
                winner=None,
                losers=[],
                final_state=SignalState.INVALIDATED,
                confidence=0.0,
                reasons=reasons or ["没有有效信号"],
            )

        scores = {id(signal): self._base_score(signal) for signal in valid}
        applied: list[str] = []
        invalidation: list[str] = []
        for match in matched_rules:
            resolution = match.rule.get("resolution", {})
            winner_name = resolution.get("winner")
            loser_name = resolution.get("loser")
            adjustment = float(resolution.get("confidence_adjustment", 0.0)) * 100
            for signal in valid:
                if signal.pattern == winner_name or (
                    match.rule_id.startswith("chart_")
                    and signal.pattern in match.rule.get("applies_to", [])
                ):
                    scores[id(signal)] += adjustment + match.priority * 0.2
                if signal.pattern == loser_name:
                    scores[id(signal)] -= abs(adjustment) + match.priority * 0.1
            if winner_name or loser_name:
                applied.append(match.rule_id)
                reason = resolution.get("suppression_reason")
                if reason:
                    reasons.append(str(reason))
                description = match.rule.get("invalidation", {}).get("description")
                if description:
                    invalidation.append(str(description))

        # Explicit contract: confirmed chart beats unconfirmed candle; higher
        # timeframe chart beats daily combinations. Measurement targets never
        # enter this score.
        for signal in valid:
            if signal.kind == PatternKind.CHART and signal.confirmed:
                for other in valid:
                    if (
                        other.direction != signal.direction
                        and other.kind in {PatternKind.SIMPLE, PatternKind.COMBINATION}
                        and not other.confirmed
                    ):
                        scores[id(signal)] += 20
                        scores[id(other)] -= 20

        ordered = sorted(valid, key=lambda item: scores[id(item)], reverse=True)
        winner = ordered[0]
        losers = [
            item
            for item in ordered[1:]
            if item.direction != winner.direction
            or item.metadata.get("family") == winner.metadata.get("family")
        ]
        confidence = max(0.0, min(1.0, scores[id(winner)] / 130.0))
        final_state = winner.state
        if (
            any(item.direction != winner.direction for item in ordered[1:])
            and confidence < 0.58
        ):
            final_state = SignalState.DEGRADED
            reasons.append("相反方向证据接近，结论降级等待确认")
        return Resolution(
            winner=winner,
            losers=losers,
            final_state=final_state,
            confidence=confidence,
            applied_rules=applied,
            reasons=reasons,
            invalidation_conditions=list(dict.fromkeys(invalidation)),
        )
