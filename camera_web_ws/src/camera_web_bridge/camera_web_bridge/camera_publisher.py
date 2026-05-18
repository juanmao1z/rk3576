"""将 V4L2 摄像头画面发布为 ROS2 Image 话题。

该节点用于开发板端快速测试：通过 OpenCV 打开 USB 摄像头，
使用 cv_bridge 将每帧图像转换为 ROS2 Image 消息，并默认发布到
/camera/image_raw。
"""

import time

import cv2
from cv_bridge import CvBridge
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image


class CameraPublisher(Node):
    """读取摄像头设备，并将画面发布为 sensor_msgs/Image。"""

    def __init__(self):
        """创建发布器、声明运行参数，并启动定时采集。"""
        super().__init__('camera_publisher')
        self.declare_parameter('device', '/dev/video73')
        self.declare_parameter('topic', '/camera/image_raw')
        self.declare_parameter('frame_id', 'usb_camera')
        self.declare_parameter('width', 640)
        self.declare_parameter('height', 480)
        self.declare_parameter('fps', 25.0)
        self.declare_parameter('fourcc', 'MJPG')

        self.device = self.get_parameter('device').value
        topic = self.get_parameter('topic').value
        self.frame_id = self.get_parameter('frame_id').value
        self.width = int(self.get_parameter('width').value)
        self.height = int(self.get_parameter('height').value)
        self.fps = float(self.get_parameter('fps').value)
        self.fourcc = str(self.get_parameter('fourcc').value)

        self.bridge = CvBridge()
        self.publisher = self.create_publisher(Image, topic, 10)
        self.capture = None
        self.last_open_attempt = 0.0

        period = 1.0 / max(self.fps, 1.0)
        self.timer = self.create_timer(period, self.publish_frame)
        self.get_logger().info(
            f'Publishing {self.device} to {topic} '
            f'at {self.width}x{self.height}@{self.fps:g}'
        )

    def open_capture(self):
        """按照配置参数打开或重新打开 V4L2 摄像头。"""
        now = time.monotonic()
        if now - self.last_open_attempt < 1.0:
            return False
        self.last_open_attempt = now

        if self.capture is not None:
            self.capture.release()

        capture = cv2.VideoCapture(self.device, cv2.CAP_V4L2)
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        capture.set(cv2.CAP_PROP_FPS, self.fps)
        # 当前测试摄像头在 MJPG 格式下比原始 YUYV 格式更容易跑到较高帧率。
        if self.fourcc:
            fourcc = cv2.VideoWriter_fourcc(*self.fourcc[:4])
            capture.set(cv2.CAP_PROP_FOURCC, fourcc)

        if not capture.isOpened():
            self.get_logger().warning(f'Cannot open camera device {self.device}')
            capture.release()
            self.capture = None
            return False

        self.capture = capture
        self.get_logger().info(f'Opened camera device {self.device}')
        return True

    def publish_frame(self):
        """采集一帧图像，并发布到配置的 ROS2 话题。"""
        if self.capture is None or not self.capture.isOpened():
            if not self.open_capture():
                return

        ok, frame = self.capture.read()
        if not ok or frame is None:
            self.get_logger().warning('Failed to read frame; reopening camera')
            self.capture.release()
            self.capture = None
            return

        msg = self.bridge.cv2_to_imgmsg(frame, encoding='bgr8')
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = self.frame_id
        self.publisher.publish(msg)

    def destroy_node(self):
        """关闭 ROS2 节点前释放摄像头设备。"""
        if self.capture is not None:
            self.capture.release()
        super().destroy_node()


def main():
    """运行摄像头发布节点。"""
    rclpy.init()
    node = CameraPublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
