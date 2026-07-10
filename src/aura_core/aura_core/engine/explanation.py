"""Explanation data structure produced by AURA.

AuraExplanation mirrors the planned ROS2 AuraExplanation.msg field for
field, plus a few demo-only conveniences (conflict description, uncertainty
flag). One instance is produced per decision cycle.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Dict, Optional


# A decision whose score gap is below this is flagged as "uncertain":
# the planner nearly chose the runner-up, and a human should know that.
UNCERTAIN_GAP_THRESHOLD: float = 0.1


@dataclass
class AuraExplanation:
    """Everything AURA can say about one planner decision."""

    # --- Trigger: what happened -----------------------------------------
    trigger_event: str = "steady_state"
    trigger_value: float = 0.0
    trigger_unit: str = ""
    trigger_description: str = ""

    # --- Conflict: what tension was detected ----------------------------
    conflict_detected: bool = False
    conflict_qas: str = ""                 # e.g. "safety vs time"
    conflict_description: str = ""
    three_way_conflict: bool = False

    # --- Decision: what was chosen ---------------------------------------
    selected_policy: str = ""
    selected_score: float = 0.0
    confidence: float = 0.0

    # --- Tradeoff: why it won --------------------------------------------
    dominant_qa: str = ""
    dominant_weight: float = 0.0
    dominant_reason: str = ""
    # v1.1: benefit/cost are exact weighted-utility quantities derived from
    # the planner's scores, satisfying benefit - cost == score_gap.
    benefit_value: float = 0.0
    benefit_description: str = ""
    cost_value: float = 0.0
    cost_description: str = ""
    # Per-QA weighted contribution to the gap (sums to score_gap exactly).
    gap_decomposition: Dict[str, float] = field(default_factory=dict)

    # --- Rejected alternative: what it beat ------------------------------
    rejected_policy: str = ""
    rejected_score: float = 0.0
    score_gap: float = 0.0
    rejection_reason: str = ""
    uncertain_decision: bool = False       # score_gap < UNCERTAIN_GAP_THRESHOLD

    # --- Transition: what changed since last cycle ------------------------
    policy_changed: bool = False
    previous_policy: str = ""
    changed_context_variable: str = ""
    changed_context_delta: float = 0.0
    change_reason: str = ""
    context_unchanged: bool = False        # true for operator-driven switches

    # --- Human readable ---------------------------------------------------
    explanation_text: str = ""

    # --- Demo bookkeeping (not part of the ROS msg) -----------------------
    timestamp: float = 0.0
    weights: Dict[str, float] = field(default_factory=dict)
    context: Dict[str, float] = field(default_factory=dict)
    qa_scores: Dict[str, Dict[str, float]] = field(default_factory=dict)
    utility_scores: Dict[str, float] = field(default_factory=dict)

    def as_dict(self) -> Dict:
        """Serialise the full explanation (for JSON logs / dashboard)."""
        return asdict(self)

    def csv_row(self) -> Dict:
        """The flat subset of fields written to the CSV logs."""
        return {
            "timestamp": round(self.timestamp, 3),
            "trigger_event": self.trigger_event,
            "selected_policy": self.selected_policy,
            "selected_score": round(self.selected_score, 4),
            "rejected_policy": self.rejected_policy,
            "rejected_score": round(self.rejected_score, 4),
            "score_gap": round(self.score_gap, 4),
            "dominant_qa": self.dominant_qa,
            "dominant_weight": round(self.dominant_weight, 3),
            "benefit_value": round(self.benefit_value, 4),
            "cost_value": round(self.cost_value, 4),
            "policy_changed": self.policy_changed,
            "conflict_qas": self.conflict_qas,
            "uncertain_decision": self.uncertain_decision,
            "explanation_text": self.explanation_text.replace("\n", " | "),
        }
