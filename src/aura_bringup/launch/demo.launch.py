"""Full AURA demo: all nodes + operator console, one command.

    ros2 launch aura_bringup demo.launch.py
    ros2 launch aura_bringup demo.launch.py scenario:=S5
    ros2 launch aura_bringup demo.launch.py planner:=rule

Opens the operator console in the browser automatically.
"""

from launch import LaunchDescription
from launch.actions import (DeclareLaunchArgument, ExecuteProcess,
                            TimerAction)
from launch.conditions import LaunchConfigurationEquals
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    scenario = LaunchConfiguration("scenario")
    return LaunchDescription([
        DeclareLaunchArgument("scenario", default_value="S1",
                              description="S1..S5"),
        DeclareLaunchArgument("planner", default_value="utility",
                              description="utility | rule"),
        DeclareLaunchArgument("rate", default_value="2.0",
                              description="context rate, Hz"),

        Node(package="aura_core", executable="scenario_manager",
             name="scenario_manager", output="screen",
             parameters=[{"scenario": scenario,
                          "rate": LaunchConfiguration("rate")}]),

        Node(package="aura_core", executable="utility_planner",
             name="utility_planner", output="screen",
             condition=LaunchConfigurationEquals("planner", "utility")),
        Node(package="aura_examples", executable="rule_planner",
             name="rule_planner", output="screen",
             condition=LaunchConfigurationEquals("planner", "rule")),

        Node(package="aura_core", executable="aura_core",
             name="aura_core", output="screen"),
        Node(package="aura_core", executable="metrics",
             name="metrics_node", output="screen"),
        Node(package="aura_core", executable="logger",
             name="logger_node", output="screen"),
        Node(package="aura_dashboard", executable="web_bridge",
             name="web_bridge", output="screen"),

        TimerAction(period=3.0, actions=[
            ExecuteProcess(cmd=["xdg-open", "http://localhost:8080"],
                           shell=False)]),
    ])
