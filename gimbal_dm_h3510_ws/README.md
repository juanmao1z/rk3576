# DM-H3510 Gimbal Workspace

DM-H3510 云台工程资料和 PC 烟测工作区。这个目录保存 USB2CANFD 烟测、配置样例、协议记录和工程说明。

ROS2 驱动主入口在 `D:\Desktop\rk3576\workspace\dm_h3510_ros_ws`。本目录不作为 ROS2 主工作区。

## 是否需要新建工作区

需要，建议保留为独立工程资料工作区。

原因：

- 云台工程资料和相机/YOLO 推理是不同生命周期：接线、协议、标定、PC 烟测需要独立记录。
- PC 侧达妙 USB2CANFD、SDK 库和烟测脚本不应混进 YOLO 工作区。
- ROS2 驱动已独立放在 `dm_h3510_ros_ws`，本目录只保留工程验证和资料入口。
- 视觉检测结果可以通过 ROS2 话题驱动云台，不需要把云台资料写进检测服务本体。

## 目录结构

```text
gimbal_dm_h3510_ws/
  config/           PC 烟测、USB2CANFD 和云台参数样例
  cpp_v1_1_smoke/   C++ v1.1 SDK PC 烟测工程
  docs/             DM-H3510 接线、协议、标定和联调记录
  scripts/
    windows/        Windows 侧枚举、探测和 PC 烟测入口
  src/              PC 烟测和串口探测辅助代码
```

## 和现有工作区的边界

| 工作区 | 职责 |
| --- | --- |
| `camera_web_cpp_ws` | 摄像头采集和 MJPEG 原始图像流 |
| `drone_yolo_web_cpp_ws` | 无人机目标检测、Web 显示和 `/yolo/detections` 发布 |
| `dm_h3510_ros_ws` | DM-H3510 ROS2 Python/C++ 驱动、构建和板端运行 |
| `gimbal_dm_h3510_ws` | DM-H3510 工程资料、PC 烟测、配置样例和协议记录 |

## 推荐集成方式

第一阶段先做 PC 侧烟测：

1. PC 先通过达妙 USB2CANFD + SDK 验证不用 DMTool 上位机也能控制 DM-H3510。
2. 确认 DM-H3510 的通信方式、设备节点和供电接线。
3. 在 `config/` 记录串口/CAN 参数、角度限位、方向反转和归中位置。
4. 在 `scripts/windows/` 保留 Windows 侧枚举和烟测入口。
5. 在 `docs/` 记录抓包、协议和工程结论。

第二阶段再接入视觉闭环：

1. 继续让 YOLO 工作区发布统一检测结果 `/yolo/detections`。
2. `dm_h3510_ros_ws` 单独接收云台目标指令，并发布 `/gimbal/state`。
3. 上层控制节点或脚本计算 pan/tilt 控制量，负责限幅、死区和丢目标回中。
4. 上层联动脚本再组合启动摄像头、YOLO 和云台，不合并三个工作区。

## ROS2 接口边界

ROS2 驱动接口以 `dm_h3510_ros_ws` 为准：

| 接口 | 建议 |
| --- | --- |
| 云台目标位置 | `/gimbal/position_cmd` |
| 云台目标 JointState | `/gimbal/target_joint_state` |
| 云台状态反馈 | `/gimbal/state` |
| 视觉检测输入 | `/yolo/detections` 由视觉工作区发布 |

## 当前 PC 验证入口

这一步用于验证 `PC + DM_DeviceSDK + USB2CANFD + DM-H3510`，不使用官方 DMTool 图形上位机。
当前优先使用 C++ v1.1 SDK 例程，因为它已经按 DMTool 抓包改为经典 CAN 1Mbps。

```powershell
cd D:\Desktop\rk3576\workspace\gimbal_dm_h3510_ws
.\scripts\windows\list_usb2canfd.ps1
.\scripts\windows\run_dm_h3510_control.ps1 -Velocity 1 -DurationMs 2000
```

详细步骤见 `docs/pc_usb2canfd_smoke_test.md` 和 `docs/dm_h3510_engineering.md`。

## 维护约定

- 不把 DM-H3510 驱动代码放入 `drone_yolo_web_cpp_ws`。
- 不在相机工作区里加入云台设备初始化逻辑。
- ROS2 驱动代码和板端构建脚本放在 `dm_h3510_ros_ws`。
- 联动启动脚本可以放在 `workspace\scripts\windows`，但具体云台逻辑放回本工作区。
- 厂商协议、SDK 烟测结论和接线记录先写入 `docs/`。
