"""Python RKNN YOLO11 服务端画框节点。

该节点订阅 /camera/image_mjpeg，使用 RKNNLite 推理，在服务端用 OpenCV
绘制检测框并重新编码 JPEG，然后通过 MJPEG 结果流输出给浏览器。
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import socket
import threading
import time
from typing import List, Optional, Sequence, Tuple

import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage
from vision_msgs.msg import Detection2D, Detection2DArray, ObjectHypothesisWithPose
from rknnlite.api import RKNNLite


IMG_SIZE = (640, 640)
DEFAULT_CLASSES = (
    "person", "bicycle", "car", "motorbike", "aeroplane", "bus", "train", "truck", "boat",
    "traffic light", "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat", "dog",
    "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella",
    "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball", "kite",
    "baseball bat", "baseball glove", "skateboard", "surfboard", "tennis racket", "bottle",
    "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple", "sandwich",
    "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair", "sofa",
    "pottedplant", "bed", "diningtable", "toilet", "tvmonitor", "laptop", "mouse", "remote",
    "keyboard", "cell phone", "microwave", "oven", "toaster", "sink", "refrigerator", "book",
    "clock", "vase", "scissors", "teddy bear", "hair drier", "toothbrush",
)


@dataclass
class Detection:
    """单个检测框，坐标使用原始输入图像像素。"""

    class_id: int
    label: str
    score: float
    x: float
    y: float
    width: float
    height: float


@dataclass
class Snapshot:
    """HTTP 线程读取的最新检测和 JPEG 结果快照。"""

    frame: int
    image_width: int
    image_height: int
    result_fps: float
    last_pipeline_ms: float
    last_decode_ms: float
    last_inference_ms: float
    last_postprocess_ms: float
    last_encode_ms: float
    age: float
    detections: List[Detection]
    jpeg: Optional[bytes]


class SharedResult:
    """ROS 推理线程和 HTTP 线程之间共享最新结果。"""

    def __init__(self):
        self.condition = threading.Condition()
        self.frame = 0
        self.image_width = 0
        self.image_height = 0
        self.jpeg: Optional[bytes] = None
        self.detections: List[Detection] = []
        self.frame_times: deque[float] = deque()
        self.last_update = 0.0
        self.last_pipeline_ms = 0.0
        self.last_decode_ms = 0.0
        self.last_inference_ms = 0.0
        self.last_postprocess_ms = 0.0
        self.last_encode_ms = 0.0

    def update(
        self,
        image_width: int,
        image_height: int,
        jpeg: bytes,
        detections: List[Detection],
        timings: Tuple[float, float, float, float, float],
        fps_window_seconds: float,
    ) -> None:
        """保存已完成推理和重新编码的一帧结果，并唤醒 MJPEG 客户端。"""
        now = time.monotonic()
        with self.condition:
            self.frame += 1
            self.image_width = image_width
            self.image_height = image_height
            self.jpeg = jpeg
            self.detections = detections
            self.last_update = now
            (
                self.last_pipeline_ms,
                self.last_decode_ms,
                self.last_inference_ms,
                self.last_postprocess_ms,
                self.last_encode_ms,
            ) = timings
            self.frame_times.append(now)
            window = max(0.2, fps_window_seconds)
            while len(self.frame_times) > 2 and now - self.frame_times[0] > window:
                self.frame_times.popleft()
            self.condition.notify_all()

    def snapshot(self, fps_window_seconds: float) -> Snapshot:
        """返回一致性快照，并按完成推理的帧计算 result_fps。"""
        now = time.monotonic()
        with self.condition:
            times = [t for t in self.frame_times if now - t <= max(0.2, fps_window_seconds)]
            if len(times) >= 2:
                result_fps = (len(times) - 1) / max(times[-1] - times[0], 1e-9)
            else:
                result_fps = 0.0
            age = now - self.last_update if self.last_update > 0 else -1.0
            return Snapshot(
                frame=self.frame,
                image_width=self.image_width,
                image_height=self.image_height,
                result_fps=result_fps,
                last_pipeline_ms=self.last_pipeline_ms,
                last_decode_ms=self.last_decode_ms,
                last_inference_ms=self.last_inference_ms,
                last_postprocess_ms=self.last_postprocess_ms,
                last_encode_ms=self.last_encode_ms,
                age=age,
                detections=list(self.detections),
                jpeg=self.jpeg,
            )

    def wait_for_jpeg(self, previous_frame: int, timeout: float = 2.0):
        with self.condition:
            if self.frame == previous_frame:
                self.condition.wait(timeout)
            return self.jpeg, self.frame


def softmax(x: np.ndarray, axis: int) -> np.ndarray:
    """数值稳定版 softmax，用于 YOLO11 DFL 后处理。"""
    x = x - np.max(x, axis=axis, keepdims=True)
    exp_x = np.exp(x)
    return exp_x / np.sum(exp_x, axis=axis, keepdims=True)


def dfl(position: np.ndarray) -> np.ndarray:
    """把 YOLO11 DFL 离散分布还原为四条边的距离。"""
    n, c, h, w = position.shape
    p_num = 4
    mc = c // p_num
    y = position.reshape(n, p_num, mc, h, w)
    y = softmax(y, axis=2)
    acc = np.arange(mc, dtype=np.float32).reshape(1, 1, mc, 1, 1)
    return (y * acc).sum(axis=2)


def box_process(position: np.ndarray) -> np.ndarray:
    grid_h, grid_w = position.shape[2:4]
    col, row = np.meshgrid(np.arange(grid_w), np.arange(grid_h))
    col = col.reshape(1, 1, grid_h, grid_w)
    row = row.reshape(1, 1, grid_h, grid_w)
    grid = np.concatenate((col, row), axis=1)
    stride = np.array([IMG_SIZE[1] // grid_h, IMG_SIZE[0] // grid_w], dtype=np.float32)
    stride = stride.reshape(1, 2, 1, 1)

    position = dfl(position)
    box_xy1 = grid + 0.5 - position[:, 0:2, :, :]
    box_xy2 = grid + 0.5 + position[:, 2:4, :, :]
    return np.concatenate((box_xy1 * stride, box_xy2 * stride), axis=1)


def sp_flatten(x: np.ndarray) -> np.ndarray:
    ch = x.shape[1]
    x = x.transpose(0, 2, 3, 1)
    return x.reshape(-1, ch)


def filter_boxes(
    boxes: np.ndarray,
    box_confidences: np.ndarray,
    box_class_probs: np.ndarray,
    threshold: float,
):
    box_confidences = box_confidences.reshape(-1)
    class_max_score = np.max(box_class_probs, axis=-1)
    classes = np.argmax(box_class_probs, axis=-1)
    keep = np.where(class_max_score * box_confidences >= threshold)
    return boxes[keep], classes[keep], (class_max_score * box_confidences)[keep]


def nms_boxes(boxes: np.ndarray, scores: np.ndarray, iou_threshold: float) -> np.ndarray:
    x1 = boxes[:, 0]
    y1 = boxes[:, 1]
    x2 = boxes[:, 2]
    y2 = boxes[:, 3]
    areas = (x2 - x1) * (y2 - y1)
    order = scores.argsort()[::-1]
    keep = []
    while order.size > 0:
        i = order[0]
        keep.append(i)
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        w = np.maximum(0.0, xx2 - xx1 + 1e-5)
        h = np.maximum(0.0, yy2 - yy1 + 1e-5)
        inter = w * h
        ovr = inter / (areas[i] + areas[order[1:]] - inter)
        order = order[np.where(ovr <= iou_threshold)[0] + 1]
    return np.array(keep, dtype=np.int32)


def post_process(outputs: Sequence[np.ndarray], confidence_threshold: float, iou_threshold: float):
    boxes, scores, classes_conf = [], [], []
    default_branch = 3
    pair_per_branch = len(outputs) // default_branch
    if pair_per_branch < 2:
        raise ValueError(f'unexpected output count: {len(outputs)}')

    for i in range(default_branch):
        boxes.append(box_process(outputs[pair_per_branch * i]))
        classes_conf.append(outputs[pair_per_branch * i + 1])
        scores.append(np.ones_like(outputs[pair_per_branch * i + 1][:, :1, :, :], dtype=np.float32))

    boxes = np.concatenate([sp_flatten(v) for v in boxes], axis=0)
    classes_conf = np.concatenate([sp_flatten(v) for v in classes_conf], axis=0)
    scores = np.concatenate([sp_flatten(v) for v in scores], axis=0)
    boxes, classes, scores = filter_boxes(boxes, scores, classes_conf, confidence_threshold)
    if boxes is None or len(boxes) == 0:
        return None, None, None

    nboxes, nclasses, nscores = [], [], []
    for class_id in set(classes.tolist()):
        inds = np.where(classes == class_id)
        b = boxes[inds]
        c_arr = classes[inds]
        s = scores[inds]
        keep = nms_boxes(b, s, iou_threshold)
        if len(keep) != 0:
            nboxes.append(b[keep])
            nclasses.append(c_arr[keep])
            nscores.append(s[keep])

    if not nboxes:
        return None, None, None
    return np.concatenate(nboxes, axis=0), np.concatenate(nclasses, axis=0), np.concatenate(nscores, axis=0)


def letterbox(image: np.ndarray):
    """按模型输入尺寸做等比缩放和灰边填充。"""
    shape = image.shape[:2]
    new_w, new_h = IMG_SIZE
    ratio = min(new_w / shape[1], new_h / shape[0])
    resized_w = int(round(shape[1] * ratio))
    resized_h = int(round(shape[0] * ratio))
    pad_w = new_w - resized_w
    pad_h = new_h - resized_h
    pad_x = pad_w / 2
    pad_y = pad_h / 2
    if (shape[1], shape[0]) != (resized_w, resized_h):
        image = cv2.resize(image, (resized_w, resized_h), interpolation=cv2.INTER_LINEAR)
    top = int(round(pad_y - 0.1))
    bottom = int(round(pad_y + 0.1))
    left = int(round(pad_x - 0.1))
    right = int(round(pad_x + 0.1))
    image = cv2.copyMakeBorder(image, top, bottom, left, right, cv2.BORDER_CONSTANT, value=(0, 0, 0))
    return image, ratio, left, top


def scale_boxes(boxes: np.ndarray, ratio: float, pad_x: int, pad_y: int, orig_w: int, orig_h: int) -> np.ndarray:
    boxes = boxes.copy().astype(np.float32)
    boxes[:, [0, 2]] -= pad_x
    boxes[:, [1, 3]] -= pad_y
    boxes[:, [0, 2]] /= ratio
    boxes[:, [1, 3]] /= ratio
    boxes[:, 0] = np.clip(boxes[:, 0], 0, orig_w - 1)
    boxes[:, 1] = np.clip(boxes[:, 1], 0, orig_h - 1)
    boxes[:, 2] = np.clip(boxes[:, 2], 0, orig_w - 1)
    boxes[:, 3] = np.clip(boxes[:, 3], 0, orig_h - 1)
    return boxes


class RKNNModel:
    """RKNNLite 模型封装，负责初始化 NPU runtime 和执行 inference。"""

    def __init__(self, model_path: str):
        self.rknn = RKNNLite()
        ret = self.rknn.load_rknn(model_path)
        if ret != 0:
            raise RuntimeError(f'load_rknn failed: {ret}')
        ret = self.rknn.init_runtime()
        if ret != 0:
            raise RuntimeError(f'init_runtime failed: {ret}')

    def run(self, image_rgb: np.ndarray):
        image_rgb = np.expand_dims(np.ascontiguousarray(image_rgb), axis=0)
        outputs = self.rknn.inference(inputs=[image_rgb])
        if outputs is None:
            raise RuntimeError('RKNN inference returned None')
        return outputs

    def release(self):
        self.rknn.release()


def draw_detections(image: np.ndarray, detections: Sequence[Detection], result_fps: float) -> None:
    for det in detections:
        x1 = int(det.x)
        y1 = int(det.y)
        x2 = int(det.x + det.width)
        y2 = int(det.y + det.height)
        label = f'{det.label} {det.score * 100:.0f}%'
        cv2.rectangle(image, (x1, y1), (x2, y2), (0, 255, 102), 2)
        (tw, th), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.52, 1)
        y_text = max(0, y1 - th - baseline - 4)
        cv2.rectangle(image, (x1, y_text), (x1 + tw + 8, y_text + th + baseline + 6), (0, 0, 0), -1)
        cv2.putText(image, label, (x1 + 4, y_text + th + 2), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (0, 255, 102), 1, cv2.LINE_AA)
    cv2.putText(image, f'PY YOLO FPS: {result_fps:.1f}', (12, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 102), 2)


def snapshot_to_dict(snapshot: Snapshot):
    return {
        'frame': snapshot.frame,
        'image_width': snapshot.image_width,
        'image_height': snapshot.image_height,
        'result_fps': round(snapshot.result_fps, 3),
        'fps_window': 'completed Python inference frames over recent sliding window',
        'last_pipeline_ms': round(snapshot.last_pipeline_ms, 3),
        'last_decode_ms': round(snapshot.last_decode_ms, 3),
        'last_inference_ms': round(snapshot.last_inference_ms, 3),
        'last_postprocess_ms': round(snapshot.last_postprocess_ms, 3),
        'last_encode_ms': round(snapshot.last_encode_ms, 3),
        'age': round(snapshot.age, 3),
        'detections': [det.__dict__ for det in snapshot.detections],
    }


class ResultHandler(BaseHTTPRequestHandler):
    server_version = 'yolo-web-py/0.1'

    def do_GET(self):
        if self.path in ('/', '/index.html'):
            self.send_index()
        elif self.path == '/stream.mjpg':
            self.send_stream()
        elif self.path == '/snapshot.jpg':
            self.send_snapshot()
        elif self.path == '/detections':
            self.send_json()
        elif self.path == '/health':
            self.send_health()
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def log_message(self, fmt, *args):
        self.server.node.get_logger().debug(fmt % args)

    def send_index(self):
        body = b'''<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>YOLO Python Result Stream</title>
  <style>
    body{margin:0;background:#111;color:#eee;font-family:system-ui,sans-serif;}
    main{max-width:1280px;margin:0 auto;padding:20px;}
    img{display:block;width:100%;height:auto;background:#000;}
    code{color:#8fd;}
  </style>
</head>
<body>
  <main>
    <h1>YOLO Python Result Stream</h1>
    <p>Server-side boxed MJPEG result: <code>/stream.mjpg</code></p>
    <img src="/stream.mjpg" alt="YOLO Python result stream">
  </main>
</body>
</html>'''
        self.send_response(HTTPStatus.OK)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        self.wfile.write(body)

    def send_health(self):
        snapshot = self.server.shared.snapshot(self.server.fps_window_seconds)
        body = (
            f'frames={snapshot.frame} age={snapshot.age:.3f} result_fps={snapshot.result_fps:.3f} '
            f'last_pipeline_ms={snapshot.last_pipeline_ms:.3f} last_decode_ms={snapshot.last_decode_ms:.3f} '
            f'last_inference_ms={snapshot.last_inference_ms:.3f} last_postprocess_ms={snapshot.last_postprocess_ms:.3f} '
            f'last_encode_ms={snapshot.last_encode_ms:.3f}\n'
        ).encode()
        self.send_response(HTTPStatus.OK)
        self.send_header('Content-Type', 'text/plain; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        self.wfile.write(body)

    def send_json(self):
        body = json.dumps(snapshot_to_dict(self.server.shared.snapshot(self.server.fps_window_seconds))).encode()
        self.send_response(HTTPStatus.OK)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        self.wfile.write(body)

    def send_snapshot(self):
        snapshot = self.server.shared.snapshot(self.server.fps_window_seconds)
        if snapshot.jpeg is None:
            self.send_error(HTTPStatus.SERVICE_UNAVAILABLE, 'No result frame received yet')
            return
        self.send_response(HTTPStatus.OK)
        self.send_header('Content-Type', 'image/jpeg')
        self.send_header('Content-Length', str(len(snapshot.jpeg)))
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        self.wfile.write(snapshot.jpeg)

    def send_stream(self):
        self.send_response(HTTPStatus.OK)
        self.send_header('Age', '0')
        self.send_header('Cache-Control', 'no-cache, private')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame')
        self.end_headers()

        frame = -1
        while self.server.running:
            jpeg, new_frame = self.server.shared.wait_for_jpeg(frame)
            if jpeg is None or new_frame == frame:
                continue
            frame = new_frame
            try:
                self.wfile.write(b'--frame\r\n')
                self.wfile.write(b'Content-Type: image/jpeg\r\n')
                self.wfile.write(f'Content-Length: {len(jpeg)}\r\n\r\n'.encode())
                self.wfile.write(jpeg)
                self.wfile.write(b'\r\n')
            except (BrokenPipeError, ConnectionResetError, socket.timeout):
                break


class YoloWebPyNode(Node):
    """Python 服务端画框版 YOLO Web 节点。"""

    def __init__(self):
        super().__init__('yolo_web_py_node')
        self.input_topic = self.declare_parameter('input_topic', '/camera/image_mjpeg').value
        self.model_path = self.declare_parameter(
            'model_path',
            '/home/lckfb/workspace/yolo/yolo_web_py_ws/models/yolo11.rknn',
        ).value
        self.port = int(self.declare_parameter('port', 8090).value)
        self.confidence_threshold = float(self.declare_parameter('confidence_threshold', 0.25).value)
        self.iou_threshold = float(self.declare_parameter('iou_threshold', 0.45).value)
        self.jpeg_quality = int(self.declare_parameter('jpeg_quality', 65).value)
        self.fps_window_seconds = float(self.declare_parameter('fps_window_seconds', 2.0).value)
        self.detections_topic = self.declare_parameter('detections_topic', '/yolo/detections').value

        self.labels = list(DEFAULT_CLASSES)
        self.model = RKNNModel(self.model_path)
        self.shared = SharedResult()
        self.subscription = self.create_subscription(
            CompressedImage,
            self.input_topic,
            self.on_image,
            10,
        )
        self.detections_publisher = self.create_publisher(Detection2DArray, self.detections_topic, 10)

        self.httpd = ThreadingHTTPServer(('0.0.0.0', self.port), ResultHandler)
        self.httpd.node = self
        self.httpd.shared = self.shared
        self.httpd.fps_window_seconds = self.fps_window_seconds
        self.httpd.running = True
        self.http_thread = threading.Thread(target=self.httpd.serve_forever, name='yolo-web-py-http', daemon=True)
        self.http_thread.start()
        self.get_logger().info(
            f'Serving Python YOLO result stream at http://0.0.0.0:{self.port}/; '
            f'publishing detections on {self.detections_topic}'
        )

    def publish_detections(self, msg: CompressedImage, detections: Sequence[Detection]) -> None:
        """把内部左上角坐标检测框转换为 vision_msgs Detection2DArray。"""
        result_msg = Detection2DArray()
        result_msg.header = msg.header
        for det in detections:
            detection_msg = Detection2D()
            detection_msg.header = msg.header
            detection_msg.id = det.label
            detection_msg.bbox.center.position.x = det.x + det.width * 0.5
            detection_msg.bbox.center.position.y = det.y + det.height * 0.5
            detection_msg.bbox.center.theta = 0.0
            detection_msg.bbox.size_x = det.width
            detection_msg.bbox.size_y = det.height

            hypothesis = ObjectHypothesisWithPose()
            hypothesis.hypothesis.class_id = str(det.class_id)
            hypothesis.hypothesis.score = float(det.score)
            detection_msg.results.append(hypothesis)
            result_msg.detections.append(detection_msg)
        self.detections_publisher.publish(result_msg)

    def on_image(self, msg: CompressedImage) -> None:
        """处理一帧摄像头压缩图像，并输出带框 JPEG、JSON 和 ROS 检测话题。"""
        pipeline_start = time.perf_counter()
        try:
            decode_start = time.perf_counter()
            frame = cv2.imdecode(np.frombuffer(msg.data, dtype=np.uint8), cv2.IMREAD_COLOR)
            if frame is None:
                raise RuntimeError('JPEG decode failed')
            decode_ms = (time.perf_counter() - decode_start) * 1000.0

            orig_h, orig_w = frame.shape[:2]
            resized, ratio, pad_x, pad_y = letterbox(frame)
            rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)

            inference_start = time.perf_counter()
            outputs = self.model.run(rgb)
            inference_ms = (time.perf_counter() - inference_start) * 1000.0

            post_start = time.perf_counter()
            boxes, classes, scores = post_process(outputs, self.confidence_threshold, self.iou_threshold)
            detections: List[Detection] = []
            if boxes is not None:
                real_boxes = scale_boxes(boxes, ratio, pad_x, pad_y, orig_w, orig_h)
                for box, class_id, score in zip(real_boxes, classes, scores):
                    x1, y1, x2, y2 = [float(v) for v in box]
                    label = self.labels[int(class_id)] if 0 <= int(class_id) < len(self.labels) else str(int(class_id))
                    detections.append(Detection(int(class_id), label, float(score), x1, y1, max(0.0, x2 - x1), max(0.0, y2 - y1)))

            fps_before_draw = self.shared.snapshot(self.fps_window_seconds).result_fps
            draw_detections(frame, detections, fps_before_draw)
            post_ms = (time.perf_counter() - post_start) * 1000.0

            encode_start = time.perf_counter()
            ok, encoded = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality])
            if not ok:
                raise RuntimeError('JPEG encode failed')
            encode_ms = (time.perf_counter() - encode_start) * 1000.0
            total_ms = (time.perf_counter() - pipeline_start) * 1000.0

            self.shared.update(
                orig_w,
                orig_h,
                encoded.tobytes(),
                detections,
                (total_ms, decode_ms, inference_ms, post_ms, encode_ms),
                self.fps_window_seconds,
            )
            self.publish_detections(msg, detections)
        except Exception as exc:  # noqa: BLE001
            self.get_logger().error(f'Python YOLO callback failed: {exc}')

    def destroy_node(self):
        if hasattr(self, 'httpd'):
            self.httpd.running = False
            self.httpd.shutdown()
            self.httpd.server_close()
        if hasattr(self, 'model'):
            self.model.release()
        super().destroy_node()


def main():
    rclpy.init()
    node = YoloWebPyNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
