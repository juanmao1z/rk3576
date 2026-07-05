# yolo_web_py_ws

YOLO Python 服务端画框工作区。它订阅摄像头 MJPEG 压缩图像，使用 RKNNLite 推理，在服务端用 OpenCV 画框并重新编码为带框 MJPEG 结果流。

下面的 Windows 命令默认从 RK3576 项目目录执行。

## 项目定位

- 主用途：保留 Python 版 YOLO Web 实现，便于调试和与 C++ 版做效果对照。
- 展示方式：服务端画框，浏览器只显示带框 MJPEG。
- 与 Canvas 版区别：本工作区不使用浏览器 Canvas 叠加结构。
- 与 C++ 版区别：本工作区使用 Python + RKNNLite，CPU 开销通常高于 C++ + RKNN C API。

## 目录结构

```text
yolo_web_py_ws/
  models/                  RKNN 模型
  scripts/board/           开发板启动/停止脚本
  scripts/windows/         Windows 一键启动/停止脚本，包含 ADB 端口映射
  src/vision_msgs/         vendored ROS 视觉检测消息
  src/yolo_web_py/         ROS2 Python 推理和 Web 包
```

## 默认配置

| 项目 | 默认值 |
| --- | --- |
| 输入话题 | `/camera/image_mjpeg` |
| RKNN 模型 | `/home/lckfb/workspace/yolo/yolo_web_py_ws/models/yolo11.rknn` |
| YOLO Web 端口 | `8090` |
| 摄像头原始流端口 | `8081` |
| JPEG 输出质量 | `65` |
| ROS 检测话题 | `/yolo/detections` |
| 消息类型 | `vision_msgs/msg/Detection2DArray` |

## 数据流

```text
camera_web_cpp
  /dev/video73 -> /camera/image_mjpeg -> http://127.0.0.1:8081/stream.mjpg

yolo_web_py
  /camera/image_mjpeg -> Python JPEG 解码 -> RKNNLite -> YOLO 后处理
  -> OpenCV 画框 -> JPEG 重新编码
  -> http://127.0.0.1:8090/stream.mjpg
  -> /yolo/detections ROS 话题
```

## 构建

在开发板上执行：

```bash
cd /home/lckfb/workspace/yolo/yolo_web_py_ws
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install --packages-up-to yolo_web_py
```

## 启动

Windows 一键启动完整链路，并自动转发 `8081` 和 `8090`：

```powershell
powershell -ExecutionPolicy Bypass -File .\yolo_web_py_ws\scripts\windows\start_camera_yolo_py_all.ps1
```

切换到 `1280x720` 时，摄像头脚本会自动请求 `30 FPS`：

```powershell
powershell -ExecutionPolicy Bypass -File .\yolo_web_py_ws\scripts\windows\start_camera_yolo_py_all.ps1 -Size 1280x720
```

开发板直接启动完整链路：

```bash
/home/lckfb/workspace/yolo/yolo_web_py_ws/scripts/board/start_camera_yolo_py_all.sh --size 1280x720
```

## 关闭

Windows 一键关闭完整链路，并移除 ADB 转发：

```powershell
powershell -ExecutionPolicy Bypass -File .\yolo_web_py_ws\scripts\windows\stop_camera_yolo_py_all.ps1
```

开发板直接关闭：

```bash
/home/lckfb/workspace/yolo/yolo_web_py_ws/scripts/board/stop_camera_yolo_py_all.sh
```

## Web 接口

| 路径 | 说明 |
| --- | --- |
| `/` 或 `/index.html` | 带框 MJPEG 结果页面 |
| `/stream.mjpg` | 带框 MJPEG 结果流 |
| `/snapshot.jpg` | 最新带框 JPEG |
| `/detections` | 最新检测 JSON、FPS 和耗时 |
| `/health` | 轻量健康检查 |

## ROS 输出

推理完成后发布：

```text
/yolo/detections
```

消息类型：

```text
vision_msgs/msg/Detection2DArray
```

## 验证

```bash
curl http://127.0.0.1:8081/health
curl http://127.0.0.1:8090/health
curl http://127.0.0.1:8090/detections
source /opt/ros/jazzy/setup.bash
source /home/lckfb/workspace/yolo/yolo_web_py_ws/install/setup.bash
ros2 topic echo /yolo/detections --once
```

Windows 侧确认端口映射：

```powershell
adb forward --list
```
