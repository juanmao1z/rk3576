#!/usr/bin/env bash
# 单独启动 YOLO Python 服务端画框节点。
# 使用前需要先启动 camera_web_cpp，保证 /camera/image_mjpeg 可用。
set -eo pipefail

YOLO_WS=/home/lckfb/workspace/yolo/yolo_web_py_ws
RKNN_MODEL=${YOLO_WS}/models/yolo11.rknn

cd "${YOLO_WS}"
source /opt/ros/jazzy/setup.bash
source install/setup.bash

if [[ ! -f "${RKNN_MODEL}" ]]; then
  echo "RKNN model not found: ${RKNN_MODEL}" >&2
  exit 1
fi

# Python 版会重新编码带框 JPEG，因此保留 jpeg_quality 参数。
exec ros2 launch yolo_web_py yolo_web_py.launch.py \
  input_topic:=/camera/image_mjpeg \
  model_path:="${RKNN_MODEL}" \
  port:=8090 \
  jpeg_quality:=65 \
  detections_topic:=/yolo/detections \
  fps_window_seconds:=2.0
