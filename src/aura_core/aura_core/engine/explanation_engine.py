"""AURA explanation engine — the core research contribution.

Given one planner decision (AuraDecision) plus the context and operator
weights around it, the engine answers, at runtime, the four questions:

    1. What happened?                       -> TriggerAnalyzer
    2. What conflict was detected?          -> ConflictAnalyzer
    3. Why was this decision chosen?        -> DominantQAAnalyzer +
                                               TradeoffAnalyzer
    4. What was rejected and why?           -> rejection analysis +
                                               TransitionAnalyzer

v1.1: the engine is an orchestrator over six modular analyzers
(core/analyzers/), each independently unit-tested. The public interface —
``explain()`` plus the per-question methods — is unchanged from v1.0.

Design invariant: AURA never scores, ranks, or alters policies. Every
number here is *read* from the planner's published PolicyEvidence and
*decomposed*. For a linear utility that decomposition is exact:

    gap  =  sum_i w_i * (selected_i - rejected_i)  =  benefit - cost

so explanations are algebraic facts about the planner's own numbers, not
post-hoc narratives (enforced by tests/test_analyzers.py).

Research context: Wohlrab et al. (2023, JSS) explain quality-attribute
tradeoffs OFFLINE over hundreds of policy runs (PRISM + PCA + MCA +
clustering). AURA performs the equivalent decomposition ONLINE, per
decision, within the control loop — the runtime gap that paper names as
future work.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

from aura_interfaces.context import RobotContext, QAWeights
from aura_core.engine.explanation import AuraExplanation, UNCERTAIN_GAP_THRESHOLD
from aura_core.engine.analyzers import (
    TriggerAnalyzer,
    ConflictAnalyzer,
    DominantQAAnalyzer,
    TradeoffAnalyzer,
    TransitionAnalyzer,
    ExplanationFormatter,
    # Re-exported for backward compatibility with v1.0 imports.
    TRIGGER_NOISE_FLOOR,        # noqa: F401
    CONTEXT_THRESHOLDS,         # noqa: F401
    QA_NAMES,                   # noqa: F401
    NOMINAL_LEG_TIME_S,         # noqa: F401
    NOMINAL_RANGE_M,            # noqa: F401
)
from aura_interfaces.evidence import AuraDecision


class ExplanationEngine:
    """Orchestrates the analyzers into one AuraExplanation per decision.

    Stateless per call: the caller supplies the previous context/weights,
    so the same engine serves live scenarios, replayed logs, and one-shot
    permutation snapshots.
    """

    def __init__(self) -> None:
        self.trigger_analyzer = TriggerAnalyzer()
        self.conflict_analyzer = ConflictAnalyzer()
        self.dominant_qa_analyzer = DominantQAAnalyzer()
        self.tradeoff_analyzer = TradeoffAnalyzer()
        self.transition_analyzer = TransitionAnalyzer()
        self.formatter = ExplanationFormatter()

    # --- v1.0-compatible per-question methods (thin delegates) ---------

    def detect_trigger(self, context, previous_context, weights,
                       previous_weights) -> Tuple[str, float, str, str]:
        """Question 1 — see TriggerAnalyzer.analyze."""
        return self.trigger_analyzer.analyze(
            context, previous_context, weights, previous_weights
        )

    def detect_conflict(self, decision, weights) -> Tuple[bool, str, str, bool]:
        """Question 2 — see ConflictAnalyzer.analyze."""
        return self.conflict_analyzer.analyze(decision, weights)

    def find_dominant_qa(self, decision, weights) -> Tuple[str, float, str]:
        """Question 3a — see DominantQAAnalyzer.analyze (v1.0 signature)."""
        dominant, weight, reason, _ = self.dominant_qa_analyzer.analyze(
            decision, weights
        )
        return dominant, weight, reason

    def compute_tradeoff(self, decision, weights,
                         dominant_qa: str = "") -> Tuple[float, str, float, str]:
        """Question 3b — see TradeoffAnalyzer.analyze (v1.0 signature)."""
        benefit, benefit_desc, cost, cost_desc, _ = self.tradeoff_analyzer.analyze(
            decision, weights
        )
        return benefit, benefit_desc, cost, cost_desc

    def detect_transition(self, decision, trigger_event, context,
                          previous_context):
        """Question 4 — see TransitionAnalyzer.analyze."""
        return self.transition_analyzer.analyze(
            decision, trigger_event, context, previous_context
        )

    def generate_explanation_text(self, exp: AuraExplanation) -> str:
        """Render — see ExplanationFormatter.format."""
        return self.formatter.format(exp)

    # --- Orchestration ---------------------------------------------------

    def explain(
        self,
        decision: AuraDecision,
        context: RobotContext,
        weights: QAWeights,
        previous_context: Optional[RobotContext] = None,
        previous_weights: Optional[QAWeights] = None,
    ) -> AuraExplanation:
        """Produce a complete AuraExplanation for one decision."""
        selected, rejected = decision.selected, decision.runner_up

        trigger_event, trigger_value, trigger_unit, trigger_desc = (
            self.trigger_analyzer.analyze(
                context, previous_context, weights, previous_weights
            )
        )
        conflict, conflict_qas, conflict_desc, three_way = (
            self.conflict_analyzer.analyze(decision, weights)
        )
        dominant_qa, dominant_weight, dominant_reason, decomposition = (
            self.dominant_qa_analyzer.analyze(decision, weights)
        )
        benefit_value, benefit_desc, cost_value, cost_desc, _ = (
            self.tradeoff_analyzer.analyze(decision, weights)
        )
        (
            policy_changed,
            previous_policy,
            changed_variable,
            changed_delta,
            change_reason,
            context_unchanged,
        ) = self.transition_analyzer.analyze(
            decision, trigger_event, context, previous_context
        )

        gap = selected.score - rejected.score if decision.alternatives else 0.0
        rejection_reason = (
            f"{rejected.policy_name} scored {rejected.score:.3f} — its edge in "
            f"other attributes did not outweigh {dominant_qa} "
            f"(weight {dominant_weight:.2f})"
        )

        explanation = AuraExplanation(
            trigger_event=trigger_event,
            trigger_value=trigger_value,
            trigger_unit=trigger_unit,
            trigger_description=trigger_desc,
            conflict_detected=conflict,
            conflict_qas=conflict_qas,
            conflict_description=conflict_desc,
            three_way_conflict=three_way,
            selected_policy=selected.policy_name,
            selected_score=selected.score,
            # Confidence: a decisive gap means a confident decision. This is
            # AURA's read of the decision, distinct from planner confidence.
            confidence=min(1.0, 0.5 + gap * 2.5),
            dominant_qa=dominant_qa,
            dominant_weight=dominant_weight,
            dominant_reason=dominant_reason,
            benefit_value=benefit_value,
            benefit_description=benefit_desc,
            cost_value=cost_value,
            cost_description=cost_desc,
            gap_decomposition={qa: round(v, 6) for qa, v in decomposition.items()},
            rejected_policy=rejected.policy_name,
            rejected_score=rejected.score,
            score_gap=gap,
            rejection_reason=rejection_reason,
            uncertain_decision=gap < UNCERTAIN_GAP_THRESHOLD,
            policy_changed=policy_changed,
            previous_policy=previous_policy,
            changed_context_variable=changed_variable,
            changed_context_delta=changed_delta,
            change_reason=change_reason,
            context_unchanged=context_unchanged,
            timestamp=context.timestamp,
            weights=weights.as_dict(),
            context=context.as_dict(),
            qa_scores={
                ev.policy_name: dict(ev.attributes)
                for ev in [decision.selected] + decision.alternatives
            },
            utility_scores={
                ev.policy_name: round(ev.score, 6)
                for ev in [decision.selected] + decision.alternatives
            },
        )
        explanation.explanation_text = self.formatter.format(explanation)
        return explanation
