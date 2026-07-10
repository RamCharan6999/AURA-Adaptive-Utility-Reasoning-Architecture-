"""Reference utility-function planner.

This is NOT the research contribution — it is demo scaffolding that gives
AURA something to explain. The scoring follows the AURA master context
document, with three documented calibrations (see CALIBRATION_NOTES.md):

C1. EMERGENCY_RUSH is only eligible when mission_priority == 'emergency'.
C2. Policies flagged ``emergency_override`` receive an extra urgency
    credit on their time score under an emergency.
C3. Low localization confidence adds a speed-scaled safety penalty that
    ``localization_replan`` policies are immune to.
"""

from __future__ import annotations

from typing import Dict, List

from aura_interfaces.context import RobotContext, QAWeights
from aura_core.engine.policy import Policy, DEFAULT_POLICIES
from aura_interfaces.evidence import PolicyEvidence


# --- Calibration constants (C2, C3) -------------------------------------

# Extra urgency credit for emergency_override policies when the mission is
# an emergency. Modeled uncapped on purpose: an emergency response policy
# is allowed to "overshoot" the nominal time scale — that IS the override.
EMERGENCY_OVERRIDE_BONUS: float = 0.35

# Localization safety penalty: below this confidence the robot's pose is
# unreliable and moving fast becomes dangerous. Penalty scales with speed
# because a fast robot with a wrong pose estimate is the real hazard.
LOCALIZATION_DANGER_THRESHOLD: float = 0.5
LOCALIZATION_PENALTY_GAIN: float = 4.0


def safety_score(policy: Policy, context: RobotContext) -> float:
    """Safety QA score, 0.0 - 1.0. Per spec, plus localization term (C3)."""
    danger = 0.0
    if context.human_proximity < 1.0:
        danger += 0.7
    elif context.human_proximity < 2.0:
        danger += 0.3
    if context.obstacle_density > 0.6:
        danger += 0.3
    base = max(0.0, 1.0 - (danger * (1.0 - policy.safety_tolerance)))

    # C3 — pose-uncertainty penalty, immune for replanning policies.
    loc_penalty = 0.0
    if (
        context.localization_confidence < LOCALIZATION_DANGER_THRESHOLD
        and not policy.localization_replan
    ):
        loc_penalty = (
            (LOCALIZATION_DANGER_THRESHOLD - context.localization_confidence)
            * policy.base_speed
            * LOCALIZATION_PENALTY_GAIN
        )
    return max(0.0, base - loc_penalty)


def time_score(policy: Policy, context: RobotContext) -> float:
    """Time QA score. Per spec: speed + mission bonus, capped at 1.0.

    C2: emergency_override policies add EMERGENCY_OVERRIDE_BONUS on top of
    the cap during an emergency, so the purpose-built emergency policy can
    out-score a merely fast one that also hits the cap.
    """
    if context.mission_priority == "emergency":
        bonus = 0.3
    elif context.mission_priority == "urgent":
        bonus = 0.15
    else:
        bonus = 0.0
    score = min(1.0, policy.base_speed + bonus)
    if policy.emergency_override and context.mission_priority == "emergency":
        score += EMERGENCY_OVERRIDE_BONUS
    return score


def energy_score(policy: Policy, context: RobotContext) -> float:
    """Energy QA score, 0.0 - 1.0. Exactly per spec."""
    consumption = policy.power_consumption
    battery = context.battery_level
    if battery < 0.2:
        penalty = consumption * 0.9
    elif battery < 0.4:
        penalty = consumption * 0.5
    else:
        penalty = consumption * 0.1
    return max(0.0, 1.0 - penalty)


def qa_scores(policy: Policy, context: RobotContext) -> Dict[str, float]:
    """All three QA scores for one policy in one context."""
    return {
        "safety": safety_score(policy, context),
        "time": time_score(policy, context),
        "energy": energy_score(policy, context),
    }


def compute_utility(
    policy: Policy, context: RobotContext, weights: QAWeights
) -> float:
    """Weighted utility = w_safety*s + w_time*t + w_energy*e (per spec)."""
    scores = qa_scores(policy, context)
    return (
        weights.w_safety * scores["safety"]
        + weights.w_time * scores["time"]
        + weights.w_energy * scores["energy"]
    )


def score_all_candidates(policies: List[Policy], context: RobotContext,
                         weights: QAWeights,
                         evidence_type: str = "utility") -> List[PolicyEvidence]:
    """Score every eligible policy; used by the ROS planner node.

    C1 — emergency_only policies require an emergency mission.
    """
    evidence: List[PolicyEvidence] = []
    eligible = [p for p in policies
                if not p.emergency_only
                or context.mission_priority == "emergency"]
    for policy in eligible:
        scores = qa_scores(policy, context)
        utility = (weights.w_safety * scores["safety"]
                   + weights.w_time * scores["time"]
                   + weights.w_energy * scores["energy"])
        evidence.append(PolicyEvidence(
            policy_name=policy.name,
            evidence_type=evidence_type,
            score=utility,
            confidence=min(1.0, 0.5 + utility / 2.0),
            attributes=scores,
            raw_evidence={
                "base_speed": policy.base_speed,
                "power_consumption": policy.power_consumption,
                "safety_tolerance": policy.safety_tolerance,
            },
        ))
    return evidence
