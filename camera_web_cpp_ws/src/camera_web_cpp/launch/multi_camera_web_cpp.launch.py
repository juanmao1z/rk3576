"""双路 C++ 摄像头 Web 服务 launch 配置。

该 launch 同时启动 front 和 left 两路摄像头。每一路使用独立的
component container、V4L2 设备、ROS2 图像话题和 HTTP 端口。
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import ComposableNodeContainer
from launch_ros.descriptions import ComposableNode
from launch_ros.parameter_descriptions import ParameterValue


def camera_container(
    prefix,
    device,
    width,
    height,
    fps,
    topic,
    frame_id,
    port,
):
    """创建单路摄像头采集和 Web 转发容器。"""
    return ComposableNodeContainer(
        name=f'{prefix}_camera_web_cpp_container',
        namespace='',
        package='rclcpp_components',
        executable='component_container_mt',
        output='screen',
        composable_node_descriptions=[
            ComposableNode(
                package='camera_web_cpp',
                plugin='camera_web_cpp::CameraMjpegPublisher',
                name=f'{prefix}_camera_mjpeg_publisher',
                parameters=[{
                    'device': device,
                    'width': ParameterValue(width, value_type=int),
                    'height': ParameterValue(height, value_type=int),
                    'fps': ParameterValue(fps, value_type=int),
                    'topic': topic,
                    'frame_id': frame_id,
                }],
                extra_arguments=[{'use_intra_process_comms': True}],
            ),
            ComposableNode(
                package='camera_web_cpp',
                plugin='camera_web_cpp::CompressedMjpegServer',
                name=f'{prefix}_compressed_mjpeg_server',
                parameters=[{
                    'image_topic': topic,
                    'port': ParameterValue(port, value_type=int),
                    'target_fps': ParameterValue(fps, value_type=float),
                }],
                extra_arguments=[{'use_intra_process_comms': True}],
            ),
        ],
    )


def generate_launch_description():
    """创建双摄像头 MJPEG 采集与 Web 转发启动配置。"""
    front_device = LaunchConfiguration('front_device')
    front_topic = LaunchConfiguration('front_topic')
    front_frame_id = LaunchConfiguration('front_frame_id')
    front_port = LaunchConfiguration('front_port')

    left_device = LaunchConfiguration('left_device')
    left_topic = LaunchConfiguration('left_topic')
    left_frame_id = LaunchConfiguration('left_frame_id')
    left_port = LaunchConfiguration('left_port')

    width = LaunchConfiguration('width')
    height = LaunchConfiguration('height')
    fps = LaunchConfiguration('fps')

    return LaunchDescription([
        DeclareLaunchArgument('front_device', default_value='/dev/video73'),
        DeclareLaunchArgument('front_topic', default_value='/camera/front/image_mjpeg'),
        DeclareLaunchArgument('front_frame_id', default_value='camera_front'),
        DeclareLaunchArgument('front_port', default_value='8081'),
        DeclareLaunchArgument('left_device', default_value='/dev/video75'),
        DeclareLaunchArgument('left_topic', default_value='/camera/left/image_mjpeg'),
        DeclareLaunchArgument('left_frame_id', default_value='camera_left'),
        DeclareLaunchArgument('left_port', default_value='8082'),
        DeclareLaunchArgument('width', default_value='640'),
        DeclareLaunchArgument('height', default_value='480'),
        DeclareLaunchArgument('fps', default_value='25'),
        camera_container(
            'front',
            front_device,
            width,
            height,
            fps,
            front_topic,
            front_frame_id,
            front_port,
        ),
        camera_container(
            'left',
            left_device,
            width,
            height,
            fps,
            left_topic,
            left_frame_id,
            left_port,
        ),
    ])
