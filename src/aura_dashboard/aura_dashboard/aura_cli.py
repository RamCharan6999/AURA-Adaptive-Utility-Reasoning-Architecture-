"""aura_cli — a live, formatted AURA readout in the terminal.

    ros2 run aura_dashboard aura_cli

Repaints on every explanation: policy, trigger, conflict, exact tradeoff,
a confidence bar, plus the live metrics line. `ros2 topic echo` shows raw
messages; this shows the middleware thinking.
"""

from __future__ import annotations

import json
import sys

import rclpy
from rclpy.node import Node

from aura_msgs.msg import (
    AuraExplanation as AuraExplanationMsg,
    AuraMetrics as AuraMetricsMsg,
    AuraDiagnostics as AuraDiagnosticsMsg,
)

# ANSI palette (keyed to the operator console colors).
RESET, DIM, BOLD = "\x1b[0m", "\x1b[2m", "\x1b[1m"
POLICY_COLOR = {
    "FAST_DELIVERY": "\x1b[33m",      # amber
    "SAFE_MODE": "\x1b[36m",          # teal
    "ENERGY_SAVE": "\x1b[32m",        # green
    "EMERGENCY_RUSH": "\x1b[31m",     # red
    "CAUTIOUS_EXPLORE": "\x1b[34m",   # blue
}
QA_ARROWS = {"safety": "safety", "time": "time", "energy": "energy"}
BAR = "\u2501" * 46


def gauge(value: float, width: int = 10) -> str:
    """A small unicode bar for 0..1 values."""
    filled = max(0, min(width, round(value * width)))
    return "\u2593" * filled + "\u2591" * (width - filled)


class AuraCli(Node):
    """Subscribes and repaints the terminal on every explanation."""

    def __init__(self) -> None:
        super().__init__("aura_cli")
        self.metrics: AuraMetricsMsg | None = None
        self.diag: AuraDiagnosticsMsg | None = None
        self.create_subscription(AuraExplanationMsg,
                                 "/aura/explanation/current",
                                 self._on_explanation, 10)
        self.create_subscription(AuraMetricsMsg, "/aura/metrics",
                                 self._on_metrics, 10)
        self.create_subscription(AuraDiagnosticsMsg, "/aura/diagnostics",
                                 self._on_diag, 10)
        print("aura_cli — waiting for /aura/explanation/current ...")

    def _on_metrics(self, msg: AuraMetricsMsg) -> None:
        self.metrics = msg

    def _on_diag(self, msg: AuraDiagnosticsMsg) -> None:
        self.diag = msg

    def _on_explanation(self, exp: AuraExplanationMsg) -> None:
        color = POLICY_COLOR.get(exp.selected_policy, "")
        decomp = json.loads(exp.gap_decomposition_json or "{}")
        _up, _dn = "\u2191", "\u2193"
        trade = "   ".join(
            f"{qa} {_up if v >= 0 else _dn} {v:+.3f}"
            for qa, v in sorted(decomp.items(), key=lambda kv: -kv[1]))
        scenario = self.diag.scenario if self.diag else ""

        lines = [
            "\x1b[2J\x1b[H",   # clear + home
            f"{BOLD}{BAR}{RESET}",
            f"{BOLD}AURA{RESET}   {DIM}{scenario}{RESET}",
            f"{BOLD}{BAR}{RESET}",
            f"Policy       {color}{BOLD}{exp.selected_policy}{RESET}"
            + (f"   {DIM}(was {exp.previous_policy}){RESET}"
               if exp.policy_changed else ""),
            f"Trigger      {exp.trigger_description or exp.trigger_event}",
            f"Conflict     "
            + (f"{exp.conflict_qas}"
               + ("  [THREE-WAY]" if exp.three_way_conflict else "")
               if exp.conflict_detected else "none"),
            f"Dominant     {exp.dominant_qa}  (w={exp.dominant_weight:.2f})",
            f"Tradeoff     {trade}",
            f"Rejected     {exp.rejected_policy}  "
            f"{DIM}{exp.rejected_score:.3f} vs {exp.selected_score:.3f}{RESET}",
            f"Gap          {exp.score_gap:.3f}  {gauge(min(1.0, exp.score_gap / 0.3))}  "
            + ("\x1b[33mUNCERTAIN\x1b[0m" if exp.uncertain_decision else "certain"),
            f"Confidence   {exp.confidence * 100:.0f}%",
        ]
        if exp.context_unchanged:
            lines.append(f"\x1b[33mNOTE         context unchanged — "
                         f"operator accepted this tradeoff{RESET}")
        lines.append(f"{BOLD}{BAR}{RESET}")
        if self.metrics:
            m = self.metrics
            lines.append(
                f"{DIM}decisions {m.total_decisions}  switches {m.policy_switches}  "
                f"conflicts {m.conflicts_detected}  uncertain {m.uncertain_decisions}  "
                f"latency {m.avg_latency_ms:.1f}ms{RESET}")
        sys.stdout.write("\n".join(lines) + "\n")
        sys.stdout.flush()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = AuraCli()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
