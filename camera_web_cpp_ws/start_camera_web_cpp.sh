#!/usr/bin/env bash
# C++ 摄像头 Web 服务启动脚本。
# 该脚本在开发板上启动 camera_web_cpp ROS2 包，并负责解析摄像头分辨率、
# 帧率、设备路径和 HTTP 端口等运行参数。
set -eo pipefail

CAMERA_DEVICE=${CAMERA_DEVICE:-/dev/video73}
CAMERA_WIDTH=${CAMERA_WIDTH:-640}
CAMERA_HEIGHT=${CAMERA_HEIGHT:-480}
CAMERA_FPS=${CAMERA_FPS:-}
CAMERA_PORT=${CAMERA_PORT:-8081}

usage() {
  cat <<'EOF'
Usage: start_camera_web_cpp.sh [options]

Options:
  --size WIDTHxHEIGHT   Camera capture size, for example 640x480 or 1280x720.
  --width WIDTH         Camera capture width.
  --height HEIGHT       Camera capture height.
  --fps FPS             Camera capture FPS.
  --device PATH         V4L2 device path.
  --port PORT           HTTP port.
  -h, --help            Show this help.

Defaults: /dev/video73 640x480@25 on port 8081.
When --fps is omitted, 1280x720 uses 30 FPS and other sizes use 25 FPS.
Environment overrides: CAMERA_DEVICE, CAMERA_WIDTH, CAMERA_HEIGHT, CAMERA_FPS, CAMERA_PORT.
EOF
}

# 命令行参数优先级高于环境变量，便于 Windows ADB 入口直接覆盖运行模式。
while [[ $# -gt 0 ]]; do
  case "$1" in
    --size)
      if [[ $# -lt 2 || "$2" != *x* ]]; then
        echo "Invalid --size value. Use WIDTHxHEIGHT, for example 1280x720." >&2
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
    --device)
      CAMERA_DEVICE=$2
      shift 2
      ;;
    --port)
      CAMERA_PORT=$2
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

case "${CAMERA_WIDTH}x${CAMERA_HEIGHT}" in
  640x480|1280x720) ;;
  *)
    echo "Warning: untested camera size ${CAMERA_WIDTH}x${CAMERA_HEIGHT}; continuing." >&2
    ;;
esac

# 开发板摄像头在 1280x720 下硬件能力是 30 FPS；其余模式默认保守使用 25 FPS。
if [[ -z "${CAMERA_FPS}" ]]; then
  case "${CAMERA_WIDTH}x${CAMERA_HEIGHT}" in
    1280x720)
      CAMERA_FPS=30
      ;;
    *)
      CAMERA_FPS=25
      ;;
  esac
fi

cd /home/lckfb/workspace/ros/camera_web_cpp_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash

exec ros2 launch camera_web_cpp camera_web_cpp.launch.py \
  device:="${CAMERA_DEVICE}" \
  width:="${CAMERA_WIDTH}" \
  height:="${CAMERA_HEIGHT}" \
  fps:="${CAMERA_FPS}" \
  port:="${CAMERA_PORT}"
