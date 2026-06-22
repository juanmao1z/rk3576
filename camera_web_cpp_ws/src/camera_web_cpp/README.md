# camera_web_cpp

RK3576 上使用的 C++ 版摄像头 Web 预览节点。

这个包的目标是把 USB 摄像头或 RTSP 网络摄像头的画面送到浏览器，同时把同一份压缩图像发布给后续 YOLO 节点使用。

## 当前默认配置

- 摄像头设备：`/dev/video73`
- 摄像头格式：`MJPEG`
- RTSP 输入：通过 `rtsp_camera_web_cpp.launch.py` 或 `start_rtsp_camera_web_cpp.sh` 启动
- 分辨率：`640x480`
- 帧率：`25 FPS`
- ROS2 话题：`/camera/image_mjpeg`
- Web 端口：`8081`
- 浏览器地址：`http://127.0.0.1:8081/`

## 架构

launch 文件会启动一个 `rclcpp_components` 多线程组件容器，并在同一个进程内加载两个组件：

1. `CameraMjpegPublisher`
   - 直接使用 V4L2 MMAP 打开 `/dev/video73`
   - 设置摄像头输出 `MJPEG`
   - 阻塞等待新帧
   - 将摄像头给出的 JPEG 字节打包成 `sensor_msgs/msg/CompressedImage`
   - 发布到 `/camera/image_mjpeg`

2. `CompressedMjpegServer`
   - 订阅 `/camera/image_mjpeg`
   - 缓存最新 JPEG 压缩帧
   - 通过 HTTP 提供浏览器 MJPEG 流
   - 提供健康检查、单帧截图和运行指标接口

RTSP 输入会把第一个组件替换为 `RtspMjpegPublisher`：

- 使用 OpenCV/FFmpeg 打开 RTSP URL
- 读取 H.264 视频帧
- 按目标尺寸输出 JPEG
- 发布到同一个 `/camera/image_mjpeg`
- 让下游 YOLO 和 Web 转发逻辑保持不变

双路摄像头会启动两个独立的组件容器：

- front：`/dev/video73` -> `/camera/front/image_mjpeg` -> `8081`
- left：`/dev/video75` -> `/camera/left/image_mjpeg` -> `8082`
- 两路摄像头使用独立话题和端口，避免同一个发布者覆盖另一条链路

两个组件都启用了 `use_intra_process_comms`，压缩帧在同进程内传递，减少 DDS 序列化和额外拷贝。

## 为什么这里不重新编码

USB 摄像头本身已经输出 MJPEG，也就是一帧一帧的 JPEG 压缩数据。USB 路径不会把帧解码成 OpenCV 图像，也不会再执行 JPEG 编码。

这样做的好处是：

- 避免 `decode -> draw -> encode` 的 CPU 开销
- 保留摄像头原始 MJPEG 字节
- 降低端到端延迟
- 让 8081 只负责原始摄像头预览

因此 USB 路径没有 `jpeg_quality` 参数。如果需要改变图像数据量，使用摄像头采集分辨率或帧率参数。当前默认是 `640x480@25`，切到 `1280x720` 时脚本会自动请求 `30 FPS`。

RTSP 路径不同。网络摄像头当前输出 H.264，节点必须解码后再编码为 JPEG。RTSP 启动脚本提供 `--jpeg-quality` 参数，默认值是 `85`。

## Web 接口

- `/` 或 `/index.html`：浏览器预览页面
- `/stream.mjpg`：MJPEG 视频流
- `/snapshot.jpg`：当前最新一帧
- `/health`：轻量健康检查，返回帧计数和最新帧年龄
- `/metrics`：JSON 指标，包含 FPS 和摄像头链路 CPU 估算

示例：

```bash
curl http://127.0.0.1:8081/health
curl http://127.0.0.1:8081/metrics
```

## 构建

在开发板上执行：

```bash
cd /home/lckfb/workspace/ros/camera_web_cpp_ws
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install --packages-select camera_web_cpp
```

## 运行

构建后可以直接使用启动脚本：

```bash
/home/lckfb/workspace/ros/camera_web_cpp_ws/start_camera_web_cpp.sh
```

默认等价于 `640x480@25`。切换到 `1280x720@30`：

```bash
/home/lckfb/workspace/ros/camera_web_cpp_ws/start_camera_web_cpp.sh --size 1280x720
```

也可以显式指定：

```bash
/home/lckfb/workspace/ros/camera_web_cpp_ws/start_camera_web_cpp.sh --width 1280 --height 720 --fps 30
```

RTSP 网络摄像头启动示例：

```bash
/home/lckfb/workspace/ros/camera_web_cpp_ws/start_rtsp_camera_web_cpp.sh \
  --rtsp-url "rtsp://admin:Lgw2003823@192.168.110.47:554/Streaming/Channels/101" \
  --size 1280x960 \
  --fps 25
```

双路 USB 摄像头启动示例：

```bash
/home/lckfb/workspace/ros/camera_web_cpp_ws/start_multi_camera_web_cpp.sh \
  --front-device /dev/video73 \
  --left-device /dev/video75 \
  --size 640x480 \
  --fps 25
```

Windows 侧通过一键 YOLO 脚本启动时也可以传同样的分辨率选项，例如：

```powershell
powershell -ExecutionPolicy Bypass -File D:\Desktop\rk3576\workspace\yolo_web_py_canvas_ws\scripts\windows\start_camera_yolo_py_canvas_all.ps1 -Size 1280x720
```

脚本等价于：

```bash
cd /home/lckfb/workspace/ros/camera_web_cpp_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash

ros2 launch camera_web_cpp camera_web_cpp.launch.py \
  device:=/dev/video73 \
  width:=640 \
  height:=480 \
  fps:=25 \
  port:=8081
```

RTSP 脚本等价于：

```bash
ros2 launch camera_web_cpp rtsp_camera_web_cpp.launch.py \
  rtsp_url:="rtsp://admin:Lgw2003823@192.168.110.47:554/Streaming/Channels/101" \
  width:=1280 \
  height:=960 \
  fps:=25 \
  jpeg_quality:=85 \
  port:=8081
```

双路脚本等价于：

```bash
ros2 launch camera_web_cpp multi_camera_web_cpp.launch.py \
  front_device:=/dev/video73 \
  left_device:=/dev/video75 \
  width:=640 \
  height:=480 \
  fps:=25 \
  front_port:=8081 \
  left_port:=8082
```

如果从 Windows 通过 ADB 查看网页，需要映射端口：

```bash
adb forward tcp:8081 tcp:8081
```

然后在电脑浏览器打开：

```text
http://127.0.0.1:8081/
```

## 常用验证

检查摄像头服务是否有帧：

```bash
curl http://127.0.0.1:8081/health
```

正常时会看到类似：

```text
frames=1234 age=0.02
```

检查端口是否监听：

```bash
ss -ltnp | grep 8081
```

检查 ROS2 话题：

```bash
source /opt/ros/jazzy/setup.bash
source /home/lckfb/workspace/ros/camera_web_cpp_ws/install/setup.bash
ros2 topic hz /camera/image_mjpeg
```

## 与 YOLO 的关系

本包只提供原始摄像头 MJPEG 流和 `/camera/image_mjpeg` 话题。YOLO 节点会订阅这个压缩图像话题，解码后执行 RKNN 推理，再发布带检测框的结果图。

也就是说：

- `8081` 是原始摄像头画面
- `8090` 是 YOLO 结果画面
- 只有 YOLO 结果图因为需要画框，才需要重新生成 JPEG
