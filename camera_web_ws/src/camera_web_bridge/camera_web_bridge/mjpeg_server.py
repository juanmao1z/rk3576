"""将 ROS2 Image 话题转换为浏览器可访问的 MJPEG 视频流。

该节点默认订阅 /camera/image_raw，将收到的 sensor_msgs/Image 消息转换为
JPEG 帧，并通过 Python 标准库 HTTP 服务输出。浏览器页面使用 /stream.mjpg，
/snapshot.jpg 和 /health 主要用于命令行验证。
"""

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from collections import deque
import os
import socket
import threading
import time

import cv2
from cv_bridge import CvBridge
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image


JPEG_ENCODE_OPTIONS = [int(cv2.IMWRITE_JPEG_QUALITY), 65]


class SharedFrame:
    """在线程之间安全传递最新 JPEG 帧的共享对象。"""

    def __init__(self):
        """初始化 ROS 线程和 HTTP 线程共用的帧状态。"""
        self.condition = threading.Condition()
        self.jpeg = None
        self.frame_count = 0
        self.last_update = 0.0

    def update(self, jpeg):
        """保存新的 JPEG 帧，并唤醒正在等待的 HTTP 客户端。"""
        with self.condition:
            self.jpeg = jpeg
            self.frame_count += 1
            self.last_update = time.time()
            self.condition.notify_all()

    def wait_for_frame(self, previous_count, timeout=2.0):
        """等待出现比 previous_count 更新的帧。"""
        with self.condition:
            if self.frame_count == previous_count:
                self.condition.wait(timeout)
            return self.jpeg, self.frame_count, self.last_update


