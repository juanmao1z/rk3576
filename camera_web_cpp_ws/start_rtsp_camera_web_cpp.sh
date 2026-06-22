#!/usr/bin/env bash
# C++ RTSP 摄像头 Web 服务启动脚本。
set -eo pipefail

RTSP_URL=${RTSP_URL:-}
CAMERA_WIDTH=${CAMERA_WIDTH:-1280}
CAMERA_HEIGHT=${CAMERA_HEIGHT:-960}
CAMERA_FPS=${CAMERA_FPS:-25}
CAMERA_PORT=${CAMERA_PORT:-8081}
JPEG_QUALITY=${JPEG_QUALITY:-85}

usage() {
  cat <<'EOF'
Usage: start_rtsp_camera_web_cpp.sh --rtsp-url URL [options]

Options:
  --rtsp-url URL        RTSP camera URL.
  --size WIDTHxHEIGHT   Output size, for example 1280x960.
  --width WIDTH         Output width.
  --height HEIGHT       Output height.
  --fps FPS             Target FPS metadata.
  --jpeg-quality VALUE  JPEG quality, 1-100.
  --port PORT           HTTP port.
  -h, --help            Show this help.

Environment overrides: RTSP_URL, CAMERA_WIDTH, CAMERA_HEIGHT, CAMERA_FPS, CAMERA_PORT, JPEG_QUALITY.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --rtsp-url)
      RTSP_URL=$2
      shift 2
      ;;
    --size)
      if [[ $# -lt 2 || "$2" != *x* ]]; then
        echo "Invalid --size value. Use WIDTHxHEIGHT, for example 1280x960." >&2
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
    --jpeg-quality)
      JPEG_QUALITY=$2
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

if [[ -z "${RTSP_URL}" ]]; then
  echo "RTSP URL is required. Pass --rtsp-url or set RTSP_URL." >&2
  exit 1
fi

cd /home/lckfb/workspace/ros/camera_web_cpp_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash

exec ros2 launch camera_web_cpp rtsp_camera_web_cpp.launch.py \
  rtsp_url:="${RTSP_URL}" \
  width:="${CAMERA_WIDTH}" \
  height:="${CAMERA_HEIGHT}" \
  fps:="${CAMERA_FPS}" \
  jpeg_quality:="${JPEG_QUALITY}" \
  port:="${CAMERA_PORT}"
