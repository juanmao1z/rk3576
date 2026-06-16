# DM-H3510 ROS2 Workspace

这个工作区专门保存 RK3576 上通过 ROS2 驱动 DM-H3510 的代码。它是云台 ROS2 主入口。

PC 侧 USB2CANFD 烟测、配置样例和工程记录位于 `D:\Desktop\rk3576\workspace\gimbal_dm_h3510_ws`。

当前硬件链路：

```text
RK3576 USB -> DM USB2CANFD -> Classic CAN 1 Mbps -> DM-H3510
```

当前实现不走 `gs_usb/can0`，而是使用达妙 `DM_DeviceSDK` 的 Linux arm64
用户态库 `libdm_device.so`。原因是当前板端内核 `6.1.99` 无法直接加载资料里的
`gs_usb.ko`。

## 当前控制模式

当前 ROS 节点只保留 **position-speed cascade mode**。

```text
CAN ID: 0x101 = 0x001 + 0x100
payload: float32 position_rad + float32 velocity_rad_s
byte order: little-endian
feedback ID: 0x011
```

`D:\Desktop\速度位置模式.csv` 中 DMTool 的指令已经验证该格式，例如：

```text
ID   = 0x101
data = 00 00 34 43 00 00 B4 42
     = position 180.0 rad, velocity 90.0 rad/s
```

## 目录结构

```text
dm_h3510_ros_ws/
  python/       # Python + rclpy 版本，ROS 包名 dm_h3510_ros_py
  cpp/          # C++ + rclcpp 版本，ROS 包名 dm_h3510_ros_cpp
  scripts/      # Windows 部署脚本与 RK3576 板端脚本
  docs/         # 调试记录和协议说明
```

Python 包名保留 `dm_h3510_ros_py`。C++ 包名保留 `dm_h3510_ros_cpp`。不要把这两个包合并到视觉工作区。

## ROS 接口

| 方向 | 名称 | 类型 | 说明 |
| --- | --- | --- | --- |
| 订阅 | `/gimbal/position_cmd` | `std_msgs/msg/Float32` | 目标位置，单位 rad；速度限制使用 `default_velocity_rad_s` |
| 订阅 | `/gimbal/target_joint_state` | `sensor_msgs/msg/JointState` | `position[0]` 为目标位置 rad，`velocity[0]` 为速度限制 rad/s |
| 发布 | `/gimbal/state` | `sensor_msgs/msg/JointState` | DM-H3510 位置、速度、力矩反馈 |

节点收到目标后会锁存该目标，并按 `command_period_ms` 周期持续发送 `0x101`
position-speed 帧。发送新的目标会覆盖旧目标。

## 和其他工作区的边界

| 工作区 | 职责 |
| --- | --- |
| `dm_h3510_ros_ws` | DM-H3510 ROS2 节点、launch、配置、部署和板端构建 |
| `gimbal_dm_h3510_ws` | PC 烟测、USB2CANFD 验证、配置样例和工程资料 |
| `camera_web_cpp_ws` | 摄像头原始 MJPEG 流 |
| `drone_yolo_web_cpp_ws` | 无人机检测和 `/yolo/detections` 发布 |

## 从 Windows 部署到 RK3576

在 PC 的 PowerShell 里执行：

```powershell
cd D:\Desktop\rk3576\workspace\dm_h3510_ros_ws
.\scripts\windows\deploy_to_board.ps1
```

部署目标路径：

```text
/home/lckfb/workspace/dm_h3510_ros_ws
```

注意：`/home/lckfb/...` 是 RK3576 开发板路径，不是 Windows 或 WSL 路径。
在 Windows PowerShell 中运行板端脚本时，需要用 `adb shell`。

## 板端构建

推荐优先使用 C++ 版本：

```powershell
adb shell "bash /home/lckfb/workspace/dm_h3510_ros_ws/scripts/board/build_cpp_ros.sh"
```

Python 版本：

```powershell
adb shell "bash /home/lckfb/workspace/dm_h3510_ros_ws/scripts/board/build_python_ros.sh"
```

如果你已经在 RK3576 的终端里，可以直接执行：

```bash
bash /home/lckfb/workspace/dm_h3510_ros_ws/scripts/board/build_cpp_ros.sh
```

## 启动节点

Windows PowerShell：

```powershell
adb shell "bash /home/lckfb/workspace/dm_h3510_ros_ws/scripts/board/run_cpp_ros.sh"
```

RK3576 板端终端：

```bash
bash /home/lckfb/workspace/dm_h3510_ros_ws/scripts/board/run_cpp_ros.sh
```

Python 版本对应脚本：

```powershell
adb shell "bash /home/lckfb/workspace/dm_h3510_ros_ws/scripts/board/run_python_ros.sh"
```

## 发送位置目标

另开一个终端，发送 `0.5 rad` 目标，速度限制 `1.0 rad/s`：

```powershell
adb shell "bash /home/lckfb/workspace/dm_h3510_ros_ws/scripts/board/pub_position_once.sh 0.5 1.0"
```

也可以手动发布 ROS topic：

```bash
source /opt/ros/jazzy/setup.bash
source /home/lckfb/workspace/dm_h3510_ros_ws/cpp/install/setup.bash
ros2 topic pub --once /gimbal/target_joint_state sensor_msgs/msg/JointState "{name: ['dm_h3510_joint'], position: [0.5], velocity: [1.0]}"
```

只发位置时，速度限制使用 `default_velocity_rad_s`：

```bash
ros2 topic pub --once /gimbal/position_cmd std_msgs/msg/Float32 "{data: 0.5}"
```

## 运行状态

查看反馈：

```bash
ros2 topic echo /gimbal/state
```

查看节点和话题：

```bash
ros2 node list
ros2 topic list
```

## 参数

主要参数在：

```text
python/src/dm_h3510_ros_py/config/dm_h3510_ros_py.yaml
cpp/src/dm_h3510_ros_cpp/config/dm_h3510_ros_cpp.yaml
```

关键默认值：

```yaml
default_velocity_rad_s: 1.0
command_period_ms: 20
switch_mode_on_start: true
motor:
  can_id: 1
  master_id: 17
  position_velocity_id_offset: 256
```
