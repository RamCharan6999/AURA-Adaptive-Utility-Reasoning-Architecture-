"""aura_core_node — the research contribution running in the ROS2 graph.

Wraps the ExplanationEngine (six modular analyzers, exact tradeoff
decomposition — identical code to the tested Python build) as a pure
observer node. It subscribes to what any planner publishes and decomposes
every decision at runtime. It never plans, never filters candidates,
never touches the planner.

Topics:
  subscribes /aura/context/current      (aura_msgs/RobotContext)
  subscribes /aura/decision/current     (aura_msgs/AuraDecision)
  subscribes /aura/weights/current      (aura_msgs/AuraWeights, state)
  subscribes /aura/scenario/reset       (std_msgs/String)
  subscribes /aura/scenario/status      (std_msgs/String)
  subscribes /aura/dashboard/status     (std_msgs/Bool)
  publishes  /aura/explanation/current  (aura_msgs/AuraExplanation)
  publishes  /aura/diagnostics          (aura_msgs/AuraDiagnostics) @ 1 Hz
"""

from __future__ import annotations

import time
from collections import deque
from typing import Optional

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool, String

from aura_msgs.msg import (
    RobotContext as RobotContextMsg,
    AuraDecision as AuraDecisionMsg,
    AuraWeights as AuraWeightsMsg,
    AuraExplanation as AuraExplanationMsg,
    AuraDiagnostics as AuraDiagnosticsMsg,
)

from aura_interfaces.context import RobotContext, QAWeights
from aura_interfaces.ros_convert import (
    context_from_msg,
    weights_from_msg,
    decision_from_msg,
    explanation_to_msg,
)
from aura_core.engine.explanation_engine import ExplanationEngine


class AuraCoreNode(Node):
    """AURA: pure observer, runtime decomposer."""

    def __init__(self) -> None:
        super().__init__("aura_core")
        self.engine = ExplanationEngine()

        self._ctx: Optional[RobotContext] = None
        self.prev_context: Optional[RobotContext] = None
        self.weights: QAWeights = QAWeights(0.5, 0.3, 0.2)
        self.prev_weights: Optional[QAWeights] = None
        self.scenario: str = ""
        self.dashboard_connected: bool = False

        self._decision_times: deque = deque(maxlen=40)
        self._explanation_times: deque = deque(maxlen=40)
        self._last_latency_ms: float = 0.0

        self.create_subscription(RobotContextMsg, "/aura/context/current",
                                 self._on_context, 10)
        self.create_subscription(AuraDecisionMsg, "/aura/decision/current",
                                 self._on_decision, 10)
        self.create_subscription(AuraWeightsMsg, "/aura/weights/current",
                                 self._on_weights, 10)
        self.create_subscription(String, "/aura/scenario/reset",
                                 self._on_reset, 10)
        self.create_subscription(String, "/aura/scenario/status",
                                 self._on_status, 10)
        self.create_subscription(Bool, "/aura/dashboard/status",
                                 self._on_dashboard, 10)

        self.exp_pub = self.create_publisher(
            AuraExplanationMsg, "/aura/explanation/current", 10)
        self.diag_pub = self.create_publisher(
            AuraDiagnosticsMsg, "/aura/diagnostics", 10)
        self.create_timer(1.0, self._publish_diagnostics)

        self.get_logger().info("aura_core up — observing /aura/decision/current")

    # --- state tracking ------------------------------------------------------

    def _on_context(self, msg: RobotContextMsg) -> None:
        self._ctx = context_from_msg(msg)

    def _on_weights(self, msg: AuraWeightsMsg) -> None:
        try:
            self.weights = weights_from_msg(msg)
        except ValueError as error:
            self.get_logger().warn(f"ignoring invalid weights: {error}")

    def _on_reset(self, msg: String) -> None:
        """Scenario (re)start: transition history must not leak across runs."""
        self.prev_context = None
        self.prev_weights = None

    def _on_status(self, msg: String) -> None:
        self.scenario = msg.data

    def _on_dashboard(self, msg: Bool) -> None:
        self.dashboard_connected = bool(msg.data)

    # --- the decision -> explanation cycle -----------------------------------

    def _on_decision(self, msg: AuraDecisionMsg) -> None:
        """One explanation per decision — the runtime loop."""
        if self._ctx is None:
            return
        arrived = time.monotonic()
        self._decision_times.append(arrived)

        decision = decision_from_msg(msg)
        explanation = self.engine.explain(
            decision, self._ctx, self.weights,
            self.prev_context, self.prev_weights)

        out = explanation_to_msg(explanation)
        out.header.stamp = self.get_clock().now().to_msg()
        self.exp_pub.publish(out)
        self._explanation_times.append(time.monotonic())
        self._last_latency_ms = (time.monotonic() - arrived) * 1000.0

        if explanation.policy_changed:
            self.get_logger().info(
                "\n" + explanation.explanation_text)

        self.prev_context = self._ctx
        self.prev_weights = self.weights

    # --- diagnostics --------------------------------------------------------

    @staticmethod
    def _hz(times: deque) -> float:
        if len(times) < 2:
            return 0.0
        span = times[-1] - times[0]
        return (len(times) - 1) / span if span > 0 else 0.0

    def _publish_diagnostics(self) -> None:
        msg = AuraDiagnosticsMsg()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.scenario = self.scenario
        msg.planner_hz = float(self._hz(self._decision_times))
        msg.explanation_hz = float(self._hz(self._explanation_times))
        msg.latency_ms = float(self._last_latency_ms)
        msg.planner_alive = bool(
            self._decision_times
            and time.monotonic() - self._decision_times[-1] < 2.0)
        msg.dashboard_connected = self.dashboard_connected
        self.diag_pub.publish(msg)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = AuraCoreNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
