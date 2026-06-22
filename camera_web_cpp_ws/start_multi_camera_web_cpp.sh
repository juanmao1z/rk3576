#!/usr/bin/env bash
# 双路 C++ 摄像头 Web 服务启动脚本。
# 默认把 4K USB Camera 作为 front，把 Integrated_Webcam_HD 作为 left。
set -eo pipefail

FRONT_DEVICE=${FRONT_DEVICE:-/dev/video73}
LEFT_DEVICE=${LEFT_DEVICE:-/dev/video75}
CAMERA_WIDTH=${CAMERA_WIDTH:-640}
CAMERA_HEIGHT=${CAMERA_HEIGHT:-480}
CAMERA_FPS=${CAMERA_FPS:-25}
FRONT_PORT=${FRONT_PORT:-8081}
LEFT_PORT=${LEFT_PORT:-8082}

usage() {
  cat <<'EOF'
Usage: start_multi_camera_web_cpp.sh [options]

Options:
  --front-device PATH   Front camera V4L2 node.
  --left-device PATH    Left camera V4L2 node.
  --size WIDTHxHEIGHT   Capture size, for example 640x480.
  --width WIDTH         Capture width.
  --height HEIGHT       Capture height.
  --fps FPS             Capture FPS.
  --front-port PORT     Front camera HTTP port.
  --left-port PORT      Left camera HTTP port.
  -h, --help            Show this help.

Defaults:
  front=/dev/video73, left=/dev/video75, 640x480@25, ports 8081/8082.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --front-device)
      FRONT_DEVICE=$2
      shift 2
      ;;
    --left-device)
      LEFT_DEVICE=$2
      shift 2
      ;;
    --size)
      if [[ $# -lt 2 || "$2" != *x* ]]; then
        echo "Invalid --size value. Use WIDTHxHEIGHT, for example 640x480." >&2
        exit 1
      fi
      CAMERA_WIDTH=${2%x*}
      CAMERA_HEIGHT=${2#*x}
      shift 2
      ;;
    --width)
      CAMERA_WIDTH=$2
      shift 2
      ;;
    --height)
      CAMERA_HEIGHT=$2
      shift 2
      ;;
    --fps)
      CAMERA_FPS=$2
      shift 2
      ;;
    --front-port)
      FRONT_PORT=$2
      shift 2
      ;;
    --left-port)
      LEFT_PORT=$2
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

cd /home/lckfb/workspace/ros/camera_web_cpp_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash

exec ros2 launch camera_web_cpp multi_camera_web_cpp.launch.py \
  front_device:="${FRONT_DEVICE}" \
  left_device:="${LEFT_DEVICE}" \
  width:="${CAMERA_WIDTH}" \
  height:="${CAMERA_HEIGHT}" \
  fps:="${CAMERA_FPS}" \
  front_port:="${FRONT_PORT}" \
  left_port:="${LEFT_PORT}"
