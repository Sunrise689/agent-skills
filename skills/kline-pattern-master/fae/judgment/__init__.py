"""FAE expert judgment, chart-pattern, and conflict-resolution layer."""

from .adapters import from_v7_events
from .case_knowledge import CaseKnowledgeBase, CaseMatch, CompiledCase
from .chart_patterns import ChartPatternDetector, plot_pattern_geometry
from .conflict_resolver import ConflictResolver
from .context_interpreter import ContextInterpreter
from .evidence_extractor import EvidenceExtractor, QuantitativeGate
from .feedback_store import FeedbackStore
from .judgment_engine import JudgmentEngine
from .rule_engine import RuleEngine
from .schemas import (
    DetectedSignal,
    Direction,
    PatternKind,
    Resolution,
    SignalState,
    Timeframe,
)
from .signal_lifecycle import SignalLifecycle

__all__ = [
    "CaseKnowledgeBase",
    "CaseMatch",
    "ChartPatternDetector",
    "CompiledCase",
    "ConflictResolver",
    "ContextInterpreter",
    "DetectedSignal",
    "Direction",
    "EvidenceExtractor",
    "FeedbackStore",
    "JudgmentEngine",
    "PatternKind",
    "QuantitativeGate",
    "Resolution",
    "RuleEngine",
    "SignalLifecycle",
    "SignalState",
    "Timeframe",
    "from_v7_events",
    "plot_pattern_geometry",
]
