#!/usr/bin/env bash
# 单独启动通用 YOLO C++ Canvas 节点。
# 使用前需要先启动 camera_web_cpp，保证 /camera/image_mjpeg 和 8081 视频流可用。
set -eo pipefail

YOLO_WS=/home/lckfb/workspace/yolo/yolo_web_cpp_ws
RKNN_MODEL=${RKNN_MODEL:-/home/lckfb/workspace/yolo/yolo_web_cpp_ws/models/yolo11.rknn}
DETECTION_LABELS=${DETECTION_LABELS:-coco}

cd "${YOLO_WS}"
source /opt/ros/jazzy/setup.bash
source install/setup.bash

if [[ ! -f "${RKNN_MODEL}" ]]; then
  echo "RKNN model not found: ${RKNN_MODEL}" >&2
  exit 1
fi

# labels:=coco 会在节点内展开为 COCO 80 类；自定义模型可传逗号分隔标签。
exec ros2 launch yolo_web_cpp yolo_web_cpp.launch.py \
  input_topic:=/camera/image_mjpeg \
  model_path:="${RKNN_MODEL}" \
  labels:="${DETECTION_LABELS}" \
  port:=8092 \
  camera_url:=http://127.0.0.1:8081/stream.mjpg \
  detections_topic:=/yolo/detections \
  fps_window_seconds:=2.0
