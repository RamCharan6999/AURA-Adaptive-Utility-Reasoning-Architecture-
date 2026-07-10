"""logger_node — raw explanation records to disk.

CSV for spreadsheets, JSONL for full-fidelity replay. One file pair per
session, timestamp-named, under `log_dir` (default ~/aura_logs).

Subscribes /aura/explanation/current
"""

from __future__ import annotations

import csv
import json
import os
import time

import rclpy
from rclpy.node import Node

from aura_msgs.msg import AuraExplanation as AuraExplanationMsg

CSV_FIELDS = [
    "stamp", "selected_policy", "selected_score", "rejected_policy",
    "rejected_score", "score_gap", "dominant_qa", "dominant_weight",
    "benefit_value", "cost_value", "trigger_event", "conflict_qas",
    "three_way_conflict", "policy_changed", "previous_policy",
    "context_unchanged", "uncertain_decision",
]


class LoggerNode(Node):
    """Appends every explanation to CSV + JSONL."""

    def __init__(self) -> None:
        super().__init__("logger_node")
        self.declare_parameter("log_dir", os.path.expanduser("~/aura_logs"))
        log_dir = os.path.expanduser(str(self.get_parameter("log_dir").value))
        os.makedirs(log_dir, exist_ok=True)
        session = time.strftime("%Y%m%d_%H%M%S")
        self.csv_path = os.path.join(log_dir, f"aura_{session}.csv")
        self.jsonl_path = os.path.join(log_dir, f"aura_{session}.jsonl")

        self._csv_handle = open(self.csv_path, "w", newline="")
        self._writer = csv.DictWriter(self._csv_handle, fieldnames=CSV_FIELDS)
        self._writer.writeheader()
        self._jsonl_handle = open(self.jsonl_path, "w")

        self.create_subscription(AuraExplanationMsg,
                                 "/aura/explanation/current",
                                 self._on_explanation, 10)
        self.get_logger().info(f"logger_node up — writing {self.csv_path}")

    def _on_explanation(self, msg: AuraExplanationMsg) -> None:
        stamp = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
        row = {
            "stamp": round(stamp, 3),
            "selected_policy": msg.selected_policy,
            "selected_score": round(msg.selected_score, 4),
            "rejected_policy": msg.rejected_policy,
            "rejected_score": round(msg.rejected_score, 4),
            "score_gap": round(msg.score_gap, 4),
            "dominant_qa": msg.dominant_qa,
            "dominant_weight": round(msg.dominant_weight, 3),
            "benefit_value": round(msg.benefit_value, 4),
            "cost_value": round(msg.cost_value, 4),
            "trigger_event": msg.trigger_event,
            "conflict_qas": msg.conflict_qas,
            "three_way_conflict": msg.three_way_conflict,
            "policy_changed": msg.policy_changed,
            "previous_policy": msg.previous_policy,
            "context_unchanged": msg.context_unchanged,
            "uncertain_decision": msg.uncertain_decision,
        }
        self._writer.writerow(row)
        self._csv_handle.flush()
        record = dict(row)
        record["explanation_text"] = msg.explanation_text
        record["gap_decomposition"] = json.loads(
            msg.gap_decomposition_json or "{}")
        self._jsonl_handle.write(json.dumps(record) + "\n")
        self._jsonl_handle.flush()

    def destroy_node(self) -> None:
        self._csv_handle.close()
        self._jsonl_handle.close()
        super().destroy_node()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = LoggerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
