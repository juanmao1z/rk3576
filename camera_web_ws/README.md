# camera_web_ws

RK3576 开发板上的 Python 摄像头 MJPEG Web 工作区。它是早期/备用实现，用 OpenCV 读取摄像头，把原始图像发布为 ROS2 `Image`，再由 Python HTTP 服务重新编码为 MJPEG。

## 项目定位

- 当前主线优先使用 `camera_web_cpp_ws`。
- 本工作区保留用于对照、回退和 Python 链路验证。
- 与 C++ 版相比，本版会经历 `读取图像 -> 发布 Image -> JPEG 编码 -> Web 输出`，CPU 开销更高。

## 目录结构

```text
camera_web_ws/
  start_camera_web.sh             开发板启动脚本
  stop_camera_web.sh              开发板关闭脚本
  src/camera_web_bridge/          ROS2 Python 包
    camera_web_bridge/            摄像头发布和 MJPEG 服务源码
    launch/                       ROS2 launch 配置
```

## 默认配置

| 项目 | 默认值 |
| --- | --- |
| 摄像头设备 | `/dev/video73` |
| 默认分辨率 | `1280x720` |
| 默认帧率 | `30 FPS` |
| ROS2 原始图像话题 | `/camera/image_raw` |
| Web 端口 | `8080` |

## 数据流

```text
/dev/video73
  -> OpenCV VideoCapture
  -> sensor_msgs/msg/Image
  -> /camera/image_raw
  -> Python/OpenCV JPEG 编码
  -> http://127.0.0.1:8080/stream.mjpg
```

## 构建

```bash
cd /home/lckfb/workspace/ros/camera_web_ws
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install
```

## 启动

```bash
source /opt/ros/jazzy/setup.bash
source /home/lckfb/workspace/ros/camera_web_ws/install/setup.bash
ros2 launch camera_web_bridge camera_web.launch.py
```

覆盖摄像头参数：

```bash
ros2 launch camera_web_bridge camera_web.launch.py device:=/dev/video73 width:=1280 height:=720 fps:=15 port:=8080
```

## Web 接口

| 路径 | 说明 |
| --- | --- |
| `/` 或 `/index.html` | 摄像头预览页面 |
| `/stream.mjpg` | MJPEG 视频流 |
| `/snapshot.jpg` | 最新 JPEG 截图 |
| `/health` | 帧计数和最新帧年龄 |

## 验证

```bash
curl http://127.0.0.1:8080/health
ros2 topic hz /camera/image_raw
```

包内详细说明见 `src\camera_web_bridge\README.md`。
