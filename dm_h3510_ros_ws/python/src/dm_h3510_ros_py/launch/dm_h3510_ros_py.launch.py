"""DM-H3510 ROS2 驱动 launch 文件。"""

from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    """创建 DM-H3510 ROS2 驱动节点启动描述。"""

    position_topic = LaunchConfiguration("position_topic")
    target_joint_topic = LaunchConfiguration("target_joint_topic")
    state_topic = LaunchConfiguration("state_topic")
    default_config = str(
        Path(get_package_share_directory("dm_h3510_ros_py")) / "config" / "dm_h3510_ros_py.yaml"
    )

    return LaunchDescription([
        DeclareLaunchArgument("position_topic", default_value="/gimbal/position_cmd"),
        DeclareLaunchArgument("target_joint_topic", default_value="/gimbal/target_joint_state"),
        DeclareLaunchArgument("state_topic", default_value="/gimbal/state"),
        Node(
            package="dm_h3510_ros_py",
            executable="dm_h3510_ros_py_node",
            name="dm_h3510_ros_py_node",
            output="screen",
            parameters=[
                default_config,
                {
                    "position_topic": position_topic,
                    "target_joint_topic": target_joint_topic,
                    "state_topic": state_topic,
                },
            ],
        ),
    ])
