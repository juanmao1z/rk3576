#!/usr/bin/env bash
# Python 摄像头 Web 服务启动脚本。
# 该旧版链路会启动 camera_publisher 与 mjpeg_server 两个 Python ROS2 节点。
set -eo pipefail

cd /home/lckfb/workspace/ros/camera_web_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash

exec ros2 launch camera_web_bridge camera_web.launch.py \
  device:=/dev/video73 \
  width:=1280 \
  height:=720 \
  fps:=30 \
  port:=8080
