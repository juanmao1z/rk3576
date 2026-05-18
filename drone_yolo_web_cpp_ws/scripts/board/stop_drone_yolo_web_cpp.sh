#!/usr/bin/env bash
# 单独关闭无人机 YOLO C++ Canvas 节点，不影响摄像头服务。
set -eo pipefail

pkill -f drone_yolo_web_cpp_node || true
pkill -f "ros2 launch drone_yolo_web_cpp" || true