class MjpegHandler(BaseHTTPRequestHandler):
    """处理 HTML 页面、MJPEG 视频流和检测接口的 HTTP 请求。"""

    server_version = 'camera-web-bridge/0.1'

    def do_GET(self):
        """将支持的 GET 路径分发到对应处理函数。"""
        if self.path in ('/', '/index.html'):
            self.send_index()
            return
        if self.path == '/stream.mjpg':
            self.send_stream()
            return
        if self.path == '/snapshot.jpg':
            self.send_snapshot()
            return
        if self.path == '/health':
            self.send_health()
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def log_message(self, fmt, *args):
        """通过 ROS 日志系统输出 HTTP 请求日志。"""
        self.server.node.get_logger().debug(fmt % args)

    def send_index(self):
        """返回一个嵌入 MJPEG 视频流的简单浏览器页面。"""
        html = b'''<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ROS2 Camera Stream</title>
  <style>
    body { margin: 0; font-family: system-ui, sans-serif; background: #111; color: #eee; }
    main { max-width: 960px; margin: 0 auto; padding: 20px; }
    img { width: 100%; height: auto; background: #000; }
    code { color: #8fd; }
  </style>
</head>
<body>
  <main>
    <h1>ROS2 Camera Stream</h1>
    <p>Topic: <code>/camera/image_raw</code> | Stream: <code>/stream.mjpg</code></p>
    <img src="/stream.mjpg" alt="ROS2 camera stream">
  </main>
</body>
</html>'''
        self.send_response(HTTPStatus.OK)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(html)))
        self.end_headers()
        self.wfile.write(html)

    def send_health(self):
        """返回帧计数和最新帧延迟，用于轻量级健康检查。"""
        shared = self.server.shared
        age = time.time() - shared.last_update if shared.last_update else -1
        body = f'frames={shared.frame_count} age={age:.3f}\n'.encode()
        self.send_response(HTTPStatus.OK)
        self.send_header('Content-Type', 'text/plain; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_snapshot(self):
        """将最新 JPEG 帧作为单张静态图片返回。"""
        jpeg, _, _ = self.server.shared.wait_for_frame(-1, timeout=0.1)
        if jpeg is None:
            self.send_error(HTTPStatus.SERVICE_UNAVAILABLE, 'No frame received yet')
            return
        self.send_response(HTTPStatus.OK)
        self.send_header('Content-Type', 'image/jpeg')
        self.send_header('Content-Length', str(len(jpeg)))
        self.end_headers()
        self.wfile.write(jpeg)

    def send_stream(self):
        """使用 multipart/x-mixed-replace 持续输出 JPEG 帧。"""
        self.send_response(HTTPStatus.OK)
        self.send_header('Age', '0')
        self.send_header('Cache-Control', 'no-cache, private')
        self.send_header('Pragma', 'no-cache')
        self.send_header(
            'Content-Type',
            'multipart/x-mixed-replace; boundary=frame',
        )
        self.end_headers()

        frame_count = -1
        while self.server.running:
            jpeg, new_count, _ = self.server.shared.wait_for_frame(frame_count)
            if jpeg is None or new_count == frame_count:
                continue
            frame_count = new_count
            try:
                # MJPEG 浏览器需要真实的 CRLF 字节分隔 multipart 头部。
                self.wfile.write(b'--frame\r\n')
                self.wfile.write(b'Content-Type: image/jpeg\r\n')
                self.wfile.write(f'Content-Length: {len(jpeg)}\r\n\r\n'.encode())
                self.wfile.write(jpeg)
                self.wfile.write(b'\r\n')
            except (BrokenPipeError, ConnectionResetError, socket.timeout):
                break


class RosMjpegServer(Node):
    """订阅 ROS2 Image 话题，并通过 HTTP 对外提供视频。"""

    def __init__(self):
        """创建 ROS 订阅，并启动 HTTP 服务线程。"""
        super().__init__('mjpeg_server')
        self.declare_parameter('image_topic', '/camera/image_raw')
        self.declare_parameter('host', '0.0.0.0')
        self.declare_parameter('port', 8080)
        self.declare_parameter('show_fps', True)
        self.declare_parameter('target_fps', 30.0)

        self.image_topic = self.get_parameter('image_topic').value
        self.host = self.get_parameter('host').value
        self.port = int(self.get_parameter('port').value)
        self.show_fps = bool(self.get_parameter('show_fps').value)
        self.target_fps = float(self.get_parameter('target_fps').value)

        self.bridge = CvBridge()
        self.shared = SharedFrame()
        self.frame_times = deque(maxlen=30)
        self.clock_ticks = os.sysconf(os.sysconf_names['SC_CLK_TCK'])
        self.cpu_count = max(os.cpu_count() or 1, 1)
        self.cpu_sample_interval = 0.5
        self.mjpeg_pid = os.getpid()
        self.publisher_pid = None
        self.last_cpu_sample = time.monotonic()
        self.last_mjpeg_ticks = self.read_process_cpu_ticks(self.mjpeg_pid)
        self.last_publisher_ticks = None
        self.current_publisher_cpu = 0.0
        self.current_mjpeg_cpu = 0.0
        self.current_total_cpu = 0.0
        self.current_system_cpu = 0.0
        self.subscription = self.create_subscription(
            Image,
            self.image_topic,
            self.on_image,
            10,
        )

        self.httpd = ThreadingHTTPServer((self.host, self.port), MjpegHandler)
        self.httpd.shared = self.shared
        self.httpd.node = self
        self.httpd.running = True
        self.http_thread = threading.Thread(
            target=self.httpd.serve_forever,
            name='mjpeg-http-server',
            daemon=True,
        )
        self.http_thread.start()
        self.get_logger().info(
            f'Serving {self.image_topic} at http://{self.host}:{self.port}/'
        )

    def on_image(self, msg):
        """将 ROS Image 消息转换为 JPEG，并发送给 HTTP 客户端。"""
        frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        if self.show_fps:
            ros_fps = self.update_fps()
            publisher_cpu, mjpeg_cpu, total_cpu, system_cpu = self.update_pipeline_cpu()
            self.draw_overlay(
                frame,
                ros_fps,
                self.target_fps,
                publisher_cpu,
                mjpeg_cpu,
                total_cpu,
                system_cpu,
            )
        ok, encoded = cv2.imencode(
            '.jpg',
            frame,
            JPEG_ENCODE_OPTIONS,
        )
        if not ok:
            self.get_logger().warning('JPEG encoding failed')
            return
        self.shared.update(encoded.tobytes())

    def update_fps(self):
        """根据最近若干帧时间戳计算滑动 FPS。"""
        now = time.monotonic()
        self.frame_times.append(now)
        if len(self.frame_times) < 2:
            return 0.0
        elapsed = self.frame_times[-1] - self.frame_times[0]
        if elapsed <= 0:
            return 0.0
        return (len(self.frame_times) - 1) / elapsed

    def update_pipeline_cpu(self):
        """估算发布节点、MJPEG 节点、总和及整机归一化后的 CPU 占用率。"""
        now = time.monotonic()
        if now - self.last_cpu_sample < self.cpu_sample_interval:
            return (
                self.current_publisher_cpu,
                self.current_mjpeg_cpu,
                self.current_total_cpu,
                self.current_system_cpu,
            )

        if self.publisher_pid is None or not os.path.exists(f'/proc/{self.publisher_pid}'):
            self.publisher_pid = self.find_publisher_pid()
            self.last_publisher_ticks = self.read_process_cpu_ticks(self.publisher_pid)

        wall_delta = now - self.last_cpu_sample
        mjpeg_ticks = self.read_process_cpu_ticks(self.mjpeg_pid)
        publisher_ticks = self.read_process_cpu_ticks(self.publisher_pid)
        self.current_mjpeg_cpu = self.ticks_to_percent(
            self.last_mjpeg_ticks,
            mjpeg_ticks,
            wall_delta,
        )
        self.current_publisher_cpu = self.ticks_to_percent(
            self.last_publisher_ticks,
            publisher_ticks,
            wall_delta,
        )
        self.current_total_cpu = self.current_publisher_cpu + self.current_mjpeg_cpu
        self.current_system_cpu = self.current_total_cpu / self.cpu_count
        self.last_cpu_sample = now
        self.last_mjpeg_ticks = mjpeg_ticks
        self.last_publisher_ticks = publisher_ticks
        return (
            self.current_publisher_cpu,
            self.current_mjpeg_cpu,
            self.current_total_cpu,
            self.current_system_cpu,
        )

    @staticmethod
    def find_publisher_pid():
        """查找当前链路中的 camera_publisher 进程 PID。"""
        current_pid = os.getpid()
        for entry in os.listdir('/proc'):
            if not entry.isdigit():
                continue
            pid = int(entry)
            if pid == current_pid:
                continue
            try:
                with open(f'/proc/{pid}/cmdline', 'rb') as handle:
                    cmdline = handle.read().decode('utf-8', errors='ignore')
            except OSError:
                continue
            if 'camera_publisher' in cmdline and 'camera_web_bridge' in cmdline:
                return pid
        return None

    @staticmethod
    def read_process_cpu_ticks(pid):
        """读取指定进程的用户态与内核态 CPU tick 总和。"""
        if pid is None:
            return None
        try:
            with open(f'/proc/{pid}/stat', 'r', encoding='utf-8') as handle:
                fields = handle.read().split()
        except OSError:
            return None
        return int(fields[13]) + int(fields[14])

    def ticks_to_percent(self, previous_ticks, current_ticks, wall_delta):
        """将两次采样间的 CPU tick 差值转换为占用率百分比。"""
        if previous_ticks is None or current_ticks is None or wall_delta <= 0:
            return 0.0
        cpu_seconds = (current_ticks - previous_ticks) / self.clock_ticks
        return max(0.0, cpu_seconds / wall_delta * 100.0)

    @staticmethod
    def draw_overlay(
        frame,
        ros_fps,
        target_fps,
        publisher_cpu,
        mjpeg_cpu,
        total_cpu,
        system_cpu,
    ):
        """将 FPS 和摄像头链路 CPU 占用率绘制到输出视频帧上。"""
        lines = [
            f'ROS FPS: {ros_fps:4.1f}',
            f'Target FPS: {target_fps:4.1f}',
            f'Publisher CPU: {publisher_cpu:4.1f}%',
            f'MJPEG CPU: {mjpeg_cpu:4.1f}%',
            f'Pipeline CPU: {system_cpu:4.1f}% sys',
        ]
        origin_x = 14
        origin_y = 34
        font = cv2.FONT_HERSHEY_SIMPLEX
        scale = 0.9
        thickness = 2
        line_gap = 12
        sizes = [
            cv2.getTextSize(text, font, scale, thickness)
            for text in lines
        ]
        width = max(size[0][0] for size in sizes)
        height = sum(size[0][1] for size in sizes) + line_gap * (len(lines) - 1)
        baseline = max(size[1] for size in sizes)
        cv2.rectangle(
            frame,
            (origin_x - 8, origin_y - sizes[0][0][1] - 8),
            (origin_x + width + 8, origin_y + height + baseline + 8),
            (0, 0, 0),
            -1,
        )
        cursor_y = origin_y
        for text, size in zip(lines, sizes):
            cv2.putText(
                frame,
                text,
                (origin_x, cursor_y),
                font,
                scale,
                (0, 255, 0),
                thickness,
                cv2.LINE_AA,
            )
            cursor_y += size[0][1] + line_gap

    def destroy_node(self):
        """关闭 ROS 节点前干净停止 HTTP 服务。"""
        if hasattr(self, 'httpd'):
            self.httpd.running = False
            self.httpd.shutdown()
            self.httpd.server_close()
        super().destroy_node()


def main():
    """运行 MJPEG 转发节点。"""
    rclpy.init()
    node = RosMjpegServer()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
