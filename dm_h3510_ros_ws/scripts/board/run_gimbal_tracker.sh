#!/usr/bin/env bash
set -euo pipefail

WORKSPACE_ROOT="${1:-/home/lckfb/workspace/dm_h3510_ros_ws}"
CPP_WS="$WORKSPACE_ROOT/cpp"
DRY_RUN="${DRY_RUN:-true}"
DETECTIONS_TOPIC="${DETECTIONS_TOPIC:-/yolo/detections}"
GIMBAL_STATE_TOPIC="${GIMBAL_STATE_TOPIC:-/gimbal/state}"
TARGET_JOINT_TOPIC="${TARGET_JOINT_TOPIC:-/gimbal/target_joint_state}"
MAX_STEP_RAD="${MAX_STEP_RAD:-0.05}"
VELOCITY_RAD_S="${VELOCITY_RAD_S:-0.6}"

source_ros() {
  if [ -n "${ROS_DISTRO:-}" ] && [ -f "/opt/ros/$ROS_DISTRO/setup.bash" ]; then
    # shellcheck disable=SC1090
    set +u
    source "/opt/ros/$ROS_DISTRO/setup.bash"
    set -u
    return
  fi

  for setup_file in /opt/ros/*/setup.bash; do
    if [ -f "$setup_file" ]; then
      # shellcheck disable=SC1090
      set +u
      source "$setup_file"
      set -u
      return
    fi
  done

  echo "未找到 /opt/ros/*/setup.bash，请先安装 ROS2。" >&2
  exit 1
}

source_ros
if [ -f "/home/lckfb/workspace/drone_yolo_web_cpp_ws/install/setup.bash" ]; then
  # shellcheck disable=SC1091
  set +u
  source /home/lckfb/workspace/drone_yolo_web_cpp_ws/install/setup.bash
  set -u
fi

cd "$CPP_WS"
if [ ! -f install/setup.bash ]; then
  echo "未找到 install/setup.bash，先执行 scripts/board/build_cpp_ros.sh。" >&2
  exit 1
fi

# shellcheck disable=SC1091
set +u
source install/setup.bash
set -u

exec ros2 launch gimbal_tracker gimbal_tracker.launch.py \
  detections_topic:="$DETECTIONS_TOPIC" \
  gimbal_state_topic:="$GIMBAL_STATE_TOPIC" \
  target_joint_topic:="$TARGET_JOINT_TOPIC" \
  max_step_rad:="$MAX_STEP_RAD" \
  velocity_rad_s:="$VELOCITY_RAD_S" \
  dry_run:="$DRY_RUN"
