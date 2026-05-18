#!/usr/bin/env bash
# 通用 YOLO C++ Canvas 完整链路启动脚本。
# 启动顺序固定为 camera_web_cpp -> yolo_web_cpp，并在每一步后检查 /health。
set -Eeuo pipefail

YOLO_WS=/home/lckfb/workspace/yolo/yolo_web_cpp_ws
CAMERA_SCRIPT=/home/lckfb/workspace/ros/camera_web_cpp_ws/start_camera_web_cpp.sh
YOLO_CPP_SCRIPT=${YOLO_WS}/scripts/board/start_yolo_web_cpp.sh
CAMERA_LOG=/tmp/camera_web_cpp.log
YOLO_CPP_LOG=/tmp/yolo_web_cpp.log
CAMERA_HEALTH=http://127.0.0.1:8081/health
YOLO_CPP_HEALTH=http://127.0.0.1:8092/health
CAMERA_ARGS=("$@")

stop_old_processes() {
  # 同一时间只保留一个 YOLO 发布者，避免 /yolo/detections 出现多个 publisher。
  pkill -TERM -f '[r]os2 launch yolo_web_py_canvas' || true
  pkill -TERM -f '[y]olo_web_py_canvas_node' || true
  pkill -TERM -f '[r]os2 launch yolo_web_py' || true
  pkill -TERM -f '[y]olo_web_py_node' || true
  pkill -TERM -f '[r]os2 launch yolo_web_cpp' || true
  pkill -TERM -f '[y]olo_web_cpp_node' || true
  pkill -TERM -f '[r]os2 launch yolo_web_demo' || true
  pkill -TERM -f '[y]olo_result_node' || true
  pkill -TERM -f '[y]olo_web_server' || true
  pkill -TERM -f '[r]os2 launch camera_web_cpp' || true
  pkill -TERM -f '[c]amera_web_cpp_container' || true
  sleep 1
}

wait_for_http() {
  local name=$1
  local url=$2
  local log_file=$3
  local require_frames=${4:-0}

  # require_frames=1 时要求 health 中 frames 大于 0，避免端口刚监听但还没有数据。
  for _ in $(seq 1 30); do
    if curl -fsS --max-time 2 "${url}" >/tmp/yolo_web_cpp_health.txt 2>/dev/null; then
      local health
      health=$(cat /tmp/yolo_web_cpp_health.txt)
      local frames
      frames=$(printf '%s\n' "${health}" | sed -n 's/.*frames=\([0-9][0-9]*\).*/\1/p')
      if [[ "${require_frames}" != "1" || "${frames:-0}" -gt 0 ]]; then
        echo "${name} ready: ${health}"
        return 0
      fi
    fi
    sleep 1
  done

  echo "${name} failed to start. Recent log:"
  tail -120 "${log_file}" 2>/dev/null || true
  return 1
}

main() {
  if [[ ! -x "${CAMERA_SCRIPT}" ]]; then
    echo "Camera script not found or not executable: ${CAMERA_SCRIPT}" >&2
    exit 1
  fi
  if [[ ! -x "${YOLO_CPP_SCRIPT}" ]]; then
    echo "YOLO C++ script not found or not executable: ${YOLO_CPP_SCRIPT}" >&2
    exit 1
  fi

  stop_old_processes

  : >"${CAMERA_LOG}"
  : >"${YOLO_CPP_LOG}"

  echo "Starting C++ camera service on 8081..."
  nohup "${CAMERA_SCRIPT}" "${CAMERA_ARGS[@]}" >"${CAMERA_LOG}" 2>&1 &
  camera_pid=$!
  wait_for_http "camera_web_cpp" "${CAMERA_HEALTH}" "${CAMERA_LOG}" 1

  echo "Starting C++ YOLO overlay service on 8092..."
  nohup "${YOLO_CPP_SCRIPT}" >"${YOLO_CPP_LOG}" 2>&1 &
  yolo_pid=$!
  wait_for_http "yolo_web_cpp" "${YOLO_CPP_HEALTH}" "${YOLO_CPP_LOG}" 1

  echo "All C++ camera + YOLO overlay services started."
  echo "Camera page: http://127.0.0.1:8081/"
  echo "YOLO C++ overlay page: http://127.0.0.1:8092/"
  echo "Logs:"
  echo "  camera pid=${camera_pid}, log=${CAMERA_LOG}"
  echo "  yolo   pid=${yolo_pid}, log=${YOLO_CPP_LOG}"
}

main "$@"
