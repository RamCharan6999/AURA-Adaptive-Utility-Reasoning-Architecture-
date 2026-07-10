"""Conflict analysis — answers question 2: *what conflict was detected?*

For each quality attribute we find its *champion*: the candidate policy
with the highest score on that attribute alone. If the highest-weighted
QAs have different champions, they demand opposite behaviour — a genuine
conflict, not just disagreement in the numbers. Three distinct champions
is a three-way conflict.
"""

from __future__ import annotations

from typing import Dict, Tuple

from aura_interfaces.context import QAWeights
from aura_core.engine.analyzers.trigger_analyzer import QA_NAMES
from aura_interfaces.evidence import AuraDecision


class ConflictAnalyzer:
    """Detects quality attributes pulling toward different policies."""

    def analyze(
        self, decision: AuraDecision, weights: QAWeights
    ) -> Tuple[bool, str, str, bool]:
        """Return (conflict_detected, conflict_qas, description, three_way).

        A QA whose scores are identical across every candidate is *neutral*:
        it favors nobody, so an arbitrary tie-break must not manufacture a
        conflict (nor hide one). Only QAs with genuine score spread
        participate.
        """
        champions = self.qa_champions(decision)
        spreads = self.qa_spreads(decision)
        active = [qa for qa in QA_NAMES if spreads[qa] > 1e-9]

        # Active QAs ordered by how much the operator cares about them.
        ranked = sorted(active, key=weights.weight_of, reverse=True)

        distinct = {champions[qa] for qa in ranked}
        if len(ranked) == 3 and len(distinct) == 3:
            desc = "; ".join(f"{qa} favors {champions[qa]}" for qa in ranked)
            return True, " vs ".join(ranked), desc, True

        for i in range(len(ranked)):
            for j in range(i + 1, len(ranked)):
                qa_a, qa_b = ranked[i], ranked[j]
                if champions[qa_a] != champions[qa_b]:
                    desc = (
                        f"{qa_a} favors {champions[qa_a]} while "
                        f"{qa_b} favors {champions[qa_b]}"
                    )
                    return True, f"{qa_a} vs {qa_b}", desc, False

        return False, "", "All quality attributes favor the same policy", False

    @staticmethod
    def qa_spreads(decision: AuraDecision) -> Dict[str, float]:
        """Max-min score spread per QA across all candidates."""
        candidates = [decision.selected] + decision.alternatives
        spreads: Dict[str, float] = {}
        for qa in QA_NAMES:
            values = [ev.attributes.get(qa, 0.0) for ev in candidates]
            spreads[qa] = max(values) - min(values)
        return spreads

    @staticmethod
    def qa_champions(decision: AuraDecision) -> Dict[str, str]:
        """Map each QA to the candidate policy that scores highest on it."""
        candidates = [decision.selected] + decision.alternatives
        return {
            qa: max(candidates, key=lambda ev: ev.attributes.get(qa, 0.0)).policy_name
            for qa in QA_NAMES
        }
