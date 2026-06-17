"""无人机 YOLO C++ Canvas 节点 launch 文件。

launch 参数只描述运行期可调配置，默认使用工作区 models/yolo11n.rknn。
如果要测试 YOLOv5 模型，启动时把 model_path 指向 models/yolov5.rknn。
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    """创建无人机 YOLO C++ 节点启动描述。"""
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
            default_value='/home/lckfb/workspace/drone_yolo_web_cpp_ws/models/yolo11n.rknn'),
        DeclareLaunchArgument('labels', default_value='drone'),
        DeclareLaunchArgument('port', default_value='8092'),
        DeclareLaunchArgument('camera_url', default_value='http://127.0.0.1:8081/stream.mjpg'),
        DeclareLaunchArgument('confidence_threshold', default_value='0.60'),
        DeclareLaunchArgument('iou_threshold', default_value='0.45'),
        DeclareLaunchArgument('fps_window_seconds', default_value='2.0'),
        DeclareLaunchArgument('detections_topic', default_value='/yolo/detections'),
        Node(
            package='drone_yolo_web_cpp',
            executable='drone_yolo_web_cpp_node',
            name='drone_yolo_web_cpp_node',
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
