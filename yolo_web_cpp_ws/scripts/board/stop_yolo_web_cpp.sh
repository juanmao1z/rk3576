#!/usr/bin/env bash
# 单独关闭通用 YOLO C++ Canvas 节点，不影响摄像头服务。
set -eo pipefail

pkill -f yolo_web_cpp_node || true
pkill -f "ros2 launch yolo_web_cpp" || true
