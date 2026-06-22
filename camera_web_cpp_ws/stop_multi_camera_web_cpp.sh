#!/usr/bin/env bash
# 双路 C++ 摄像头 Web 服务关闭脚本。
# 允许重复执行，未运行的进程会被忽略。
set -eo pipefail

pkill -TERM -f '[r]os2 launch camera_web_cpp multi_camera_web_cpp.launch.py' || true
pkill -TERM -f '[f]ront_camera_web_cpp_container' || true
pkill -TERM -f '[l]eft_camera_web_cpp_container' || true
pkill -TERM -f '[c]amera_web_cpp_container' || true
