"""Converters between aura_msgs ROS messages and the plain dataclasses.

Nodes speak ROS messages on the wire; the engine speaks dataclasses. These
converters are the only place the two meet, so the engine stays free of
rclpy and remains unit-testable without a ROS installation.
"""

from __future__ import annotations

import json
from typing import Optional

from aura_msgs.msg import (
    RobotContext as RobotContextMsg,
    AuraWeights as AuraWeightsMsg,
    PolicyEvidence as PolicyEvidenceMsg,
    AuraDecision as AuraDecisionMsg,
    AuraExplanation as AuraExplanationMsg,
)

from aura_interfaces.context import RobotContext, QAWeights
from aura_interfaces.evidence import PolicyEvidence, AuraDecision


# --- context ---------------------------------------------------------------

def context_from_msg(msg: RobotContextMsg, timestamp: float = 0.0) -> RobotContext:
    """RobotContext.msg -> RobotContext dataclass."""
    stamp = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
    return RobotContext(
        battery_level=float(msg.battery_level),
        human_proximity=float(msg.human_proximity),
        obstacle_density=float(msg.obstacle_density),
        localization_confidence=float(msg.localization_confidence),
        mission_priority=msg.mission_priority,
        sensor_health=float(msg.sensor_health),
        timestamp=timestamp or stamp,
    )


def context_to_msg(ctx: RobotContext, msg: Optional[RobotContextMsg] = None
                   ) -> RobotContextMsg:
    """RobotContext dataclass -> RobotContext.msg (header stamped by caller)."""
    msg = msg or RobotContextMsg()
    msg.battery_level = float(ctx.battery_level)
    msg.human_proximity = float(ctx.human_proximity)
    msg.obstacle_density = float(ctx.obstacle_density)
    msg.localization_confidence = float(ctx.localization_confidence)
    msg.mission_priority = ctx.mission_priority
    msg.sensor_health = float(ctx.sensor_health)
    return msg


# --- weights ---------------------------------------------------------------

def weights_from_msg(msg: AuraWeightsMsg) -> QAWeights:
    """AuraWeights.msg -> QAWeights (raises ValueError if sum != 1)."""
    return QAWeights(round(float(msg.w_safety), 4),
                     round(float(msg.w_time), 4),
                     round(float(msg.w_energy), 4))


def weights_to_msg(w: QAWeights, msg: Optional[AuraWeightsMsg] = None
                   ) -> AuraWeightsMsg:
    """QAWeights -> AuraWeights.msg."""
    msg = msg or AuraWeightsMsg()
    msg.w_safety, msg.w_time, msg.w_energy = (
        float(w.w_safety), float(w.w_time), float(w.w_energy))
    return msg


# --- evidence / decision -----------------------------------------------------

def evidence_to_msg(ev: PolicyEvidence) -> PolicyEvidenceMsg:
    """PolicyEvidence dataclass -> PolicyEvidence.msg."""
    msg = PolicyEvidenceMsg()
    msg.policy_name = ev.policy_name
    msg.evidence_type = ev.evidence_type
    msg.score = float(ev.score)
    msg.confidence = float(ev.confidence)
    msg.attributes_json = json.dumps(ev.attributes)
    msg.raw_evidence_json = json.dumps(ev.raw_evidence)
    return msg


def evidence_from_msg(msg: PolicyEvidenceMsg) -> PolicyEvidence:
    """PolicyEvidence.msg -> PolicyEvidence dataclass."""
    return PolicyEvidence(
        policy_name=msg.policy_name,
        evidence_type=msg.evidence_type,
        score=float(msg.score),
        confidence=float(msg.confidence),
        attributes=json.loads(msg.attributes_json or "{}"),
        raw_evidence=json.loads(msg.raw_evidence_json or "{}"),
    )


def decision_to_msg(decision: AuraDecision) -> AuraDecisionMsg:
    """AuraDecision dataclass -> AuraDecision.msg (header stamped by caller)."""
    msg = AuraDecisionMsg()
    msg.selected = evidence_to_msg(decision.selected)
    msg.alternatives = [evidence_to_msg(a) for a in decision.alternatives]
    msg.policy_changed = bool(decision.policy_changed)
    msg.previous_policy = decision.previous_policy
    return msg


def decision_from_msg(msg: AuraDecisionMsg) -> AuraDecision:
    """AuraDecision.msg -> AuraDecision dataclass."""
    stamp = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
    return AuraDecision(
        selected=evidence_from_msg(msg.selected),
        alternatives=[evidence_from_msg(a) for a in msg.alternatives],
        policy_changed=bool(msg.policy_changed),
        previous_policy=msg.previous_policy,
        timestamp=stamp,
    )


# --- explanation -------------------------------------------------------------

def explanation_to_msg(exp) -> AuraExplanationMsg:
    """AuraExplanation dataclass -> AuraExplanation.msg."""
    msg = AuraExplanationMsg()
    msg.trigger_event = exp.trigger_event
    msg.trigger_value = float(exp.trigger_value)
    msg.trigger_unit = exp.trigger_unit
    msg.trigger_description = exp.trigger_description
    msg.conflict_detected = bool(exp.conflict_detected)
    msg.conflict_qas = exp.conflict_qas
    msg.conflict_description = exp.conflict_description
    msg.three_way_conflict = bool(exp.three_way_conflict)
    msg.selected_policy = exp.selected_policy
    msg.selected_score = float(exp.selected_score)
    msg.confidence = float(exp.confidence)
    msg.dominant_qa = exp.dominant_qa
    msg.dominant_weight = float(exp.dominant_weight)
    msg.dominant_reason = exp.dominant_reason
    msg.benefit_value = float(exp.benefit_value)
    msg.benefit_description = exp.benefit_description
    msg.cost_value = float(exp.cost_value)
    msg.cost_description = exp.cost_description
    msg.gap_decomposition_json = json.dumps(exp.gap_decomposition)
    msg.rejected_policy = exp.rejected_policy
    msg.rejected_score = float(exp.rejected_score)
    msg.score_gap = float(exp.score_gap)
    msg.rejection_reason = exp.rejection_reason
    msg.uncertain_decision = bool(exp.uncertain_decision)
    msg.policy_changed = bool(exp.policy_changed)
    msg.previous_policy = exp.previous_policy
    msg.changed_context_variable = exp.changed_context_variable
    msg.changed_context_delta = float(exp.changed_context_delta)
    msg.change_reason = exp.change_reason
    msg.context_unchanged = bool(exp.context_unchanged)
    msg.explanation_text = exp.explanation_text
    return msg
