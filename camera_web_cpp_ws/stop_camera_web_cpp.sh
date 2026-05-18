#!/usr/bin/env bash
# C++ 摄像头 Web 服务关闭脚本。
# 使用进程名匹配清理 ROS launch、采集组件和 Web 转发组件，允许重复执行。
set -eo pipefail

pkill -TERM -f '[r]os2 launch camera_web_cpp' || true
pkill -TERM -f '[c]amera_mjpeg_publisher' || true
pkill -TERM -f '[c]ompressed_mjpeg_server' || true
