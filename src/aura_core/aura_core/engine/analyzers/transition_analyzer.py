"""Transition analysis — question 4's second half: *what changed to cause
a policy switch?*

If the trigger was an operator weight change and the context is unchanged,
AURA flags that explicitly: the world did not change, the human's
priorities did. This is the human-in-the-loop case (Scenario 5), and it is
the distinction that makes preference changes auditable.
"""

from __future__ import annotations

from typing import Optional, Tuple

from aura_interfaces.context import RobotContext, MISSION_LEVELS
from aura_core.engine.analyzers.trigger_analyzer import TRIGGER_NOISE_FLOOR
from aura_interfaces.evidence import AuraDecision


class TransitionAnalyzer:
    """Explains policy switches in terms of what caused them."""

    def analyze(
        self,
        decision: AuraDecision,
        trigger_event: str,
        context: RobotContext,
        previous_context: Optional[RobotContext],
    ) -> Tuple[bool, str, str, float, str, bool]:
        """Return (policy_changed, previous_policy, changed_variable,
        delta, change_reason, context_unchanged)."""
        if not decision.policy_changed:
            return False, decision.previous_policy, "", 0.0, "", False

        previous = decision.previous_policy
        selected = decision.selected.policy_name

        if trigger_event == "operator_weight_change":
            unchanged = True
            if previous_context is not None:
                deltas = context.normalized_deltas(previous_context)
                unchanged = max(deltas.values()) <= TRIGGER_NOISE_FLOOR
            reason = (
                f"Switched {previous} -> {selected} because the operator "
                "re-weighted priorities"
                + ("; context itself is unchanged" if unchanged else "")
            )
            return True, previous, "operator_weights", 0.0, reason, unchanged

        if previous_context is not None and trigger_event not in ("steady_state", ""):
            if trigger_event == "mission_priority":
                delta = float(
                    MISSION_LEVELS.get(context.mission_priority, 0)
                    - MISSION_LEVELS.get(previous_context.mission_priority, 0)
                )
                reason = (
                    f"Switched {previous} -> {selected} after mission "
                    f"priority became {context.mission_priority}"
                )
                return True, previous, "mission_priority", delta, reason, False
            old = previous_context.numeric_fields().get(trigger_event, 0.0)
            new = context.numeric_fields().get(trigger_event, 0.0)
            reason = (
                f"Switched {previous} -> {selected} after "
                f"{trigger_event} moved {old:.2f} -> {new:.2f}"
            )
            return True, previous, trigger_event, new - old, reason, False

        return True, previous, trigger_event, 0.0, \
            f"Switched {previous} -> {selected}", False
