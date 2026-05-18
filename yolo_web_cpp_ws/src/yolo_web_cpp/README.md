# yolo_web_cpp

通用 C++ + RKNN C API YOLO Canvas 叠加项目。

这个包订阅 C++ 摄像头节点发布的 `/camera/image_mjpeg`，用 RKNN C API 做 YOLO 推理，在 `8092` 提供 Web 页面和 `/detections` JSON。浏览器直接显示 `8081` 的原始 MJPEG 流，检测框由前端 Canvas 叠加；推理结果同时发布到 ROS 话题 `/yolo/detections`。

无人机专用版本在独立工作区 `drone_yolo_web_cpp_ws`，本工作区保持通用 YOLO 用途。

## 工作区结构

```text
yolo_web_cpp_ws/
  models/
    yolo11.rknn
  scripts/
    board/
      start_camera_yolo_cpp_all.sh
      stop_camera_yolo_cpp_all.sh
      start_yolo_web_cpp.sh
      stop_yolo_web_cpp.sh
    windows/
      start_camera_yolo_cpp_all.ps1
      stop_camera_yolo_cpp_all.ps1
  src/
    vision_msgs/
      msg/
    yolo_web_cpp/
      include/yolo_web_cpp/
      launch/
      src/
      third_party/rknpu2/include/
```

## 默认配置

- 输入话题：`/camera/image_mjpeg`
- RKNN 模型：`/home/lckfb/workspace/yolo/yolo_web_cpp_ws/models/yolo11.rknn`
- 检测标签：`coco`
- YOLO Web 端口：`8092`
- 原始视频来源：`http://127.0.0.1:8081/stream.mjpg`
- 检测框接口：`http://127.0.0.1:8092/detections`
- ROS 检测结果话题：`/yolo/detections`
- FPS 统计窗口：最近 `2.0` 秒内完成推理的帧

## 运行架构

```text
camera_web_cpp
  /dev/video73 -> V4L2 MJPEG -> /camera/image_mjpeg -> http://127.0.0.1:8081/stream.mjpg

yolo_web_cpp
  /camera/image_mjpeg -> JPEG decode -> RKNN C API -> YOLO postprocess
  -> /detections JSON
  -> /yolo/detections ROS topic

browser
  <img src="http://127.0.0.1:8081/stream.mjpg"> + Canvas detection overlay
```

服务端不生成带框 JPEG 结果流，也没有 `jpeg_quality` 参数。仍然需要 JPEG 解码，因为 RKNN 推理输入需要像素矩阵。

## 构建

在开发板上执行：

```bash
cd /home/lckfb/workspace/yolo/yolo_web_cpp_ws
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install --packages-up-to yolo_web_cpp
```

## 一键启动和关闭

Windows 侧启动完整 C++ 链路，并自动设置 ADB 端口映射：

```powershell
powershell -ExecutionPolicy Bypass -File D:\Desktop\rk3576\workspace\yolo_web_cpp_ws\scripts\windows\start_camera_yolo_cpp_all.ps1
```

切换到 `1280x720`：

```powershell
powershell -ExecutionPolicy Bypass -File D:\Desktop\rk3576\workspace\yolo_web_cpp_ws\scripts\windows\start_camera_yolo_cpp_all.ps1 -Size 1280x720
```

覆盖模型或标签：

```powershell
powershell -ExecutionPolicy Bypass -File D:\Desktop\rk3576\workspace\yolo_web_cpp_ws\scripts\windows\start_camera_yolo_cpp_all.ps1 -Model /home/lckfb/workspace/yolo/yolo_web_cpp_ws/models/yolo11.rknn -Labels coco
```

Windows 侧关闭完整 C++ 链路，并移除 `8081/8092` 映射：

```powershell
powershell -ExecutionPolicy Bypass -File D:\Desktop\rk3576\workspace\yolo_web_cpp_ws\scripts\windows\stop_camera_yolo_cpp_all.ps1
```

开发板侧启动：

```bash
/home/lckfb/workspace/yolo/yolo_web_cpp_ws/scripts/board/start_camera_yolo_cpp_all.sh
```

开发板侧关闭：

```bash
/home/lckfb/workspace/yolo/yolo_web_cpp_ws/scripts/board/stop_camera_yolo_cpp_all.sh
```

启动成功后打开：

```text
http://127.0.0.1:8092/
```

## 单独启动 YOLO 服务

先确保摄像头服务已经运行：

```bash
/home/lckfb/workspace/ros/camera_web_cpp_ws/start_camera_web_cpp.sh
```

再启动 YOLO：

```bash
/home/lckfb/workspace/yolo/yolo_web_cpp_ws/scripts/board/start_yolo_web_cpp.sh
```

## Web 接口

- `/` 或 `/index.html`：原始视频 + Canvas 检测框页面
- `/detections`：最新检测框 JSON
- `/health`：轻量健康检查

`/detections` 示例：

```json
{
  "frame": 426,
  "image_width": 640,
  "image_height": 480,
  "result_fps": 24.975,
  "fps_window": "completed inference frames over recent sliding window",
  "last_pipeline_ms": 38.008,
  "last_decode_ms": 10.56,
  "last_inference_ms": 23.464,
  "last_postprocess_ms": 3.985,
  "age": 0.031,
  "detections": []
}
```

## ROS 检测结果话题

推理完成后会发布：

```text
/yolo/detections
```

消息类型：

```text
vision_msgs/msg/Detection2DArray
```

验证命令：

```bash
source /opt/ros/jazzy/setup.bash
source /home/lckfb/workspace/yolo/yolo_web_cpp_ws/install/setup.bash
ros2 topic echo /yolo/detections --once
```

## FPS 统计口径

`result_fps` 是 YOLO C++ 节点最近滑动窗口内完成推理并更新结果的帧率。它不是摄像头采集 FPS、浏览器刷新 FPS，也不是 `/detections` 的 HTTP 请求频率。

## 常用验证

```bash
curl http://127.0.0.1:8081/health
curl http://127.0.0.1:8092/health
curl http://127.0.0.1:8092/detections
source /opt/ros/jazzy/setup.bash && source /home/lckfb/workspace/yolo/yolo_web_cpp_ws/install/setup.bash && ros2 topic list | grep /yolo/detections
ss -ltnp | grep -E ':(8081|8092) '
```

Windows 侧确认映射：

```powershell
adb forward --list
```
