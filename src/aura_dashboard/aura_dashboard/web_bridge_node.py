"""web_bridge_node — ROS2 <-> WebSocket bridge for the operator console.

Uses aura_dashboard.ws_server (pure standard library, RFC 6455) instead
of the python3-websockets package. Ubuntu 22.04's websockets 9.1 passes
``loop=`` kwargs that Python 3.10 removed, so the old asyncio-based
bridge could die at startup inside its background thread — the browser
then showed "connecting…" forever and no ticks reached the console.
This bridge has no asyncio and no third-party dependency: broadcasts
are plain locked socket writes made directly from ROS callbacks.

On every new console connection the bridge pushes a snapshot (current
scenario, weights, last tick) so the page paints immediately instead of
waiting for the next explanation cycle.
"""

from __future__ import annotations

import http.server
import json
import os
import socketserver
import threading
from functools import partial

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool, String
from ament_index_python.packages import get_package_share_directory

from aura_msgs.msg import (
    RobotContext as RobotContextMsg,
    AuraDecision as AuraDecisionMsg,
    AuraExplanation as AuraExplanationMsg,
    AuraWeights as AuraWeightsMsg,
    AuraMetrics as AuraMetricsMsg,
    AuraDiagnostics as AuraDiagnosticsMsg,
)

from aura_dashboard.ws_server import WebSocketServer


