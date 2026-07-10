"""scenario_manager_node — drives the simulated world.

This node OWNS the world: the human entering the corridor, the battery
draining, the emergency call, the localization decay, the operator's S5
weight change. It publishes the resulting context stream exactly the way a
sensor-fusion node would on real hardware — which is the point: to deploy
AURA on a Duckiebot or TurtleBot, this node is replaced by one that reads
real sensors, and nothing downstream changes.

Topics:
  publishes  /aura/context/current   (aura_msgs/RobotContext)   @ `rate` Hz
  publishes  /aura/weights           (aura_msgs/AuraWeights)    scheduled ops
  publishes  /aura/scenario/status   (std_msgs/String)          "S1 t=13.0"
  publishes  /aura/scenario/reset    (std_msgs/String)          on (re)start
  subscribes /aura/scenario/select   (std_msgs/String)          switch live

Parameters:
  scenario (string, default "S1")  — S1..S5
  rate (double, default 2.0)       — context publish rate, Hz
  loop (bool, default true)        — restart the scenario when it ends
  config_file (string)             — path to scenarios.yaml
"""

from __future__ import annotations

import os
from typing import Dict, List

import yaml
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from ament_index_python.packages import get_package_share_directory

from aura_msgs.msg import RobotContext as RobotContextMsg
from aura_msgs.msg import AuraWeights as AuraWeightsMsg

from aura_interfaces.context import RobotContext
from aura_interfaces.ros_convert import context_to_msg


class ScenarioManagerNode(Node):
    """Runs one scripted scenario as a live ROS2 context stream."""

    def __init__(self) -> None:
        super().__init__("scenario_manager")
        self.declare_parameter("scenario", "S1")
        self.declare_parameter("rate", 2.0)
        self.declare_parameter("loop", True)
        default_cfg = os.path.join(
            get_package_share_directory("aura_core"), "config", "scenarios.yaml")
        self.declare_parameter("config_file", default_cfg)

        cfg_path = self.get_parameter("config_file").value
        with open(cfg_path) as handle:
            self.scenarios: Dict = yaml.safe_load(handle)["scenarios"]

        self.ctx_pub = self.create_publisher(
            RobotContextMsg, "/aura/context/current", 10)
        self.weights_pub = self.create_publisher(
            AuraWeightsMsg, "/aura/weights", 10)
        self.status_pub = self.create_publisher(
            String, "/aura/scenario/status", 10)
        self.reset_pub = self.create_publisher(
            String, "/aura/scenario/reset", 10)
        self.create_subscription(
            String, "/aura/scenario/select", self._on_select, 10)

        self.rate = float(self.get_parameter("rate").value)
        self.sid = str(self.get_parameter("scenario").value)
        self._start_scenario(self.sid)
        self.create_timer(1.0 / self.rate, self._tick)
        self.get_logger().info(
            f"scenario_manager up — {self.sid} @ {self.rate:.1f} Hz "
            f"({len(self.scenarios)} scenarios loaded from {cfg_path})")

    # --- scenario lifecycle ------------------------------------------------

    def _start_scenario(self, sid: str) -> None:
        """(Re)initialise world state for scenario `sid`."""
        if sid not in self.scenarios:
            self.get_logger().warn(f"unknown scenario '{sid}', keeping {self.sid}")
            return
        self.sid = sid
        spec = self.scenarios[sid]
        self.t = 0.0
        self.duration = float(spec.get("duration", 25))
        self.events: List[Dict] = list(spec.get("events", []))
        self.weight_schedule: List[Dict] = sorted(
            spec.get("weight_schedule", []), key=lambda e: e["at"])
        self._weights_fired = [False] * len(self.weight_schedule)
        c = spec["context"]
        self._world = RobotContext(
            battery_level=float(c["battery_level"]),
            human_proximity=float(c["human_proximity"]),
            obstacle_density=float(c["obstacle_density"]),
            localization_confidence=float(c["localization_confidence"]),
            mission_priority=str(c["mission_priority"]),
        )
        # Announce the reset so planner + AURA core clear transition state.
        msg = String(); msg.data = sid
        self.reset_pub.publish(msg)
        # Publish the scenario's default weights as an operator command so
        # the planner's parameters converge to the script.
        w = spec["weights"]
        self._publish_weights(float(w["safety"]), float(w["time"]),
                              float(w["energy"]))
        self.get_logger().info(f"scenario {sid} started — {spec['name']}")

    def _on_select(self, msg: String) -> None:
        """Live scenario switch from the console or CLI."""
        self._start_scenario(msg.data.strip())

    # --- world stepping ------------------------------------------------------

    def _tick(self) -> None:
        """Advance the world one publish interval and emit the context."""
        dt = 1.0 / self.rate
        self.t += dt

        for event in self.events:
            self._apply_event(self._world, event, dt)

        for i, entry in enumerate(self.weight_schedule):
            if not self._weights_fired[i] and self.t >= float(entry["at"]):
                self._weights_fired[i] = True
                self._publish_weights(float(entry["w_safety"]),
                                      float(entry["w_time"]),
                                      float(entry["w_energy"]))
                self.get_logger().info(
                    f"OPERATOR weight change fired at t={self.t:.1f}s")

        self._world.timestamp = self.t
        msg = context_to_msg(self._world)
        msg.header.stamp = self.get_clock().now().to_msg()
        self.ctx_pub.publish(msg)

        status = String(); status.data = f"{self.sid} t={self.t:.1f}"
        self.status_pub.publish(status)

        if self.t >= self.duration:
            if bool(self.get_parameter("loop").value):
                self._start_scenario(self.sid)
            else:
                self.get_logger().info(f"scenario {self.sid} finished")
                self.t = self.duration   # hold final state

    def _apply_event(self, world: RobotContext, event: Dict, dt: float) -> None:
        """Apply one scripted event for this tick."""
        kind = event["type"]
        var = event["variable"]
        if kind == "drain":
            value = getattr(world, var) - float(event["rate"]) * dt
            setattr(world, var, max(float(event.get("floor", 0.0)), value))
        elif kind == "ramp":
            start, end = float(event["start"]), float(event["end"])
            if self.t < start:
                return
            if self.t >= end:
                setattr(world, var, float(event["to"]))
                return
            frac = (self.t - start) / (end - start)
            value = float(event["from"]) + frac * (float(event["to"])
                                                   - float(event["from"]))
            setattr(world, var, value)
        elif kind == "step":
            if self.t >= float(event["at"]):
                setattr(world, var, event["value"])

    def _publish_weights(self, ws: float, wt: float, we: float) -> None:
        msg = AuraWeightsMsg()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.w_safety, msg.w_time, msg.w_energy = ws, wt, we
        self.weights_pub.publish(msg)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = ScenarioManagerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
