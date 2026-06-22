"""RTSP camera_web 的同进程组件 launch 配置。"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import ComposableNodeContainer
from launch_ros.descriptions import ComposableNode
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    rtsp_url = LaunchConfiguration('rtsp_url')
    width = LaunchConfiguration('width')
    height = LaunchConfiguration('height')
    fps = LaunchConfiguration('fps')
    port = LaunchConfiguration('port')
    jpeg_quality = LaunchConfiguration('jpeg_quality')

    return LaunchDescription([
        DeclareLaunchArgument('rtsp_url'),
        DeclareLaunchArgument('width', default_value='1280'),
        DeclareLaunchArgument('height', default_value='960'),
        DeclareLaunchArgument('fps', default_value='25'),
        DeclareLaunchArgument('port', default_value='8081'),
        DeclareLaunchArgument('jpeg_quality', default_value='85'),
        ComposableNodeContainer(
            name='camera_web_cpp_container',
            namespace='',
            package='rclcpp_components',
            executable='component_container_mt',
            output='screen',
            composable_node_descriptions=[
                ComposableNode(
                    package='camera_web_cpp',
                    plugin='camera_web_cpp::RtspMjpegPublisher',
                    name='rtsp_mjpeg_publisher',
                    parameters=[{
                        'rtsp_url': rtsp_url,
                        'width': ParameterValue(width, value_type=int),
                        'height': ParameterValue(height, value_type=int),
                        'fps': ParameterValue(fps, value_type=int),
                        'jpeg_quality': ParameterValue(jpeg_quality, value_type=int),
                        'topic': '/camera/image_mjpeg',
                    }],
                    extra_arguments=[{'use_intra_process_comms': True}],
                ),
                ComposableNode(
                    package='camera_web_cpp',
                    plugin='camera_web_cpp::CompressedMjpegServer',
                    name='compressed_mjpeg_server',
                    parameters=[{
                        'image_topic': '/camera/image_mjpeg',
                        'port': ParameterValue(port, value_type=int),
                        'target_fps': ParameterValue(fps, value_type=float),
                    }],
                    extra_arguments=[{'use_intra_process_comms': True}],
                ),
            ],
        ),
    ])
