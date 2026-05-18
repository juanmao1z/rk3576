"""通用 YOLO C++ Canvas 节点 launch 文件。

launch 参数只描述运行期可调配置，默认值保持通用 YOLO 路径：
模型使用 yolo_web_cpp_ws/models/yolo11.rknn，标签使用 coco。
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    """创建通用 YOLO C++ 节点启动描述。"""
    input_topic = LaunchConfiguration('input_topic')
    model_path = LaunchConfiguration('model_path')
    labels = LaunchConfiguration('labels')
    port = LaunchConfiguration('port')
    camera_url = LaunchConfiguration('camera_url')
    confidence_threshold = LaunchConfiguration('confidence_threshold')
    iou_threshold = LaunchConfiguration('iou_threshold')
    fps_window_seconds = LaunchConfiguration('fps_window_seconds')
    detections_topic = LaunchConfiguration('detections_topic')

    return LaunchDescription([
        DeclareLaunchArgument('input_topic', default_value='/camera/image_mjpeg'),
        DeclareLaunchArgument(
            'model_path',
            default_value='/home/lckfb/workspace/yolo/yolo_web_cpp_ws/models/yolo11.rknn'),
        DeclareLaunchArgument('labels', default_value='coco'),
        DeclareLaunchArgument('port', default_value='8092'),
        DeclareLaunchArgument('camera_url', default_value='http://127.0.0.1:8081/stream.mjpg'),
        DeclareLaunchArgument('confidence_threshold', default_value='0.25'),
        DeclareLaunchArgument('iou_threshold', default_value='0.45'),
        DeclareLaunchArgument('fps_window_seconds', default_value='2.0'),
        DeclareLaunchArgument('detections_topic', default_value='/yolo/detections'),
        Node(
            package='yolo_web_cpp',
            executable='yolo_web_cpp_node',
            name='yolo_web_cpp_node',
            output='screen',
            parameters=[{
                'input_topic': input_topic,
                'model_path': model_path,
                'labels': labels,
                'port': ParameterValue(port, value_type=int),
                'camera_url': camera_url,
                'confidence_threshold': ParameterValue(confidence_threshold, value_type=float),
                'iou_threshold': ParameterValue(iou_threshold, value_type=float),
                'fps_window_seconds': ParameterValue(fps_window_seconds, value_type=float),
                'detections_topic': detections_topic,
            }],
        ),
    ])
