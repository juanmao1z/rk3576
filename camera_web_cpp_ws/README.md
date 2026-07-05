# camera_web_cpp_ws

RK3576 开发板上的 C++ 摄像头 MJPEG Web 工作区。它负责从 USB 摄像头或 RTSP 网络摄像头读取图像，发布 ROS2 压缩图像话题，并把同一份帧数据转发给浏览器。

下面的 Windows 命令默认从 RK3576 项目目录执行。

## 项目定位

- 主用途：提供低开销摄像头原始流，供 YOLO C++、YOLO Python 和浏览器预览共同使用。
- 当前主线：优先使用本 C++ 工作区，`camera_web_ws` 仅作为 Python 旧版/备用实现。
- 性能边界：USB MJPEG 路径不解码图像、不画框、不重新编码 JPEG；RTSP H.264 路径会解码并编码为 JPEG，再发布给下游。

## 目录结构

```text
camera_web_cpp_ws/
  start_camera_web_cpp.sh       开发板启动脚本
  start_multi_camera_web_cpp.sh 开发板双路摄像头启动脚本
  start_rtsp_camera_web_cpp.sh  开发板 RTSP 启动脚本
  stop_camera_web_cpp.sh        开发板关闭脚本
  stop_multi_camera_web_cpp.sh  开发板双路摄像头关闭脚本
  src/camera_web_cpp/           ROS2 C++ 包
    include/camera_web_cpp/     组件头文件
    launch/                     ROS2 launch 配置
    src/                        V4L2 采集和 HTTP 转发实现
```

## 默认配置

| 项目 | 默认值 |
| --- | --- |
| 摄像头设备 | `/dev/video73` |
| RTSP 输入 | 通过 `start_rtsp_camera_web_cpp.sh --rtsp-url` 指定 |
| 图像格式 | `MJPEG` |
| 默认分辨率 | `640x480` |
| 默认帧率 | `25 FPS` |
| `1280x720` 帧率 | `30 FPS` |
| ROS2 话题 | `/camera/image_mjpeg` |
| Web 端口 | `8081` |
| 双路摄像头话题 | `/camera/front/image_mjpeg`、`/camera/left/image_mjpeg` |
| 双路摄像头端口 | `8081`、`8082` |
| 浏览器地址 | `http://127.0.0.1:8081/` |

## 数据流

```text
/dev/video73
  -> V4L2 MMAP 读取 MJPEG 压缩帧
  -> sensor_msgs/msg/CompressedImage
  -> /camera/image_mjpeg
  -> http://127.0.0.1:8081/stream.mjpg
```

RTSP 网络摄像头路径：

```text
rtsp://admin:Lgw2003823@192.168.110.47:554/Streaming/Channels/101
  -> OpenCV/FFmpeg 读取 H.264
  -> JPEG 编码
  -> sensor_msgs/msg/CompressedImage
  -> /camera/image_mjpeg
  -> http://127.0.0.1:8081/stream.mjpg
```

双路 USB 摄像头路径：

```text
/dev/video73 -> /camera/front/image_mjpeg -> http://<board-ip>:8081/stream.mjpg
/dev/video75 -> /camera/left/image_mjpeg  -> http://<board-ip>:8082/stream.mjpg
```

## 构建

在开发板上执行：

```bash
cd /home/lckfb/workspace/ros/camera_web_cpp_ws
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install --packages-select camera_web_cpp
```

## 启动

开发板直接启动：

```bash
/home/lckfb/workspace/ros/camera_web_cpp_ws/start_camera_web_cpp.sh
```

切换到 `1280x720@30`：

```bash
/home/lckfb/workspace/ros/camera_web_cpp_ws/start_camera_web_cpp.sh --size 1280x720
```

启动 RTSP 网络摄像头：

```bash
/home/lckfb/workspace/ros/camera_web_cpp_ws/start_rtsp_camera_web_cpp.sh \
  --rtsp-url "rtsp://admin:Lgw2003823@192.168.110.47:554/Streaming/Channels/101" \
  --size 1280x960 \
  --fps 25
```

Windows 统一入口会自动通过 ADB 启动开发板服务并转发 `8081`：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\start_camera_cpp.ps1
```

启动双路 USB 摄像头：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\start_multi_camera_cpp.ps1
```

默认开发板地址是 `192.168.137.217`，页面是：

```text
http://192.168.137.217:8081/
http://192.168.137.217:8082/
```

## 关闭

开发板直接关闭：

```bash
/home/lckfb/workspace/ros/camera_web_cpp_ws/stop_camera_web_cpp.sh
```

Windows 统一入口：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\stop_camera_cpp.ps1
```

关闭双路 USB 摄像头：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\stop_multi_camera_cpp.ps1
```

## Web 接口

| 路径 | 说明 |
| --- | --- |
| `/` 或 `/index.html` | 摄像头预览页面 |
| `/stream.mjpg` | 原始 MJPEG 视频流 |
| `/snapshot.jpg` | 最新一帧 JPEG |
| `/health` | 帧计数和最新帧年龄 |
| `/metrics` | FPS、CPU 和链路指标 JSON |

## 验证

```bash
curl http://127.0.0.1:8081/health
curl http://127.0.0.1:8081/metrics
ss -ltnp | grep 8081
```

RTSP 输入正常时，`/health` 中 `frames` 会持续增加。网络摄像头当前验证过的码流为 `1280x960@25`。

Windows 侧检查 ADB 转发：

```powershell
adb forward --list
```

包内详细说明见 `src\camera_web_cpp\README.md`。
