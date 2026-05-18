"""C++ 版本 camera_web 的同进程组件 launch 配置。

该 launch 会启动一个 `ComposableNodeContainer`，并把：
1. CameraMjpegPublisher
2. CompressedMjpegServer

两个组件同时加载到同一个进程里运行。两者都显式启用
`use_intra_process_comms`，从而让压缩 JPEG 数据在容器内按同进程路径传递，
尽量减少跨进程搬运与 DDS 序列化开销。
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import ComposableNodeContainer
from launch_ros.descriptions import ComposableNode
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    """创建同进程 intra-process 版摄像头采集与 Web 转发联合启动配置。

    默认参数说明：
    - `device`: 摄像头设备节点
    - `width` / `height`: 采集分辨率
    - `fps`: 目标采集帧率，同时也会传给 Web 组件作为展示用目标 FPS
    - `port`: 浏览器访问端口
    """
    device = LaunchConfiguration('device')
    width = LaunchConfiguration('width')
    height = LaunchConfiguration('height')
    fps = LaunchConfiguration('fps')
    port = LaunchConfiguration('port')

    return LaunchDescription([
        # 默认参数与当前开发板上的 USB 摄像头能力保持一致。
        DeclareLaunchArgument('device', default_value='/dev/video73'),
        DeclareLaunchArgument('width', default_value='640'),
        DeclareLaunchArgument('height', default_value='480'),
        DeclareLaunchArgument('fps', default_value='25'),
        DeclareLaunchArgument('port', default_value='8081'),
        ComposableNodeContainer(
            # 使用多线程容器，保证采集节点和 Web 服务节点可以并行执行。
            name='camera_web_cpp_container',
            namespace='',
            package='rclcpp_components',
            executable='component_container_mt',
            output='screen',
            composable_node_descriptions=[
                ComposableNode(
                    # 摄像头采集组件：负责 V4L2 MMAP + MJPEG 压缩帧发布。
                    package='camera_web_cpp',
                    plugin='camera_web_cpp::CameraMjpegPublisher',
                    name='camera_mjpeg_publisher',
                    parameters=[{
                        'device': device,
                        'width': ParameterValue(width, value_type=int),
                        'height': ParameterValue(height, value_type=int),
                        'fps': ParameterValue(fps, value_type=int),
                        'topic': '/camera/image_mjpeg',
                    }],
                    extra_arguments=[{'use_intra_process_comms': True}],
                ),
                ComposableNode(
                    # Web 转发组件：负责浏览器 MJPEG 流和指标接口。
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
