"""Dominant-QA analysis — the first half of question 3: *why this decision?*

For a linear utility the winner's margin over the runner-up decomposes
EXACTLY, with no residual:

    gap  =  Σᵢ  wᵢ · (selectedᵢ − rejectedᵢ)

The dominant QA is the term contributing most to the gap — the attribute
that actually decided this decision, which is NOT necessarily the
attribute with the largest weight. This exactness is a core property of
AURA's explanations: they are algebraic facts about the planner's own
numbers, not post-hoc narratives.
"""

from __future__ import annotations

from typing import Dict, Tuple

from aura_interfaces.context import QAWeights
from aura_core.engine.analyzers.trigger_analyzer import QA_NAMES
from aura_interfaces.evidence import AuraDecision


class DominantQAAnalyzer:
    """Decomposes the score gap per quality attribute."""

    @staticmethod
    def decompose(decision: AuraDecision, weights: QAWeights) -> Dict[str, float]:
        """Per-QA weighted contribution to the winner-vs-runner-up gap.

        The values sum to (selected.score − runner_up.score) exactly, up to
        floating point — an invariant enforced by the test suite.
        """
        selected, rejected = decision.selected, decision.runner_up
        return {
            qa: weights.weight_of(qa)
            * (selected.attributes.get(qa, 0.0) - rejected.attributes.get(qa, 0.0))
            for qa in QA_NAMES
        }

    def analyze(
        self, decision: AuraDecision, weights: QAWeights
    ) -> Tuple[str, float, str, Dict[str, float]]:
        """Return (dominant_qa, dominant_weight, reason, gap_decomposition)."""
        contributions = self.decompose(decision, weights)
        dominant = max(contributions, key=lambda qa: contributions[qa])
        selected, rejected = decision.selected, decision.runner_up
        raw_edge = (
            selected.attributes.get(dominant, 0.0)
            - rejected.attributes.get(dominant, 0.0)
        )
        gap = selected.score - rejected.score
        reason = (
            f"{dominant} contributed {contributions[dominant]:+.3f} of the "
            f"{gap:+.3f} score gap (weight {weights.weight_of(dominant):.2f} "
            f"x score edge {raw_edge:+.3f})"
        )
        return dominant, weights.weight_of(dominant), reason, contributions
