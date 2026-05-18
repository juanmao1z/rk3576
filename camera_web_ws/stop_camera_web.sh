#!/usr/bin/env bash
# Python 摄像头 Web 服务关闭脚本。
# 使用宽松进程匹配，便于重复执行和从 Windows ADB 入口调用。
set -eo pipefail

pkill -TERM -f '[r]os2 launch camera_web_bridge' || true
pkill -TERM -f '[c]amera_publisher' || true
pkill -TERM -f '[m]jpeg_server' || true
