# DM-H3510 Python ROS2 工作区

这是 Python / `rclpy` 备用版本。当前推荐主线是 `cpp/`。

Python 版本用于快速验证接口和对照 C++ 行为。正式联调优先使用 C++ 版本。

## 功能

| 项目 | 说明 |
| --- | --- |
| ROS 包名 | `dm_h3510_ros_py` |
| 控制模式 | `position-speed cascade mode` |
| 输入话题 | `/gimbal/position_cmd`、`/gimbal/target_joint_state` |
| 输出话题 | `/gimbal/state` |

## 构建

PC 端通过 ADB：

```powershell
adb shell "bash /home/lckfb/workspace/dm_h3510_ros_ws/scripts/board/build_python_ros.sh"
```

RK3576 板端终端：

```bash
bash /home/lckfb/workspace/dm_h3510_ros_ws/scripts/board/build_python_ros.sh
```

## 启动

PC 端通过 ADB：

```powershell
adb shell "bash /home/lckfb/workspace/dm_h3510_ros_ws/scripts/board/run_python_ros.sh"
```

RK3576 板端终端：

```bash
bash /home/lckfb/workspace/dm_h3510_ros_ws/scripts/board/run_python_ros.sh
```

## 发布位置目标

```bash
source /opt/ros/jazzy/setup.bash
source /home/lckfb/workspace/dm_h3510_ros_ws/python/install/setup.bash
ros2 topic pub --once /gimbal/target_joint_state sensor_msgs/msg/JointState "{name: ['dm_h3510_joint'], position: [0.5], velocity: [0.5]}"
```

`position[0]` 是云台输出端角度，单位是 rad。

`velocity[0]` 是云台输出端速度限制，单位是 rad/s。

## 参数文件

```text
src/dm_h3510_ros_py/config/dm_h3510_ros_py.yaml
```

减速器参数：

```yaml
motor:
  gear_ratio: 35.0
  gear_direction: 1.0
```

修改后需要重新部署和构建：

```powershell
cd .\dm_h3510_ros_ws
.\scripts\windows\deploy_to_board.ps1
adb shell "bash /home/lckfb/workspace/dm_h3510_ros_ws/scripts/board/build_python_ros.sh"
```
