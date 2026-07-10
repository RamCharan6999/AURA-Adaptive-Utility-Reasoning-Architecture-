"""AuraBasePlanner — the planner side of the AURA middleware contract, as a
ready-to-subclass ROS2 node.

Any planner that inherits this and implements one method,
``score_candidates()``, automatically:

  * subscribes to  /aura/context/current   (RobotContext)
  * subscribes to  /aura/weights           (command channel)
  * exposes        w_safety / w_time / w_energy as ROS parameters
                   (``ros2 param set`` works; topic and params converge)
  * publishes to   /aura/decision/current  (AuraDecision)
  * publishes to   /aura/weights/current   (current weight state, latched-ish)

This is what makes AURA planner-agnostic: a rule-based, RL, or LLM planner
is ~50 lines on top of this class (see aura_examples).
"""

from __future__ import annotations

from abc import abstractmethod
from typing import List

import rclpy
from rclpy.node import Node
from rcl_interfaces.msg import SetParametersResult

from aura_msgs.msg import RobotContext as RobotContextMsg
from aura_msgs.msg import AuraWeights as AuraWeightsMsg
from aura_msgs.msg import AuraDecision as AuraDecisionMsg

from aura_interfaces.context import RobotContext, QAWeights
from aura_interfaces.evidence import PolicyEvidence, AuraDecision
from aura_interfaces.ros_convert import (
    context_from_msg,
    weights_from_msg,
    weights_to_msg,
    decision_to_msg,
)


class AuraBasePlanner(Node):
    """Subclass and implement score_candidates(); everything else is wired."""

    evidence_type: str = "generic"

    def __init__(self, node_name: str) -> None:
        super().__init__(node_name)

        # --- weights: parameters are the source of truth ------------------
        self.declare_parameter("w_safety", 0.5)
        self.declare_parameter("w_time", 0.3)
        self.declare_parameter("w_energy", 0.2)
        self._syncing = False          # guard against param<->topic loops
        self.add_on_set_parameters_callback(self._on_params)

        # --- wiring ---------------------------------------------------------
        self.create_subscription(
            RobotContextMsg, "/aura/context/current", self._on_context, 10)
        self.create_subscription(
            AuraWeightsMsg, "/aura/weights", self._on_weights_cmd, 10)
        self._decision_pub = self.create_publisher(
            AuraDecisionMsg, "/aura/decision/current", 10)
        self._weights_state_pub = self.create_publisher(
            AuraWeightsMsg, "/aura/weights/current", 10)

        self._last_selected: str = ""
        self.get_logger().info(
            f"{node_name} up — weights "
            f"{self.weights().w_safety:.2f}/{self.weights().w_time:.2f}/"
            f"{self.weights().w_energy:.2f}")

    # --- the one method a planner implements ------------------------------

    @abstractmethod
    def score_candidates(self, context: RobotContext,
                         weights: QAWeights) -> List[PolicyEvidence]:
        """Score every eligible candidate policy for this context."""

    # --- weights handling ----------------------------------------------------

    def weights(self) -> QAWeights:
        """Current weights from the parameter server (validated)."""
        w = (self.get_parameter("w_safety").value,
             self.get_parameter("w_time").value,
             self.get_parameter("w_energy").value)
        try:
            return QAWeights(*[round(float(x), 4) for x in w])
        except ValueError:
            # Params can be transiently inconsistent mid-update; renormalise.
            total = sum(w) or 1.0
            return QAWeights(*[round(float(x) / total, 4) for x in w])

    def _on_params(self, params) -> SetParametersResult:
        """Accept weight changes; renormalise so the trio sums to 1.0.

        This makes single-parameter operator commands work naturally:
        `ros2 param set /utility_planner w_safety 0.2` is accepted and the
        other two weights scale proportionally to keep the sum at 1.0.
        """
        touched = [p for p in params
                   if p.name in ("w_safety", "w_time", "w_energy")]
        for p in touched:
            if not isinstance(p.value, (int, float)) or not 0.0 <= p.value <= 1.0:
                return SetParametersResult(
                    successful=False,
                    reason=f"{p.name} must be a number in [0, 1]")
        if touched and not self._syncing:
            # Defer renormalisation until after this set is applied.
            self._renorm_timer = self.create_timer(0.05, self._renormalise)
        return SetParametersResult(successful=True)

    def _renormalise(self) -> None:
        """One-shot: scale the weight trio back to sum 1.0 and publish."""
        self._renorm_timer.cancel()
        names = ("w_safety", "w_time", "w_energy")
        values = [float(self.get_parameter(n).value) for n in names]
        total = sum(values)
        if total <= 0:
            values = [0.5, 0.3, 0.2]
        elif abs(total - 1.0) > 1e-6:
            values = [v / total for v in values]
        # Round two, derive the third — guarantees an exact 1.0 sum.
        values = [round(values[0], 4), round(values[1], 4), 0.0]
        values[2] = round(1.0 - values[0] - values[1], 4)
        self._syncing = True
        try:
            self.set_parameters([
                rclpy.parameter.Parameter(n, value=round(v, 4))
                for n, v in zip(names, values)])
        finally:
            self._syncing = False
        w = QAWeights(*[round(v, 4) for v in values])
        self._publish_weight_state(w)
        self.get_logger().info(
            f"weights = {w.w_safety:.2f}/{w.w_time:.2f}/{w.w_energy:.2f}")

    def _on_weights_cmd(self, msg: AuraWeightsMsg) -> None:
        """Weight command from the topic (console sliders, scenario S5, CLI)."""
        try:
            w = weights_from_msg(msg)
        except ValueError as error:
            self.get_logger().warn(f"rejected weights: {error}")
            return
        self._syncing = True
        try:
            self.set_parameters([
                rclpy.parameter.Parameter("w_safety", value=float(w.w_safety)),
                rclpy.parameter.Parameter("w_time", value=float(w.w_time)),
                rclpy.parameter.Parameter("w_energy", value=float(w.w_energy)),
            ])
        finally:
            self._syncing = False
        self._publish_weight_state(w)
        self.get_logger().info(
            f"weights <- {w.w_safety:.2f}/{w.w_time:.2f}/{w.w_energy:.2f}")

    def _publish_weight_state(self, w: QAWeights) -> None:
        msg = weights_to_msg(w)
        msg.header.stamp = self.get_clock().now().to_msg()
        self._weights_state_pub.publish(msg)

    # --- decision cycle ---------------------------------------------------

    def _on_context(self, msg: RobotContextMsg) -> None:
        """One decision per context tick: score, rank, publish."""
        context = context_from_msg(msg)
        weights = self.weights()
        candidates = self.score_candidates(context, weights)
        if not candidates:
            self.get_logger().warn("no eligible candidates")
            return
        ranked = sorted(candidates, key=lambda ev: ev.score, reverse=True)
        decision = AuraDecision(
            selected=ranked[0],
            alternatives=ranked[1:],
            policy_changed=(self._last_selected != ""
                            and self._last_selected != ranked[0].policy_name),
            previous_policy=self._last_selected,
        )
        self._last_selected = ranked[0].policy_name

        out = decision_to_msg(decision)
        out.header.stamp = msg.header.stamp   # carry the context stamp
        self._decision_pub.publish(out)

    def reset(self) -> None:
        """Forget the previous selection (e.g. on scenario change)."""
        self._last_selected = ""
