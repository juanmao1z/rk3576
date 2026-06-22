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

if [ ! -f install/setup.bash ]; then
  echo "未找到 install/setup.bash，先执行 scripts/board/build_python_ros.sh。" >&2
  exit 1
fi

# shellcheck disable=SC1091
set +u
source install/setup.bash
set -u
exec ros2 launch dm_h3510_ros_py dm_h3510_ros_py.launch.py
