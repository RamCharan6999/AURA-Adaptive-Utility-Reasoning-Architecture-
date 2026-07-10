"""Decision evidence structures — the AURA middleware contract.

Any planner that fills a PolicyEvidence for its winner and its rejected
alternatives can be explained by AURA, whether the underlying decision
mechanism is a utility function, a rule table, an RL policy, or an LLM.
This is what makes AURA reusable middleware: it never looks inside the
planner, only at the evidence it publishes.

Mirrors the planned ROS2 messages PolicyEvidence.msg and AuraDecision.msg.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Dict, List

from aura_interfaces.context import RobotContext, QAWeights


@dataclass
class PolicyEvidence:
    """Generic evidence any planner attaches to a candidate policy."""

    policy_name: str
    evidence_type: str                      # utility / rule / rl / llm
    score: float                            # normalized utility, 0.0 - ~1.0
    confidence: float                       # 0.0 - 1.0
    attributes: Dict[str, float] = field(default_factory=dict)   # {qa: score}
    raw_evidence: Dict = field(default_factory=dict)             # planner-specific

    def as_dict(self) -> Dict:
        """Serialise to a plain dict."""
        return asdict(self)


@dataclass
class AuraDecision:
    """One planner decision: the winner plus every rejected candidate."""

    selected: PolicyEvidence
    alternatives: List[PolicyEvidence] = field(default_factory=list)
    policy_changed: bool = False
    previous_policy: str = ""
    timestamp: float = 0.0

    @property
    def runner_up(self) -> PolicyEvidence:
        """The best rejected alternative (alternatives are score-sorted)."""
        if not self.alternatives:
            return self.selected
        return self.alternatives[0]

    def as_dict(self) -> Dict:
        """Serialise to a plain dict."""
        return {
            "selected": self.selected.as_dict(),
            "alternatives": [a.as_dict() for a in self.alternatives],
            "policy_changed": self.policy_changed,
            "previous_policy": self.previous_policy,
            "timestamp": self.timestamp,
        }


