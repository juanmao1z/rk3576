"""YOLO Python 服务端画框版 launch 文件。

默认模型来自 yolo_web_py_ws/models/yolo11.rknn，输出 8090 带框 MJPEG。
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    """创建 Python 服务端画框版 YOLO 节点启动描述。"""
    input_topic = LaunchConfiguration('input_topic')
    model_path = LaunchConfiguration('model_path')
    port = LaunchConfiguration('port')
    confidence_threshold = LaunchConfiguration('confidence_threshold')
    iou_threshold = LaunchConfiguration('iou_threshold')
    jpeg_quality = LaunchConfiguration('jpeg_quality')
    fps_window_seconds = LaunchConfiguration('fps_window_seconds')
    detections_topic = LaunchConfiguration('detections_topic')

    return LaunchDescription([
        DeclareLaunchArgument('input_topic', default_value='/camera/image_mjpeg'),
        DeclareLaunchArgument(
            'model_path',
            default_value='/home/lckfb/workspace/yolo/yolo_web_py_ws/models/yolo11.rknn'),
        DeclareLaunchArgument('port', default_value='8090'),
        DeclareLaunchArgument('confidence_threshold', default_value='0.25'),
        DeclareLaunchArgument('iou_threshold', default_value='0.45'),
        DeclareLaunchArgument('jpeg_quality', default_value='65'),
        DeclareLaunchArgument('fps_window_seconds', default_value='2.0'),
        DeclareLaunchArgument('detections_topic', default_value='/yolo/detections'),
        Node(
            package='yolo_web_py',
            executable='yolo_web_py_node',
            name='yolo_web_py_node',
            output='screen',
            parameters=[{
                'input_topic': input_topic,
                'model_path': model_path,
                'port': ParameterValue(port, value_type=int),
                'confidence_threshold': ParameterValue(confidence_threshold, value_type=float),
                'iou_threshold': ParameterValue(iou_threshold, value_type=float),
                'jpeg_quality': ParameterValue(jpeg_quality, value_type=int),
                'fps_window_seconds': ParameterValue(fps_window_seconds, value_type=float),
                'detections_topic': detections_topic,
            }],
        ),
    ])
