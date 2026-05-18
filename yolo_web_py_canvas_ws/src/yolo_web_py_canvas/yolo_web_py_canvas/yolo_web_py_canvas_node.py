"""Python RKNN YOLO11 浏览器 Canvas 叠框节点。

该节点订阅 /camera/image_mjpeg 并用 RKNNLite 推理，只输出检测 JSON 和
ROS 检测话题；浏览器页面直接显示 8081 原始 MJPEG 流，再用 Canvas 叠框。
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import html
import json
import threading
import time
from typing import List, Sequence, Tuple

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
    """HTTP 线程读取的最新检测结果快照。"""

    frame: int
    image_width: int
    image_height: int
    result_fps: float
    last_pipeline_ms: float
    last_decode_ms: float
    last_inference_ms: float
    last_postprocess_ms: float
    age: float
    detections: List[Detection]


class SharedDetections:
    """ROS 推理线程和 HTTP 线程之间共享最新检测结果。"""

    def __init__(self):
        self.condition = threading.Condition()
        self.frame = 0
        self.image_width = 0
        self.image_height = 0
        self.detections: List[Detection] = []
        self.frame_times: deque[float] = deque()
        self.last_update = 0.0
        self.last_pipeline_ms = 0.0
        self.last_decode_ms = 0.0
        self.last_inference_ms = 0.0
        self.last_postprocess_ms = 0.0

    def update(
        self,
        image_width: int,
        image_height: int,
        detections: List[Detection],
        timings: Tuple[float, float, float, float],
        fps_window_seconds: float,
    ) -> None:
        """保存已完成推理的一帧检测结果，并唤醒等待中的 HTTP 客户端。"""
        now = time.monotonic()
        with self.condition:
            self.frame += 1
            self.image_width = image_width
            self.image_height = image_height
            self.detections = detections
            self.last_update = now
            (
                self.last_pipeline_ms,
                self.last_decode_ms,
                self.last_inference_ms,
                self.last_postprocess_ms,
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
            result_fps = (len(times) - 1) / max(times[-1] - times[0], 1e-9) if len(times) >= 2 else 0.0
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
                age=age,
                detections=list(self.detections),
            )


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


def filter_boxes(boxes: np.ndarray, box_confidences: np.ndarray, box_class_probs: np.ndarray, threshold: float):
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
        keep = nms_boxes(boxes[inds], scores[inds], iou_threshold)
        if len(keep) != 0:
            nboxes.append(boxes[inds][keep])
            nclasses.append(classes[inds][keep])
            nscores.append(scores[inds][keep])
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
        'age': round(snapshot.age, 3),
        'detections': [det.__dict__ for det in snapshot.detections],
    }


class OverlayHandler(BaseHTTPRequestHandler):
    server_version = 'yolo-web-py-canvas/0.1'

    def do_GET(self):
        if self.path in ('/', '/index.html'):
            self.send_index()
        elif self.path == '/detections':
            self.send_json()
        elif self.path == '/health':
            self.send_health()
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def log_message(self, fmt, *args):
        self.server.node.get_logger().debug(fmt % args)

    def send_index(self):
        camera_url = html.escape(self.server.camera_url, quote=True)
        body = f'''<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>YOLO Python Canvas Overlay</title>
  <style>
    body{{margin:0;background:#111;color:#eee;font-family:system-ui,sans-serif;}}
    main{{max-width:1280px;margin:0 auto;padding:20px;}}
    .viewer{{position:relative;background:#000;line-height:0;}}
    img{{display:block;width:100%;height:auto;background:#000;}}
    canvas{{position:absolute;inset:0;width:100%;height:100%;pointer-events:none;}}
    .hud{{position:absolute;left:12px;top:12px;padding:8px 10px;border-radius:4px;background:rgba(0,0,0,.72);color:#00ff66;font:600 15px/1.45 ui-monospace,monospace;white-space:pre;line-height:1.45;}}
    code{{color:#8fd;}}
  </style>
</head>
<body>
  <main>
    <h1>YOLO Python Canvas Overlay</h1>
    <p>Video: <code>{camera_url}</code> | Detections: <code>/detections</code></p>
    <div class="viewer">
      <img id="stream" src="{camera_url}" alt="camera stream">
      <canvas id="overlay"></canvas>
      <div class="hud" id="hud">Waiting for detections...</div>
    </div>
  </main>
  <script>
    const img = document.getElementById('stream');
    const canvas = document.getElementById('overlay');
    const ctx = canvas.getContext('2d');
    const hud = document.getElementById('hud');
    function resizeCanvas() {{
      const rect = img.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      const width = Math.max(1, Math.round(rect.width * dpr));
      const height = Math.max(1, Math.round(rect.height * dpr));
      if (canvas.width !== width || canvas.height !== height) {{
        canvas.width = width;
        canvas.height = height;
      }}
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      return rect;
    }}
    function draw(data) {{
      const rect = resizeCanvas();
      ctx.clearRect(0, 0, rect.width, rect.height);
      const scaleX = rect.width / Math.max(1, data.image_width || img.naturalWidth || 1);
      const scaleY = rect.height / Math.max(1, data.image_height || img.naturalHeight || 1);
      ctx.lineWidth = 2;
      ctx.font = '14px ui-monospace, monospace';
      for (const det of data.detections || []) {{
        const x = det.x * scaleX;
        const y = det.y * scaleY;
        const w = det.width * scaleX;
        const h = det.height * scaleY;
        const label = `${{det.label}} ${{(det.score * 100).toFixed(0)}}%`;
        ctx.strokeStyle = '#00ff66';
        ctx.fillStyle = 'rgba(0,0,0,.74)';
        ctx.strokeRect(x, y, w, h);
        const textWidth = ctx.measureText(label).width + 10;
        ctx.fillRect(x, Math.max(0, y - 22), textWidth, 22);
        ctx.fillStyle = '#00ff66';
        ctx.fillText(label, x + 5, Math.max(14, y - 7));
      }}
      hud.textContent =
        `DETECTIONS: ${{(data.detections || []).length}}\\n` +
        `PY FPS: ${{(data.result_fps || 0).toFixed(1)}}\\n` +
        `PIPELINE: ${{(data.last_pipeline_ms || 0).toFixed(1)}} ms\\n` +
        `RKNN: ${{(data.last_inference_ms || 0).toFixed(1)}} ms\\n` +
        `AGE: ${{(data.age || 0).toFixed(2)}} s`;
    }}
    async function tick() {{
      try {{
        const res = await fetch('/detections', {{cache: 'no-store'}});
        draw(await res.json());
      }} catch (error) {{
        hud.textContent = 'Detection service unavailable';
      }}
      setTimeout(tick, 80);
    }}
    window.addEventListener('resize', () => fetch('/detections', {{cache:'no-store'}}).then(r => r.json()).then(draw).catch(() => {{}}));
    tick();
  </script>
</body>
</html>'''.encode()
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
            f'last_inference_ms={snapshot.last_inference_ms:.3f} last_postprocess_ms={snapshot.last_postprocess_ms:.3f}\n'
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


class YoloWebPyCanvasNode(Node):
    """Python Canvas 版 YOLO Web 节点。"""

    def __init__(self):
        super().__init__('yolo_web_py_canvas_node')
        self.input_topic = self.declare_parameter('input_topic', '/camera/image_mjpeg').value
        self.model_path = self.declare_parameter(
            'model_path',
            '/home/lckfb/workspace/yolo/yolo_web_py_canvas_ws/models/yolo11.rknn',
        ).value
        self.port = int(self.declare_parameter('port', 8091).value)
        self.camera_url = self.declare_parameter('camera_url', 'http://127.0.0.1:8081/stream.mjpg').value
        self.confidence_threshold = float(self.declare_parameter('confidence_threshold', 0.25).value)
        self.iou_threshold = float(self.declare_parameter('iou_threshold', 0.45).value)
        self.fps_window_seconds = float(self.declare_parameter('fps_window_seconds', 2.0).value)
        self.detections_topic = self.declare_parameter('detections_topic', '/yolo/detections').value

        self.labels = list(DEFAULT_CLASSES)
        self.model = RKNNModel(self.model_path)
        self.shared = SharedDetections()
        self.subscription = self.create_subscription(CompressedImage, self.input_topic, self.on_image, 10)
        self.detections_publisher = self.create_publisher(Detection2DArray, self.detections_topic, 10)

        self.httpd = ThreadingHTTPServer(('0.0.0.0', self.port), OverlayHandler)
        self.httpd.node = self
        self.httpd.shared = self.shared
        self.httpd.camera_url = self.camera_url
        self.httpd.fps_window_seconds = self.fps_window_seconds
        self.http_thread = threading.Thread(target=self.httpd.serve_forever, name='yolo-web-py-canvas-http', daemon=True)
        self.http_thread.start()
        self.get_logger().info(
            f'Serving Python YOLO Canvas overlay at http://0.0.0.0:{self.port}/; '
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
        """处理一帧摄像头压缩图像，并输出 JSON 和 ROS 检测话题。"""
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
            post_ms = (time.perf_counter() - post_start) * 1000.0
            total_ms = (time.perf_counter() - pipeline_start) * 1000.0
            self.shared.update(orig_w, orig_h, detections, (total_ms, decode_ms, inference_ms, post_ms), self.fps_window_seconds)
            self.publish_detections(msg, detections)
        except Exception as exc:  # noqa: BLE001
            self.get_logger().error(f'Python Canvas YOLO callback failed: {exc}')

    def destroy_node(self):
        if hasattr(self, 'httpd'):
            self.httpd.shutdown()
            self.httpd.server_close()
        if hasattr(self, 'model'):
            self.model.release()
        super().destroy_node()


def main():
    rclpy.init()
    node = YoloWebPyCanvasNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
