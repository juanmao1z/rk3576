#!/usr/bin/env bash
# 关闭通用 YOLO C++ Canvas 完整链路。
# 允许重复执行，未运行的进程会被忽略。
set -Eeuo pipefail

stop_by_pattern() {
  # 只在匹配到进程时输出停止信息，减少重复执行时的噪声。
  local name=$1
  local pattern=$2

  if pgrep -f "${pattern}" >/dev/null 2>&1; then
    echo "Stopping ${name}..."
    pkill -TERM -f "${pattern}" || true
  fi
}

stop_by_pattern "YOLO C++ launch" '[r]os2 launch yolo_web_cpp'
stop_by_pattern "YOLO C++ node" '[y]olo_web_cpp_node'
stop_by_pattern "camera launch" '[r]os2 launch camera_web_cpp'
stop_by_pattern "camera component container" '[c]amera_web_cpp_container'

sleep 2

remaining=$(
  pgrep -af 'yolo_web_cpp_node|ros2 launch yolo_web_cpp|ros2 launch camera_web_cpp|camera_web_cpp_container' || true
)

if [[ -n "${remaining}" ]]; then
  echo "Some C++ camera + YOLO processes are still running:"
  echo "${remaining}"
  exit 1
fi

echo "All C++ camera + YOLO overlay services stopped."
