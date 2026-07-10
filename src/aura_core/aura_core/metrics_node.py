"""metrics_node — live research statistics over the session.

Separated from the logger on purpose: the logger records raw data, this
node computes running statistics and publishes them as a live topic, so a
researcher can `ros2 topic echo /aura/metrics` and watch the numbers move.

Subscribes /aura/explanation/current, /aura/diagnostics, /aura/scenario/reset
Publishes  /aura/metrics (aura_msgs/AuraMetrics) @ 1 Hz
"""

from __future__ import annotations

import json
from collections import Counter, deque

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from aura_msgs.msg import (
    AuraExplanation as AuraExplanationMsg,
    AuraDiagnostics as AuraDiagnosticsMsg,
    AuraMetrics as AuraMetricsMsg,
)


class MetricsNode(Node):
    """Counts what AURA sees; publishes the running tally."""

    def __init__(self) -> None:
        super().__init__("metrics_node")
        self.declare_parameter("reset_on_scenario", False)
        self._zero()
        self.create_subscription(AuraExplanationMsg,
                                 "/aura/explanation/current",
                                 self._on_explanation, 10)
        self.create_subscription(AuraDiagnosticsMsg, "/aura/diagnostics",
                                 self._on_diagnostics, 10)
        self.create_subscription(String, "/aura/scenario/reset",
                                 self._on_reset, 10)
        self.pub = self.create_publisher(AuraMetricsMsg, "/aura/metrics", 10)
        self.create_timer(1.0, self._publish)
        self.get_logger().info("metrics_node up — /aura/metrics @ 1 Hz")

    def _zero(self) -> None:
        self.total = 0
        self.switches = 0
        self.conflicts = 0
        self.three_way = 0
        self.uncertain = 0
        self.gap_sum = 0.0
        self.policy_counts: Counter = Counter()
        self.latencies: deque = deque(maxlen=200)

    def _on_reset(self, msg: String) -> None:
        if bool(self.get_parameter("reset_on_scenario").value):
            self._zero()

    def _on_explanation(self, msg: AuraExplanationMsg) -> None:
        self.total += 1
        self.gap_sum += msg.score_gap
        self.policy_counts[msg.selected_policy] += 1
        if msg.policy_changed:
            self.switches += 1
        if msg.conflict_detected:
            self.conflicts += 1
        if msg.three_way_conflict:
            self.three_way += 1
        if msg.uncertain_decision:
            self.uncertain += 1

    def _on_diagnostics(self, msg: AuraDiagnosticsMsg) -> None:
        if msg.latency_ms > 0:
            self.latencies.append(msg.latency_ms)

    def _publish(self) -> None:
        out = AuraMetricsMsg()
        out.header.stamp = self.get_clock().now().to_msg()
        out.total_decisions = self.total
        out.policy_switches = self.switches
        out.conflicts_detected = self.conflicts
        out.three_way_conflicts = self.three_way
        out.uncertain_decisions = self.uncertain
        out.avg_latency_ms = float(
            sum(self.latencies) / len(self.latencies)) if self.latencies else 0.0
        out.avg_score_gap = float(
            self.gap_sum / self.total) if self.total else 0.0
        out.policy_frequency_json = json.dumps(dict(self.policy_counts))
        self.pub.publish(out)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = MetricsNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
