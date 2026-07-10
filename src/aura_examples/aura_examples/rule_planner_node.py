"""rule_planner_node — proof that AURA is planner-agnostic.

A deliberately simple if/else planner. It knows nothing about utilities;
it just ranks policies by hand-written rules and publishes the same
PolicyEvidence contract. AURA explains it without a single change.

Try it:
  ros2 launch aura_bringup demo.launch.py planner:=rule

~60 lines of logic on top of AuraBasePlanner — that is the middleware
claim, demonstrated.
"""

from __future__ import annotations

from typing import List

import rclpy
from std_msgs.msg import String

from aura_interfaces.base_planner import AuraBasePlanner
from aura_interfaces.context import RobotContext, QAWeights
from aura_interfaces.evidence import PolicyEvidence


# Priority-ordered rules: first matching rule's ranking wins.
# Each ranking lists policies best-first; scores are assigned 1.0 -> 0.2.
RULES = [
    ("emergency mission",
     lambda c: c.mission_priority == "emergency",
     ["EMERGENCY_RUSH", "FAST_DELIVERY", "SAFE_MODE",
      "ENERGY_SAVE", "CAUTIOUS_EXPLORE"]),
    ("human close",
     lambda c: c.human_proximity < 2.0,
     ["SAFE_MODE", "CAUTIOUS_EXPLORE", "ENERGY_SAVE", "FAST_DELIVERY"]),
    ("localization degraded",
     lambda c: c.localization_confidence < 0.5,
     ["CAUTIOUS_EXPLORE", "SAFE_MODE", "ENERGY_SAVE", "FAST_DELIVERY"]),
    ("battery critical",
     lambda c: c.battery_level < 0.2,
     ["ENERGY_SAVE", "SAFE_MODE", "CAUTIOUS_EXPLORE", "FAST_DELIVERY"]),
    ("default",
     lambda c: True,
     ["FAST_DELIVERY", "SAFE_MODE", "ENERGY_SAVE", "CAUTIOUS_EXPLORE"]),
]

# Crude per-policy QA profiles so AURA's decomposition has attributes to
# read. A rule planner has no utilities; these are its published beliefs.
QA_PROFILE = {
    "FAST_DELIVERY":    {"safety": 0.4, "time": 0.95, "energy": 0.5},
    "SAFE_MODE":        {"safety": 0.95, "time": 0.6, "energy": 0.7},
    "ENERGY_SAVE":      {"safety": 0.7, "time": 0.5, "energy": 0.95},
    "EMERGENCY_RUSH":   {"safety": 0.2, "time": 1.0, "energy": 0.3},
    "CAUTIOUS_EXPLORE": {"safety": 0.98, "time": 0.3, "energy": 0.8},
}


class RulePlannerNode(AuraBasePlanner):
    """If/else planner behind the exact same AURA contract."""

    evidence_type = "rule"

    def __init__(self) -> None:
        super().__init__("rule_planner")
        self.create_subscription(String, "/aura/scenario/reset",
                                 lambda m: self.reset(), 10)

    def score_candidates(self, context: RobotContext,
                         weights: QAWeights) -> List[PolicyEvidence]:
        rule_name, ranking = next(
            (name, order) for name, cond, order in RULES if cond(context))
        evidence: List[PolicyEvidence] = []
        for rank, policy in enumerate(ranking):
            score = 1.0 - 0.2 * rank
            evidence.append(PolicyEvidence(
                policy_name=policy,
                evidence_type=self.evidence_type,
                score=score,
                confidence=0.9,
                attributes=QA_PROFILE[policy],
                raw_evidence={"rule": rule_name, "rank": rank + 1},
            ))
        return evidence


def main(args=None) -> None:
    rclpy.init(args=args)
    node = RulePlannerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
