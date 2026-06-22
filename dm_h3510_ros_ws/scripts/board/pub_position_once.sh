#!/usr/bin/env bash
set -euo pipefail

POSITION_RAD="${1:-0.0}"
VELOCITY_RAD_S="${2:-1.0}"
TOPIC="${3:-/gimbal/target_joint_state}"
WORKSPACE_ROOT="${4:-/home/lckfb/workspace/dm_h3510_ros_ws}"
PYTHON_WS="$WORKSPACE_ROOT/python"
CPP_WS="$WORKSPACE_ROOT/cpp"

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

source_overlay_if_exists() {
  local setup_file="$1"
  if [ -f "$setup_file" ]; then
    # shellcheck disable=SC1090
    set +u
    source "$setup_file"
    set -u
  fi
}

source_ros
source_overlay_if_exists "$PYTHON_WS/install/setup.bash"
source_overlay_if_exists "$CPP_WS/install/setup.bash"

ros2 topic pub --once "$TOPIC" sensor_msgs/msg/JointState \
  "{name: ['dm_h3510_joint'], position: [$POSITION_RAD], velocity: [$VELOCITY_RAD_S]}"
