"""Trigger analysis — answers question 1: *what happened?*

Compares the current cycle's context and operator weights against the
previous cycle's, and names the single most salient change. Operator
interventions always outrank sensor drift: a human acting is the most
important thing that can happen in a human-in-the-loop system.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from aura_interfaces.context import (
    RobotContext,
    QAWeights,
    CONTEXT_UNITS,
    MISSION_LEVELS,
)

# A normalised context delta below this is treated as noise, not a trigger.
TRIGGER_NOISE_FLOOR: float = 0.01

# Decision-relevant thresholds in the reference planner's scoring. AURA
# uses these only to say *which line was crossed* — it never scores.
CONTEXT_THRESHOLDS: Dict[str, List[float]] = {
    "battery_level": [0.2, 0.4],
    "human_proximity": [1.0, 2.0],
    "obstacle_density": [0.6],
    "localization_confidence": [0.5],
}

QA_NAMES: Tuple[str, str, str] = ("safety", "time", "energy")


class TriggerAnalyzer:
    """Detects the most significant change since the previous cycle."""

    def analyze(
        self,
        context: RobotContext,
        previous_context: Optional[RobotContext],
        weights: QAWeights,
        previous_weights: Optional[QAWeights],
    ) -> Tuple[str, float, str, str]:
        """Return (trigger_event, trigger_value, trigger_unit, description).

        Priority order:
          1. Operator weight change (a human acted — always report it).
          2. Context variable with the largest normalised delta.
          3. Steady state (nothing moved beyond the noise floor).
        """
        # 1 — operator intervention beats sensor drift in salience.
        if weights.changed_from(previous_weights):
            deltas = {
                qa: weights.as_dict()[qa] - previous_weights.as_dict()[qa]
                for qa in QA_NAMES
            }
            biggest = max(deltas, key=lambda qa: abs(deltas[qa]))
            desc = ", ".join(
                f"w_{qa}: {previous_weights.as_dict()[qa]:.2f} -> "
                f"{weights.as_dict()[qa]:.2f}"
                for qa in QA_NAMES
                if abs(deltas[qa]) > 1e-9
            )
            return (
                "operator_weight_change",
                deltas[biggest],
                "weight",
                f"Operator changed preferences ({desc})",
            )

        # 2 — largest normalised context change.
        if previous_context is not None:
            deltas = context.normalized_deltas(previous_context)
            variable = max(deltas, key=lambda name: deltas[name])
            if deltas[variable] > TRIGGER_NOISE_FLOOR:
                if variable == "mission_priority":
                    return (
                        "mission_priority",
                        float(MISSION_LEVELS.get(context.mission_priority, 0)),
                        "level",
                        f"Mission priority changed: "
                        f"{previous_context.mission_priority} -> "
                        f"{context.mission_priority}",
                    )
                old = previous_context.numeric_fields()[variable]
                new = context.numeric_fields()[variable]
                desc = f"{variable}: {old:.2f} -> {new:.2f}"
                crossed = self.crossed_threshold(variable, old, new)
                if crossed is not None:
                    desc += f" (crossed decision threshold {crossed:g})"
                return (variable, new, CONTEXT_UNITS.get(variable, ""), desc)

        # 3 — nothing notable changed.
        return ("steady_state", 0.0, "", "No significant context change")

    @staticmethod
    def crossed_threshold(variable: str, old: float, new: float) -> Optional[float]:
        """Return the decision threshold crossed between old and new, if any."""
        for threshold in CONTEXT_THRESHOLDS.get(variable, []):
            lo, hi = min(old, new), max(old, new)
            if lo < threshold <= hi or lo <= threshold < hi:
                return threshold
        return None
