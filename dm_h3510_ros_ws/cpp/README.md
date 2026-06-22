# DM-H3510 C++ ROS Driver

这是 C++ / `rclcpp` 版本，推荐作为 RK3576 云台控制的主版本。

## 协议

```text
控制模式: position-speed cascade mode
CAN ID: 0x101 = 0x001 + 0x100
payload: float32 position_rad + float32 velocity_rad_s
byte order: little-endian
Classic CAN: 1 Mbps
feedback ID: 0x011
```

使能帧：

```text
ID: 0x101
data: FF FF FF FF FF FF FF FC
```

失能帧：

```text
ID: 0x101
data: FF FF FF FF FF FF FF FD
```

## 构建

PC 端通过 ADB：

```powershell
adb shell "bash /home/lckfb/workspace/dm_h3510_ros_ws/scripts/board/build_cpp_ros.sh"
```

RK3576 板端终端：

```bash
bash /home/lckfb/workspace/dm_h3510_ros_ws/scripts/board/build_cpp_ros.sh
```

## 启动

PC 端通过 ADB：

```powershell
adb shell "bash /home/lckfb/workspace/dm_h3510_ros_ws/scripts/board/run_cpp_ros.sh"
```

RK3576 板端终端：

```bash
bash /home/lckfb/workspace/dm_h3510_ros_ws/scripts/board/run_cpp_ros.sh
```

## 发布位置目标

```bash
ros2 topic pub --once /gimbal/target_joint_state sensor_msgs/msg/JointState "{name: ['dm_h3510_joint'], position: [0.5], velocity: [1.0]}"
```

`position[0]` 单位为 rad，`velocity[0]` 单位为 rad/s。
