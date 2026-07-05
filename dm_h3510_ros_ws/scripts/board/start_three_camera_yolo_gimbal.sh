#!/usr/bin/env bash
# Start three-camera Drone YOLO and drive the gimbal from the USB camera detections.
set -Eeuo pipefail

WORKSPACE_ROOT="${WORKSPACE_ROOT:-/home/lckfb/workspace/dm_h3510_ros_ws}"
DRONE_YOLO_ROOT="${DRONE_YOLO_ROOT:-/home/lckfb/workspace/drone_yolo_web_cpp_ws}"
THREE_CAMERA_SCRIPT="${THREE_CAMERA_SCRIPT:-${DRONE_YOLO_ROOT}/scripts/board/start_three_camera_drone_yolo_cpp_all.sh}"
DM_DRIVER_SCRIPT="${WORKSPACE_ROOT}/scripts/board/run_cpp_ros.sh"
TRACKER_SCRIPT="${WORKSPACE_ROOT}/scripts/board/run_gimbal_tracker.sh"
PUB_POSITION_SCRIPT="${WORKSPACE_ROOT}/scripts/board/pub_position_once.sh"

DRY_RUN="${DRY_RUN:-true}"
DETECTIONS_TOPIC="${DETECTIONS_TOPIC:-/yolo/usb_rear/detections}"
GIMBAL_STATE_TOPIC="${GIMBAL_STATE_TOPIC:-/gimbal/state}"
TARGET_JOINT_TOPIC="${TARGET_JOINT_TOPIC:-/gimbal/target_joint_state}"
MAX_STEP_RAD="${MAX_STEP_RAD:-0.05}"
VELOCITY_RAD_S="${VELOCITY_RAD_S:-0.6}"
KICK_POSITION_RAD="${KICK_POSITION_RAD:-0.05}"
KICK_VELOCITY_RAD_S="${KICK_VELOCITY_RAD_S:-0.03}"

CAMERA_YOLO_LOG="${CAMERA_YOLO_LOG:-/tmp/three_camera_drone_yolo_cpp_all.log}"
DM_LOG="${DM_LOG:-/tmp/dm_h3510_ros_cpp.log}"
TRACKER_LOG="${TRACKER_LOG:-/tmp/gimbal_tracker.log}"

source_ros() {
  if [ -n "${ROS_DISTRO:-}" ] && [ -f "/opt/ros/$ROS_DISTRO/setup.bash" ]; then
    set +u
    # shellcheck disable=SC1090
    source "/opt/ros/$ROS_DISTRO/setup.bash"
    set -u
    return
  fi

  for setup_file in /opt/ros/*/setup.bash; do
    if [ -f "$setup_file" ]; then
      set +u
      # shellcheck disable=SC1090
      source "$setup_file"
      set -u
      return
    fi
  done

  echo "未找到 /opt/ros/*/setup.bash，请先安装 ROS2。" >&2
  exit 1
}

source_overlay_if_exists() {
  local setup_file=$1
  if [ -f "$setup_file" ]; then
    set +u
    # shellcheck disable=SC1090
    source "$setup_file"
    set -u
  fi
}

wait_for_topic_once() {
  local topic=$1
  local seconds=$2

  if timeout "$seconds" ros2 topic echo "$topic" --once >/tmp/three_camera_yolo_gimbal_topic.txt 2>/dev/null; then
    cat /tmp/three_camera_yolo_gimbal_topic.txt
    return 0
  fi

  echo "等待 ${topic} 超时。" >&2
  return 1
}

wait_for_process() {
  local name=$1
  local pattern=$2

  for _ in $(seq 1 20); do
    if pgrep -f "$pattern" >/dev/null; then
      echo "${name} process is running."
      return 0
    fi
    sleep 1
  done

  echo "${name} process did not start." >&2
  return 1
}

main() {
  if [ ! -x "$THREE_CAMERA_SCRIPT" ]; then
    echo "三路 YOLO 启动脚本不存在或不可执行: $THREE_CAMERA_SCRIPT" >&2
    exit 1
  fi
  if [ ! -x "$DM_DRIVER_SCRIPT" ] || [ ! -x "$TRACKER_SCRIPT" ] || [ ! -x "$PUB_POSITION_SCRIPT" ]; then
    echo "云台脚本缺失，请先部署 dm_h3510_ros_ws/scripts。" >&2
    exit 1
  fi

  echo "Stopping any existing gimbal tracker before switching camera topology..."
  pkill -TERM -f '[r]os2 launch gimbal_tracker' || true
  pkill -TERM -f '[g]imbal_tracker_node' || true

  echo "Starting three-camera Drone YOLO..."
  : >"$CAMERA_YOLO_LOG"
  "$THREE_CAMERA_SCRIPT" "$@" >"$CAMERA_YOLO_LOG" 2>&1
  tail -40 "$CAMERA_YOLO_LOG" || true

  echo "Starting DM-H3510 driver..."
  pkill -TERM -f '[r]os2 launch dm_h3510_ros_cpp' || true
  pkill -TERM -f '[d]m_h3510_ros_cpp_node' || true
  : >"$DM_LOG"
  nohup "$DM_DRIVER_SCRIPT" "$WORKSPACE_ROOT" >"$DM_LOG" 2>&1 &
  wait_for_process "dm_h3510_ros_cpp" 'dm_h3510_ros_cpp_node'

  source_ros
  source_overlay_if_exists "${DRONE_YOLO_ROOT}/install/setup.bash"
  source_overlay_if_exists "${WORKSPACE_ROOT}/cpp/install/setup.bash"

  echo "Priming gimbal feedback with ${KICK_POSITION_RAD} rad @ ${KICK_VELOCITY_RAD_S} rad/s..."
  "$PUB_POSITION_SCRIPT" "$KICK_POSITION_RAD" "$KICK_VELOCITY_RAD_S" "$TARGET_JOINT_TOPIC" "$WORKSPACE_ROOT"
  wait_for_topic_once "$GIMBAL_STATE_TOPIC" 8
  "$PUB_POSITION_SCRIPT" "0.0" "$KICK_VELOCITY_RAD_S" "$TARGET_JOINT_TOPIC" "$WORKSPACE_ROOT" || true

  echo "Starting gimbal tracker from ${DETECTIONS_TOPIC}, dry_run=${DRY_RUN}..."
  : >"$TRACKER_LOG"
  DETECTIONS_TOPIC="$DETECTIONS_TOPIC" \
    GIMBAL_STATE_TOPIC="$GIMBAL_STATE_TOPIC" \
    TARGET_JOINT_TOPIC="$TARGET_JOINT_TOPIC" \
    MAX_STEP_RAD="$MAX_STEP_RAD" \
    VELOCITY_RAD_S="$VELOCITY_RAD_S" \
    DRY_RUN="$DRY_RUN" \
    nohup "$TRACKER_SCRIPT" "$WORKSPACE_ROOT" >"$TRACKER_LOG" 2>&1 &
  wait_for_process "gimbal_tracker" 'gimbal_tracker_node'
  sleep 2
  tail -80 "$TRACKER_LOG" || true

  echo "Three-camera YOLO + gimbal tracker started."
  echo "  detections=${DETECTIONS_TOPIC}"
  echo "  dry_run=${DRY_RUN}"
  echo "  max_step_rad=${MAX_STEP_RAD}"
  echo "  velocity_rad_s=${VELOCITY_RAD_S}"
  echo "  overview=http://127.0.0.1:8099/"
  echo "  USB YOLO=http://127.0.0.1:8094/"
}

main "$@"
