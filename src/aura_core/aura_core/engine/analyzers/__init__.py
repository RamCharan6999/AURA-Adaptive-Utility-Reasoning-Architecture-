"""Modular analyzers composing the AURA explanation engine.

Each analyzer answers one of AURA's four questions (formatting is a pure
presentation concern). The engine (core/explanation_engine.py) orchestrates
them; every analyzer is independently importable and unit-testable.
"""

from aura_core.engine.analyzers.trigger_analyzer import (
    TriggerAnalyzer,
    TRIGGER_NOISE_FLOOR,
    CONTEXT_THRESHOLDS,
    QA_NAMES,
)
from aura_core.engine.analyzers.conflict_analyzer import ConflictAnalyzer
from aura_core.engine.analyzers.dominant_qa_analyzer import DominantQAAnalyzer
from aura_core.engine.analyzers.tradeoff_analyzer import (
    TradeoffAnalyzer,
    NOMINAL_LEG_TIME_S,
    NOMINAL_RANGE_M,
    qa_diff_phrase,
)
from aura_core.engine.analyzers.transition_analyzer import TransitionAnalyzer
from aura_core.engine.analyzers.formatter import ExplanationFormatter

__all__ = [
    "TriggerAnalyzer",
    "ConflictAnalyzer",
    "DominantQAAnalyzer",
    "TradeoffAnalyzer",
    "TransitionAnalyzer",
    "ExplanationFormatter",
    "TRIGGER_NOISE_FLOOR",
    "CONTEXT_THRESHOLDS",
    "QA_NAMES",
    "NOMINAL_LEG_TIME_S",
    "NOMINAL_RANGE_M",
    "qa_diff_phrase",
]
