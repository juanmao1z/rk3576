# Python ROS Workspace

这是 Python / `rclpy` 版本，ROS 包名为 `dm_h3510_ros_py`，功能与 C++ 版本一致，
控制模式为 **position-speed cascade mode**。

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
ros2 topic pub --once /gimbal/target_joint_state sensor_msgs/msg/JointState "{name: ['dm_h3510_joint'], position: [0.5], velocity: [1.0]}"
```

`position[0]` 单位为 rad，`velocity[0]` 单位为 rad/s。
