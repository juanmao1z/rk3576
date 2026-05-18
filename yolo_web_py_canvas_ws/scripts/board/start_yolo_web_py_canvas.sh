#!/usr/bin/env bash
# 单独启动 YOLO Python Canvas 节点。
# 使用前需要先启动 camera_web_cpp，保证 /camera/image_mjpeg 和 8081 视频流可用。
set -eo pipefail

YOLO_WS=/home/lckfb/workspace/yolo/yolo_web_py_canvas_ws
RKNN_MODEL=${YOLO_WS}/models/yolo11.rknn

cd "${YOLO_WS}"
source /opt/ros/jazzy/setup.bash
source install/setup.bash

if [[ ! -f "${RKNN_MODEL}" ]]; then
  echo "RKNN model not found: ${RKNN_MODEL}" >&2
  exit 1
fi

# Canvas 版不生成带框 MJPEG，只输出检测 JSON 和 ROS 检测话题。
exec ros2 launch yolo_web_py_canvas yolo_web_py_canvas.launch.py \
  input_topic:=/camera/image_mjpeg \
  model_path:="${RKNN_MODEL}" \
  port:=8091 \
  camera_url:=http://127.0.0.1:8081/stream.mjpg \
  detections_topic:=/yolo/detections \
  fps_window_seconds:=2.0
