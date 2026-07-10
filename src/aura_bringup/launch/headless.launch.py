"""AURA without the browser: nodes only, for rosbag recording / SSH runs.

    ros2 launch aura_bringup headless.launch.py scenario:=S3
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument("scenario", default_value="S1"),
        DeclareLaunchArgument("rate", default_value="2.0"),
        Node(package="aura_core", executable="scenario_manager",
             name="scenario_manager", output="screen",
             parameters=[{"scenario": LaunchConfiguration("scenario"),
                          "rate": LaunchConfiguration("rate")}]),
        Node(package="aura_core", executable="utility_planner",
             name="utility_planner", output="screen"),
        Node(package="aura_core", executable="aura_core",
             name="aura_core", output="screen"),
        Node(package="aura_core", executable="metrics",
             name="metrics_node", output="screen"),
        Node(package="aura_core", executable="logger",
             name="logger_node", output="screen"),
    ])
