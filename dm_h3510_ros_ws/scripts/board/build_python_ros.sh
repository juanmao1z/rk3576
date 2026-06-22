#!/usr/bin/env bash
set -euo pipefail

WORKSPACE_ROOT="${1:-/home/lckfb/workspace/dm_h3510_ros_ws}"
PYTHON_WS="$WORKSPACE_ROOT/python"

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
cd "$PYTHON_WS"
colcon build --symlink-install
