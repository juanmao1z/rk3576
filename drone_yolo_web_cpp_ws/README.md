# drone_yolo_web_cpp_ws

无人机实时检测 C++ Canvas 工作区。它专门保存 drone 场景的 RKNN C++ 推理代码、启动脚本和文档，不再混在通用 YOLO 工作区里。

## 项目定位

- 主用途：使用摄像头实时检测无人机。
- 推理路径：C++ + RKNN C API。
- 展示路径：浏览器显示原始 MJPEG 流，Canvas 叠加无人机检测框。
- ROS 输出：推理结果发布到 `/yolo/detections`，方便其他 ROS2 节点订阅。
- 与通用 YOLO 的边界：通用模型保留在 `yolo_web_cpp_ws`，本工作区默认只使用 `drone` 标签。

## 目录结构

```text
drone_yolo_web_cpp_ws/
  models/                       可放置无人机 RKNN 模型
  scripts/board/                开发板启动/停止脚本
  scripts/windows/              Windows 一键启动/停止脚本，包含 ADB 端口映射
  src/vision_msgs/              vendored ROS 视觉检测消息
  src/drone_yolo_web_cpp/       ROS2 C++ 推理和 Web 包
```

## 默认配置

| 项目 | 默认值 |
| --- | --- |
| 输入话题 | `/camera/image_mjpeg` |
| RKNN 模型 | `/home/lckfb/workspace/drone_yolo_web_cpp_ws/models/yolo11n.rknn` |
| 标签 | `drone` |
| YOLO Web 端口 | `8092` |
| 摄像头原始流 | `http://127.0.0.1:8081/stream.mjpg` |
| 检测 JSON | `http://127.0.0.1:8092/detections` |
| ROS 检测话题 | `/yolo/detections` |
| 消息类型 | `vision_msgs/msg/Detection2DArray` |

## 数据流

```text
camera_web_cpp
  /dev/video73 -> /camera/image_mjpeg -> http://127.0.0.1:8081/stream.mjpg

drone_yolo_web_cpp
  /camera/image_mjpeg -> JPEG 解码 -> RKNN C API -> YOLO11 drone 后处理
  -> /detections JSON
  -> /yolo/detections ROS 话题

browser
  原始 MJPEG 图像 + Canvas drone 检测框
```

网络摄像头 RTSP 输入时，前半段替换为：

```text
RTSP camera
  rtsp://admin:Lgw2003823@192.168.110.47:554/Streaming/Channels/101
  -> rtsp_camera_web_cpp -> /camera/image_mjpeg
  -> http://127.0.0.1:8081/stream.mjpg
```

## 构建

在开发板上执行：

```bash
cd /home/lckfb/workspace/drone_yolo_web_cpp_ws
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install --packages-up-to drone_yolo_web_cpp
```

## 启动

Windows 一键启动完整链路，并自动转发 `8081` 和 `8092`：

```powershell
powershell -ExecutionPolicy Bypass -File D:\Desktop\rk3576\workspace\drone_yolo_web_cpp_ws\scripts\windows\start_drone_yolo_cpp_all.ps1
```

切换到 `1280x720` 时，摄像头脚本会自动请求 `30 FPS`：

```powershell
powershell -ExecutionPolicy Bypass -File D:\Desktop\rk3576\workspace\drone_yolo_web_cpp_ws\scripts\windows\start_drone_yolo_cpp_all.ps1 -Size 1280x720
```

切换到 s 模型：

```powershell
powershell -ExecutionPolicy Bypass -File D:\Desktop\rk3576\workspace\drone_yolo_web_cpp_ws\scripts\windows\start_drone_yolo_cpp_all.ps1 -Size 1280x720 -Model /home/lckfb/workspace/trained_yolo11s_best_rk3576_i8.rknn
```

切换到 YOLOv5 模型：

```powershell
powershell -ExecutionPolicy Bypass -File D:\Desktop\rk3576\workspace\drone_yolo_web_cpp_ws\scripts\windows\start_drone_yolo_cpp_all.ps1 -Model /home/lckfb/workspace/drone_yolo_web_cpp_ws/models/yolov5.rknn -Labels UAV
```

多类别模型可以传逗号分隔标签：

```powershell
powershell -ExecutionPolicy Bypass -File D:\Desktop\rk3576\workspace\drone_yolo_web_cpp_ws\scripts\windows\start_drone_yolo_cpp_all.ps1 -Labels drone,bird
```

使用网络摄像头 RTSP 输入：

```powershell
powershell -ExecutionPolicy Bypass -File D:\Desktop\rk3576\workspace\drone_yolo_web_cpp_ws\scripts\windows\start_drone_yolo_cpp_all.ps1 -Source rtsp -RtspUrl "rtsp://admin:Lgw2003823@192.168.110.47:554/Streaming/Channels/101" -Size 1280x960 -Fps 25
```

开发板直接启动完整链路：

```bash
/home/lckfb/workspace/drone_yolo_web_cpp_ws/scripts/board/start_drone_yolo_cpp_all.sh --size 1280x720
```

开发板直接使用 RTSP：

```bash
/home/lckfb/workspace/drone_yolo_web_cpp_ws/scripts/board/start_drone_yolo_cpp_all.sh \
  --source rtsp \
  --rtsp-url "rtsp://admin:Lgw2003823@192.168.110.47:554/Streaming/Channels/101" \
  --size 1280x960 \
  --fps 25
```

## 关闭

Windows 一键关闭完整链路，并移除 ADB 转发：

```powershell
powershell -ExecutionPolicy Bypass -File D:\Desktop\rk3576\workspace\drone_yolo_web_cpp_ws\scripts\windows\stop_drone_yolo_cpp_all.ps1
```

开发板直接关闭：

```bash
/home/lckfb/workspace/drone_yolo_web_cpp_ws/scripts/board/stop_drone_yolo_cpp_all.sh
```

## Web 接口

| 路径 | 说明 |
| --- | --- |
| `/` 或 `/index.html` | 原始视频 + Canvas 无人机检测框页面 |
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

`bbox.center.position.x/y` 表示检测框中心点，`bbox.size_x/size_y` 表示宽高，单位都是原始图像像素。`results[0].hypothesis.score` 保存置信度，`id` 保存标签文本。

## 验证

```bash
curl http://127.0.0.1:8081/health
curl http://127.0.0.1:8092/health
curl http://127.0.0.1:8092/detections
source /opt/ros/jazzy/setup.bash
source /home/lckfb/workspace/drone_yolo_web_cpp_ws/install/setup.bash
ros2 topic echo /yolo/detections --once
```

Windows 侧确认端口映射：

```powershell
adb forward --list
```

RTSP 链路已验证的健康检查示例：

```text
camera_web_cpp: frames>0
drone_yolo_web_cpp: result_fps≈25
/detections: image_width=1280, image_height=960
```

包内详细说明见 `src\drone_yolo_web_cpp\README.md`。