class WebBridgeNode(Node):
    """Bridges AURA ROS2 topics to the operator console."""

    def __init__(self) -> None:
        super().__init__("web_bridge")
        self.declare_parameter("http_port", 8080)
        self.declare_parameter("ws_port", 9090)

        self._last_context = None
        self._last_decision = None
        self._last_tick = None          # full last tick payload (JSON str)
        self._last_weights = None       # last weights payload (JSON str)
        self._scenario = ""
        self._state_lock = threading.Lock()

        self.create_subscription(RobotContextMsg, "/aura/context/current",
                                 self._on_context, 10)
        self.create_subscription(AuraDecisionMsg, "/aura/decision/current",
                                 self._on_decision, 10)
        self.create_subscription(AuraExplanationMsg,
                                 "/aura/explanation/current",
                                 self._on_explanation, 10)
        self.create_subscription(AuraWeightsMsg, "/aura/weights/current",
                                 self._on_weights_state, 10)
        self.create_subscription(AuraMetricsMsg, "/aura/metrics",
                                 self._on_metrics, 10)
        self.create_subscription(AuraDiagnosticsMsg, "/aura/diagnostics",
                                 self._on_diagnostics, 10)
        self.create_subscription(String, "/aura/scenario/status",
                                 self._on_status, 10)
        self.create_subscription(String, "/aura/scenario/reset",
                                 self._on_reset, 10)

        self._weights_pub = self.create_publisher(
            AuraWeightsMsg, "/aura/weights", 10)
        self._select_pub = self.create_publisher(
            String, "/aura/scenario/select", 10)
        self._status_pub = self.create_publisher(
            Bool, "/aura/dashboard/status", 10)
        self.create_timer(1.0, self._publish_status)

        ws_port = int(self.get_parameter("ws_port").value)
        self._ws = WebSocketServer(
            "0.0.0.0", ws_port,
            on_message=self.handle_inbound,
            on_connect=self._on_console_connect,
            log=lambda s: self.get_logger().info(s))
        self._ws.start()   # raises loudly if the port is taken

        http_port = int(self.get_parameter("http_port").value)
        self.get_logger().info(
            f"web_bridge up — operator console: http://localhost:{http_port}")

    # -- outbound ------------------------------------------------------------

    def _send(self, payload: dict) -> None:
        self._ws.broadcast(json.dumps(payload))

    def _on_console_connect(self, send) -> None:
        """Push current state to a console that just connected."""
        with self._state_lock:
            scenario, weights, tick = (self._scenario, self._last_weights,
                                       self._last_tick)
        if scenario:
            send(json.dumps({"type": "reset",
                             "scenario": scenario.split(" ")[0]}))
        if weights:
            send(weights)
        if tick:
            send(tick)

    def _on_context(self, msg: RobotContextMsg) -> None:
        self._last_context = {
            "battery_level": round(msg.battery_level, 4),
            "human_proximity": round(msg.human_proximity, 4),
            "obstacle_density": round(msg.obstacle_density, 4),
            "localization_confidence": round(msg.localization_confidence, 4),
            "mission_priority": msg.mission_priority,
        }

    def _on_decision(self, msg: AuraDecisionMsg) -> None:
        def ev(e):
            return {"name": e.policy_name, "score": round(e.score, 4),
                    "qa": json.loads(e.attributes_json or "{}")}
        self._last_decision = {
            "selected": ev(msg.selected),
            "alternatives": [ev(a) for a in msg.alternatives],
            "policy_changed": msg.policy_changed,
            "previous_policy": msg.previous_policy,
        }

    def _on_explanation(self, msg: AuraExplanationMsg) -> None:
        payload = {
            "type": "tick",
            "scenario": self._scenario,
            "context": self._last_context,
            "decision": self._last_decision,
            "explanation": {
                "text": msg.explanation_text,
                "selected_policy": msg.selected_policy,
                "selected_score": round(msg.selected_score, 4),
                "rejected_policy": msg.rejected_policy,
                "score_gap": round(msg.score_gap, 4),
                "trigger_event": msg.trigger_event,
                "trigger_description": msg.trigger_description,
                "conflict_qas": msg.conflict_qas,
                "three_way_conflict": msg.three_way_conflict,
                "dominant_qa": msg.dominant_qa,
                "dominant_weight": round(msg.dominant_weight, 3),
                "benefit_value": round(msg.benefit_value, 4),
                "cost_value": round(msg.cost_value, 4),
                "gap_decomposition": json.loads(
                    msg.gap_decomposition_json or "{}"),
                "policy_changed": msg.policy_changed,
                "previous_policy": msg.previous_policy,
                "context_unchanged": msg.context_unchanged,
                "uncertain_decision": msg.uncertain_decision,
            },
        }
        text = json.dumps(payload)
        with self._state_lock:
            self._last_tick = text
        self._ws.broadcast(text)

    def _on_weights_state(self, msg: AuraWeightsMsg) -> None:
        text = json.dumps({"type": "weights",
                           "safety": round(msg.w_safety, 3),
                           "time": round(msg.w_time, 3),
                           "energy": round(msg.w_energy, 3)})
        with self._state_lock:
            self._last_weights = text
        self._ws.broadcast(text)

    def _on_metrics(self, msg: AuraMetricsMsg) -> None:
        self._send({"type": "metrics",
                    "total": msg.total_decisions,
                    "switches": msg.policy_switches,
                    "conflicts": msg.conflicts_detected,
                    "uncertain": msg.uncertain_decisions,
                    "latency_ms": round(msg.avg_latency_ms, 1)})

    def _on_diagnostics(self, msg: AuraDiagnosticsMsg) -> None:
        self._send({"type": "diagnostics",
                    "planner_hz": round(msg.planner_hz, 1),
                    "explanation_hz": round(msg.explanation_hz, 1),
                    "latency_ms": round(msg.latency_ms, 2),
                    "planner_alive": msg.planner_alive})

    def _on_status(self, msg: String) -> None:
        with self._state_lock:
            self._scenario = msg.data

    def _on_reset(self, msg: String) -> None:
        self._send({"type": "reset", "scenario": msg.data})

    def _publish_status(self) -> None:
        out = Bool()
        out.data = self._ws.count() > 0
        self._status_pub.publish(out)

    # -- inbound (console -> ROS) ---------------------------------------------

    def handle_inbound(self, raw: str) -> None:
        try:
            cmd = json.loads(raw)
        except json.JSONDecodeError:
            return
        if cmd.get("type") == "weights":
            msg = AuraWeightsMsg()
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.w_safety = float(cmd["safety"])
            msg.w_time = float(cmd["time"])
            msg.w_energy = float(cmd["energy"])
            self._weights_pub.publish(msg)
        elif cmd.get("type") == "scenario":
            msg = String()
            msg.data = str(cmd["id"])
            self._select_pub.publish(msg)

    def shutdown(self) -> None:
        self._ws.stop()


def _run_http_server(http_port: int) -> None:
    web_dir = os.path.join(
        get_package_share_directory("aura_dashboard"), "operator_console")
    class _QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args, **kwargs):
            pass  # keep the launch terminal readable

    handler = partial(_QuietHandler, directory=web_dir)
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer(("0.0.0.0", http_port),
                                         handler) as httpd:
        httpd.serve_forever()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = WebBridgeNode()

    http_port = int(node.get_parameter("http_port").value)
    threading.Thread(
        target=_run_http_server, args=(http_port,), daemon=True).start()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            node.shutdown()
            node.destroy_node()
        except Exception:
            pass
        try:
            rclpy.shutdown()
        except Exception:
            pass


if __name__ == "__main__":
    main()
