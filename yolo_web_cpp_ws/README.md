# yolo_web_cpp_ws

通用 YOLO C++ Canvas 工作区。它在 RK3576 上使用 RKNN C API 推理，浏览器直接显示摄像头原始 MJPEG 流，并用 Canvas 叠加检测框。

## 项目定位

- 主用途：通用 YOLO11 RKNN 检测，不绑定某一个业务类别。
- 推理路径：C++ + RKNN C API。
- 展示路径：服务端输出 JSON，浏览器 Canvas 叠加检测框。
- 无人机专用版本：`D:\Desktop\rk3576\workspace\drone_yolo_web_cpp_ws`。

## 目录结构

```text
yolo_web_cpp_ws/
  models/                  通用 RKNN 模型
  scripts/board/           开发板启动/停止脚本
  scripts/windows/         Windows 一键启动/停止脚本，包含 ADB 端口映射
  src/vision_msgs/         vendored ROS 视觉检测消息
  src/yolo_web_cpp/        ROS2 C++ 推理和 Web 包
```

## 默认配置

| 项目 | 默认值 |
| --- | --- |
| 输入话题 | `/camera/image_mjpeg` |
| RKNN 模型 | `/home/lckfb/workspace/yolo/yolo_web_cpp_ws/models/yolo11.rknn` |
| 标签 | `coco` |
| YOLO Web 端口 | `8092` |
| 摄像头原始流 | `http://127.0.0.1:8081/stream.mjpg` |
| 检测 JSON | `http://127.0.0.1:8092/detections` |
| ROS 检测话题 | `/yolo/detections` |
| 消息类型 | `vision_msgs/msg/Detection2DArray` |

## 数据流

```text
camera_web_cpp
  /dev/video73 -> /camera/image_mjpeg -> http://127.0.0.1:8081/stream.mjpg

yolo_web_cpp
  /camera/image_mjpeg -> JPEG 解码 -> RKNN C API -> YOLO 后处理
  -> /detections JSON
  -> /yolo/detections ROS 话题

browser
  原始 MJPEG 图像 + Canvas 检测框
```

## 构建

在开发板上执行：

```bash
cd /home/lckfb/workspace/yolo/yolo_web_cpp_ws
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install --packages-up-to yolo_web_cpp
```

## 启动

Windows 一键启动完整链路，并自动转发 `8081` 和 `8092`：

```powershell
powershell -ExecutionPolicy Bypass -File D:\Desktop\rk3576\workspace\yolo_web_cpp_ws\scripts\windows\start_camera_yolo_cpp_all.ps1
```

切换到 `1280x720` 时，摄像头脚本会自动请求 `30 FPS`：

```powershell
powershell -ExecutionPolicy Bypass -File D:\Desktop\rk3576\workspace\yolo_web_cpp_ws\scripts\windows\start_camera_yolo_cpp_all.ps1 -Size 1280x720
```

覆盖模型和标签：

```powershell
powershell -ExecutionPolicy Bypass -File D:\Desktop\rk3576\workspace\yolo_web_cpp_ws\scripts\windows\start_camera_yolo_cpp_all.ps1 -Model /home/lckfb/workspace/yolo/yolo_web_cpp_ws/models/yolo11.rknn -Labels coco
```

开发板直接启动完整链路：

```bash
/home/lckfb/workspace/yolo/yolo_web_cpp_ws/scripts/board/start_camera_yolo_cpp_all.sh
```

## 关闭

Windows 一键关闭完整链路，并移除 ADB 转发：

```powershell
powershell -ExecutionPolicy Bypass -File D:\Desktop\rk3576\workspace\yolo_web_cpp_ws\scripts\windows\stop_camera_yolo_cpp_all.ps1
```

开发板直接关闭：

```bash
/home/lckfb/workspace/yolo/yolo_web_cpp_ws/scripts/board/stop_camera_yolo_cpp_all.sh
```

## Web 接口

| 路径 | 说明 |
| --- | --- |
| `/` 或 `/index.html` | 原始视频 + Canvas 检测框页面 |
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
curl http://127.0.0.1:8092/health
curl http://127.0.0.1:8092/detections
source /opt/ros/jazzy/setup.bash
source /home/lckfb/workspace/yolo/yolo_web_cpp_ws/install/setup.bash
ros2 topic echo /yolo/detections --once
```

Windows 侧确认端口映射：

```powershell
adb forward --list
```

包内详细说明见 `src\yolo_web_cpp\README.md`。
