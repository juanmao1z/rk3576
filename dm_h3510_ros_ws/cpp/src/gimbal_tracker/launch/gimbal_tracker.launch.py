"""gimbal_tracker launch file."""

import os

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from ament_index_python.packages import get_package_share_directory
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    config_file = os.path.join(
        get_package_share_directory("gimbal_tracker"),
        "config",
        "gimbal_tracker.yaml",
    )
    detections_topic = LaunchConfiguration("detections_topic")
    gimbal_state_topic = LaunchConfiguration("gimbal_state_topic")
    target_joint_topic = LaunchConfiguration("target_joint_topic")
    max_step_rad = LaunchConfiguration("max_step_rad")
    velocity_rad_s = LaunchConfiguration("velocity_rad_s")
    dry_run = LaunchConfiguration("dry_run")

    return LaunchDescription([
        DeclareLaunchArgument("detections_topic", default_value="/yolo/detections"),
        DeclareLaunchArgument("gimbal_state_topic", default_value="/gimbal/state"),
        DeclareLaunchArgument("target_joint_topic", default_value="/gimbal/target_joint_state"),
        DeclareLaunchArgument("max_step_rad", default_value="0.05"),
        DeclareLaunchArgument("velocity_rad_s", default_value="0.6"),
        DeclareLaunchArgument("dry_run", default_value="true"),
        Node(
            package="gimbal_tracker",
            executable="gimbal_tracker_node",
            name="gimbal_tracker_node",
            output="screen",
            parameters=[
                config_file,
                {
                    # 命令行参数放在配置文件之后，用于临时覆盖话题名和 dry-run。
                    "detections_topic": detections_topic,
                    "gimbal_state_topic": gimbal_state_topic,
                    "target_joint_topic": target_joint_topic,
                    "max_step_rad": ParameterValue(max_step_rad, value_type=float),
                    "velocity_rad_s": ParameterValue(velocity_rad_s, value_type=float),
                    "dry_run": ParameterValue(dry_run, value_type=bool),
                },
            ],
        ),
    ])
