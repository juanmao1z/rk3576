"""同时启动摄像头发布节点和 MJPEG 转发节点。"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    """创建从摄像头到浏览器视频流的完整 launch 配置。"""
    device = LaunchConfiguration('device')
    width = LaunchConfiguration('width')
    height = LaunchConfiguration('height')
    fps = LaunchConfiguration('fps')
    port = LaunchConfiguration('port')

    return LaunchDescription([
        # 默认参数匹配当前 RK3576 开发板上检测到的 USB 摄像头。
        DeclareLaunchArgument('device', default_value='/dev/video73'),
        DeclareLaunchArgument('width', default_value='1280'),
        DeclareLaunchArgument('height', default_value='720'),
        DeclareLaunchArgument('fps', default_value='30.0'),
        DeclareLaunchArgument('port', default_value='8080'),
        Node(
            package='camera_web_bridge',
            executable='camera_publisher',
            name='camera_publisher',
            output='screen',
            parameters=[{
                'device': device,
                'width': ParameterValue(width, value_type=int),
                'height': ParameterValue(height, value_type=int),
                'fps': ParameterValue(fps, value_type=float),
                'topic': '/camera/image_raw',
            }],
        ),
        Node(
            package='camera_web_bridge',
            executable='mjpeg_server',
            name='mjpeg_server',
            output='screen',
            parameters=[{
                'image_topic': '/camera/image_raw',
                'host': '0.0.0.0',
                'port': ParameterValue(port, value_type=int),
            }],
        ),
    ])
