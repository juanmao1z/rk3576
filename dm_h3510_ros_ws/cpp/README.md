# DM-H3510 C++ ROS2 工作区

这是当前推荐主线。它包含云台驱动 `dm_h3510_ros_cpp` 和 YOLO 跟踪节点 `gimbal_tracker`。

## 包说明

| 包 | 作用 |
| --- | --- |
| `dm_h3510_ros_cpp` | 连接 DM USB2CANFD，并驱动 DM-H3510 |
| `gimbal_tracker` | 把 YOLO 检测框转换为云台 yaw 目标角度 |

## 构建

PC 端通过 ADB 构建：

```powershell
adb shell "bash /home/lckfb/workspace/dm_h3510_ros_ws/scripts/board/build_cpp_ros.sh"
```

RK3576 板端终端：

```bash
bash /home/lckfb/workspace/dm_h3510_ros_ws/scripts/board/build_cpp_ros.sh
```

## 启动云台驱动

PC 端通过 ADB 启动：

```powershell
adb shell "bash /home/lckfb/workspace/dm_h3510_ros_ws/scripts/board/run_cpp_ros.sh"
```

RK3576 板端终端：

```bash
bash /home/lckfb/workspace/dm_h3510_ros_ws/scripts/board/run_cpp_ros.sh
```

确认反馈：

```powershell
adb shell "source /opt/ros/jazzy/setup.bash && source /home/lckfb/workspace/dm_h3510_ros_ws/cpp/install/setup.bash && ros2 topic echo /gimbal/state --once"
```

## 启动 YOLO 跟踪

先 dry-run：

```powershell
adb shell "DRY_RUN=true bash /home/lckfb/workspace/dm_h3510_ros_ws/scripts/board/run_gimbal_tracker.sh"
```

真实控制：

```powershell
adb shell "DRY_RUN=false bash /home/lckfb/workspace/dm_h3510_ros_ws/scripts/board/run_gimbal_tracker.sh"
```

`gimbal_tracker` 参数见：

```text
src/gimbal_tracker/README.md
```

## 控制协议

当前 C++ 主线使用 `speed mode + software position loop`。

上层仍然发目标角度。驱动内部把角度误差转换为速度命令。

```text
CAN ID: 0x201 = 0x001 + 0x200
payload: float32 velocity_rad_s
byte order: little-endian
Classic CAN: 1 Mbps
feedback ID: 0x011
```

ROS 话题统一使用云台输出端单位。驱动内部按 `35:1` 谐波减速器换算到电机端。

```text
motor_velocity_rad_s = output_velocity_rad_s * gear_ratio * gear_direction
output_position_rad = unwrapped_motor_position_rad / gear_ratio * gear_direction
output_velocity_rad_s = motor_velocity_rad_s / gear_ratio
```

使能帧：

```text
ID: 0x201
data: FF FF FF FF FF FF FF FC
```

失能帧：

```text
ID: 0x201
data: FF FF FF FF FF FF FF FD
```

## 发布位置目标

用脚本发送：

```powershell
adb shell "bash /home/lckfb/workspace/dm_h3510_ros_ws/scripts/board/pub_position_once.sh 0.5 0.5"
```

手动发布：

```bash
source /opt/ros/jazzy/setup.bash
source /home/lckfb/workspace/dm_h3510_ros_ws/cpp/install/setup.bash
ros2 topic pub --once /gimbal/target_joint_state sensor_msgs/msg/JointState "{name: ['dm_h3510_joint'], position: [0.5], velocity: [0.5]}"
```

`position[0]` 是云台输出端角度，单位是 rad。

`velocity[0]` 是云台输出端速度限制，单位是 rad/s。

## 参数文件

云台驱动：

```text
src/dm_h3510_ros_cpp/config/dm_h3510_ros_cpp.yaml
```

减速器参数：

```yaml
motor:
  gear_ratio: 35.0
  gear_direction: 1.0
  velocity_id_offset: 512
position_loop:
  kp: 2.0
  tolerance_rad: 0.02
```

YOLO 跟踪：

```text
src/gimbal_tracker/config/gimbal_tracker.yaml
```
