"""Operator console only — attach to an already-running AURA graph.

    ros2 launch aura_bringup dashboard.launch.py
"""

from launch import LaunchDescription
from launch.actions import ExecuteProcess, TimerAction
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(package="aura_dashboard", executable="web_bridge",
             name="web_bridge", output="screen"),
        TimerAction(period=2.0, actions=[
            ExecuteProcess(cmd=["xdg-open", "http://localhost:8080"],
                           shell=False)]),
    ])
