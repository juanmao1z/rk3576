# YOLO 云台联调步骤

这份文档从 Windows PowerShell 开始。目标是让 YOLO 检测结果驱动 DM-H3510 云台。

默认先 dry-run。确认日志正确后，再真实控制。

## 前置条件

你需要满足：

| 项目 | 要求 |
| --- | --- |
| RK3576 | ADB 在线 |
| 云台 | DM-H3510 已供电 |
| USB2CANFD | 已连接 RK3576 |
| 相机 | 能发布图像 |
| YOLO | 能发布 `/yolo/detections` |

确认 ADB：

```powershell
adb devices
```

应该看到：

```text
List of devices attached
xxxxxxxx	device
```

## 1. 部署代码

```powershell
cd .\dm_h3510_ros_ws
.\scripts\windows\deploy_to_board.ps1
```

部署目标路径：

```text
/home/lckfb/workspace/dm_h3510_ros_ws
```

## 2. 构建 C++ 工作区

```powershell
adb shell "bash /home/lckfb/workspace/dm_h3510_ros_ws/scripts/board/build_cpp_ros.sh"
```

期望看到：

```text
Summary: 2 packages finished
```

如果看到 `Clock skew detected`，先记录。它通常是板端时间不准导致。

## 3. 启动云台驱动

打开一个 PowerShell 终端：

```powershell
adb shell "bash /home/lckfb/workspace/dm_h3510_ros_ws/scripts/board/run_cpp_ros.sh"
```

这个终端保持运行。

## 4. 检查云台状态

另开一个 PowerShell 终端：

```powershell
adb shell "source /opt/ros/jazzy/setup.bash && source /home/lckfb/workspace/dm_h3510_ros_ws/cpp/install/setup.bash && ros2 topic echo /gimbal/state --once"
```

能看到 `position`、`velocity`、`effort` 才能继续。

## 5. 检查 YOLO 检测

确认 YOLO 已经启动后执行：

```powershell
adb shell "source /opt/ros/jazzy/setup.bash && source /home/lckfb/workspace/drone_yolo_web_cpp_ws/install/setup.bash && ros2 topic echo /yolo/detections --once"
```

画面里放入无人机。你应该看到检测框数据。

## 6. dry-run 启动 tracker

```powershell
adb shell "DRY_RUN=true bash /home/lckfb/workspace/dm_h3510_ros_ws/scripts/board/run_gimbal_tracker.sh"
```

期望看到：

```text
gimbal_tracker started: detections=/yolo/detections state=/gimbal/state target=/gimbal/target_joint_state dry_run=true rate=10Hz
```

检测到目标后，会看到：

```text
target=drone score=... center=(..., ...) error_x=... delta=... current=... target=... dry_run=true
```

dry-run 不会控制云台。

## 7. 判断方向

把无人机放到画面右侧。当前逻辑应该输出正向 `delta`。

把无人机放到画面左侧。当前逻辑应该输出负向 `delta`。

如果方向反了，先不要真实控制。需要修改控制方向。

## 8. 真实控制

确认方向正确后执行：

```powershell
adb shell "DRY_RUN=false bash /home/lckfb/workspace/dm_h3510_ros_ws/scripts/board/run_gimbal_tracker.sh"
```

这时节点会发布 `/gimbal/target_joint_state`。

## 9. 调整参数

参数文件：

```text
.\dm_h3510_ros_ws\cpp\src\gimbal_tracker\config\gimbal_tracker.yaml
```

常调参数：

| 现象 | 优先修改 |
| --- | --- |
| 中心附近抖动 | 增大 `deadband_px` |
| 跟踪太慢 | 增大 `max_step_rad` |
| 仍然太慢 | 小幅增大 `kp_x` |
| 电机实际转得慢 | 增大 `velocity_rad_s` |
| 左右角度不够 | 调整 `min_yaw_rad`、`max_yaw_rad` |

当前装了 `35:1` 谐波减速器。ROS 话题里的角度和速度仍然表示云台输出端。

驱动会自动换算到电机端：

```text
电机角度 = 云台输出角度 * 35
电机速度 = 云台输出速度 * 35
```

修改后重新部署和构建：

```powershell
cd .\dm_h3510_ros_ws
.\scripts\windows\deploy_to_board.ps1
adb shell "bash /home/lckfb/workspace/dm_h3510_ros_ws/scripts/board/build_cpp_ros.sh"
```

## 10. 验收标准

| 检查项 | 通过标准 |
| --- | --- |
| `/gimbal/state` | 能持续输出 |
| `/yolo/detections` | 画面有无人机时有检测 |
| dry-run | 能打印 `target=drone` |
| 方向 | 左右移动时 `delta` 方向符合预期 |
| 真实控制 | 云台向目标方向转动 |
| 安全 | 丢目标后不会继续输出旧目标 |
