#!/usr/bin/env bash
# 单独启动无人机 YOLO C++ Canvas 节点。
# 使用前需要先启动 camera_web_cpp，保证 /camera/image_mjpeg 和 8081 视频流可用。
set -eo pipefail

YOLO_WS=/home/lckfb/workspace/drone_yolo_web_cpp_ws
RKNN_MODEL=${RKNN_MODEL:-${YOLO_WS}/models/yolo11n.rknn}
DETECTION_LABELS=${DETECTION_LABELS:-drone}

cd "${YOLO_WS}"
source /opt/ros/jazzy/setup.bash
source install/setup.bash

if [[ ! -f "${RKNN_MODEL}" ]]; then
  echo "RKNN model not found: ${RKNN_MODEL}" >&2
  exit 1
fi

# 默认标签为 drone；多类别无人机模型可通过 DETECTION_LABELS 传逗号分隔标签。
exec ros2 launch drone_yolo_web_cpp drone_yolo_web_cpp.launch.py \
  input_topic:=/camera/image_mjpeg \
  model_path:="${RKNN_MODEL}" \
  labels:="${DETECTION_LABELS}" \
  port:=8092 \
  camera_url:=http://127.0.0.1:8081/stream.mjpg \
  detections_topic:=/yolo/detections \
  fps_window_seconds:=2.0
