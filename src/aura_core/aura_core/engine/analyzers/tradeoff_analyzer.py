"""Tradeoff analysis — the second half of question 3: *at what price?*

v1.1 change (research rigor): benefit and cost are now derived EXACTLY
from the planner's own score decomposition, not from heuristics.

Split the per-QA gap decomposition (see DominantQAAnalyzer) by sign:

    benefit = Σ  max(0,  wᵢ·(selᵢ − rejᵢ))     what choosing the winner gained
    cost    = Σ  max(0, −wᵢ·(selᵢ − rejᵢ))     what choosing the winner conceded

By construction:   benefit − cost  ==  score_gap   (exactly)

This invariant is enforced by the test suite. It means every explanation's
tradeoff figures are algebraically faithful to the planner's reasoning —
if AURA says the price of this decision was 0.087 utility, the planner's
arithmetic agrees to the last bit.

Operator-facing unit conversions (seconds / metres / collision margin)
are still attached to the descriptions, clearly labelled as illustrative
estimates for a nominal warehouse leg — they aid intuition but the
utility figures are the ground truth.
"""

from __future__ import annotations

from typing import Dict, Tuple

from aura_interfaces.context import QAWeights
from aura_core.engine.analyzers.trigger_analyzer import QA_NAMES
from aura_core.engine.analyzers.dominant_qa_analyzer import DominantQAAnalyzer
from aura_interfaces.evidence import AuraDecision

# Illustrative converters for operator intuition only (documented in the
# README): a nominal 30 s pickup->dock leg and a 1,000 m full-battery range.
NOMINAL_LEG_TIME_S: float = 30.0
NOMINAL_RANGE_M: float = 1000.0


def qa_diff_phrase(qa: str, raw_diff: float) -> str:
    """Turn a raw QA score difference into an operator-facing phrase."""
    if qa == "safety":
        return f"{raw_diff * 100:+.0f}% collision-avoidance margin"
    if qa == "time":
        return f"{-raw_diff * NOMINAL_LEG_TIME_S:+.1f}s delivery time"
    return f"{raw_diff * NOMINAL_RANGE_M:+.0f}m estimated range"


class TradeoffAnalyzer:
    """Quantifies what was gained and what was paid, exactly."""

    def analyze(
        self, decision: AuraDecision, weights: QAWeights
    ) -> Tuple[float, str, float, str, Dict[str, float]]:
        """Return (benefit_value, benefit_desc, cost_value, cost_desc,
        gap_decomposition).

        benefit_value / cost_value are in weighted-utility units — the
        planner's own currency — and satisfy benefit − cost == score_gap.
        """
        decomposition = DominantQAAnalyzer.decompose(decision, weights)
        selected, rejected = decision.selected, decision.runner_up

        gains = {qa: c for qa, c in decomposition.items() if c > 1e-12}
        losses = {qa: -c for qa, c in decomposition.items() if c < -1e-12}

        benefit_value = sum(gains.values())
        cost_value = sum(losses.values())

        benefit_desc = self._describe(gains, selected, rejected) \
            or "none — no attribute favored the selected policy"
        cost_desc = self._describe(losses, selected, rejected, negate=True) \
            or "none — selected policy dominated on every attribute"

        return benefit_value, benefit_desc, cost_value, cost_desc, decomposition

    @staticmethod
    def _describe(parts: Dict[str, float], selected, rejected,
                  negate: bool = False) -> str:
        """Render one side of the tradeoff: utility terms + intuition units."""
        if not parts:
            return ""
        fragments = []
        for qa, utility in sorted(parts.items(), key=lambda kv: -kv[1]):
            raw = (
                selected.attributes.get(qa, 0.0)
                - rejected.attributes.get(qa, 0.0)
            )
            fragments.append(
                f"{qa} {utility:+.3f} utility (≈ {qa_diff_phrase(qa, raw)})"
            )
        return "; ".join(fragments)
