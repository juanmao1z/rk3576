# ROS Packages

ROS2 `.deb` 安装包归档目录。

## 当前包

| 文件 | 说明 |
| --- | --- |
| `ros-jazzy-vision-msgs_4.1.1-3noble.20260412.091152_arm64.deb` | RK3576/Ubuntu noble arm64 可用的 `vision_msgs` 包 |

## 使用场景

当开发板无法在线安装 `vision_msgs` 时，可以用这里的 `.deb` 离线安装；当前各 YOLO 工作区也 vendored 了 `src/vision_msgs`，用于保证 `/yolo/detections` 的标准消息类型可构建。
