"""utility_planner_node — the reference planner as an AURA-compatible node.

Demo scaffolding, not the research contribution. It inherits everything
from aura_interfaces.AuraBasePlanner (subscriptions, weight parameters,
publishing) and implements exactly one method — which is the point: any
planner is ~50 lines on top of the contract (see aura_examples for a
rule-based one).

Subscribes /aura/context/current, /aura/weights, /aura/scenario/reset.
Publishes  /aura/decision/current, /aura/weights/current.
Parameters w_safety / w_time / w_energy (ros2 param set works live).
"""

from __future__ import annotations

from typing import List

import rclpy
from std_msgs.msg import String

from aura_interfaces.base_planner import AuraBasePlanner
from aura_interfaces.context import RobotContext, QAWeights
from aura_interfaces.evidence import PolicyEvidence
from aura_core.engine.policy import DEFAULT_POLICIES
from aura_core.engine.scoring import score_all_candidates


class UtilityPlannerNode(AuraBasePlanner):
    """Weighted-utility planner over the five candidate policies."""

    evidence_type = "utility"

    def __init__(self) -> None:
        super().__init__("utility_planner")
        self.policies = DEFAULT_POLICIES
        self.create_subscription(String, "/aura/scenario/reset",
                                 self._on_reset, 10)
        # Publish the initial weight state once so downstream nodes
        # (aura_core, console) know the starting weights.
        self._boot_timer = self.create_timer(0.5, self._announce_weights_once)

    def _announce_weights_once(self) -> None:
        self._publish_weight_state(self.weights())
        self._boot_timer.cancel()

    def _on_reset(self, msg: String) -> None:
        """Scenario (re)start: forget the previous selection."""
        self.reset()
        self.get_logger().info(f"reset for scenario {msg.data}")

    def score_candidates(self, context: RobotContext,
                         weights: QAWeights) -> List[PolicyEvidence]:
        """Score every eligible policy (calibrations C1-C3 in the engine)."""
        return score_all_candidates(self.policies, context, weights,
                                    evidence_type=self.evidence_type)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = UtilityPlannerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
