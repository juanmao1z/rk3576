# drone_yolo_web_cpp

C++ + RKNN C API 版无人机实时检测项目。

这个包负责无人机 YOLO 推理和检测框输出。浏览器直接显示 C++ 摄像头节点在 `8081` 提供的原始 MJPEG 流，本包在 `8092` 提供页面和 `/detections` JSON，前端 Canvas 负责叠加检测框；同时发布 ROS 检测结果话题 `/yolo/detections`。

## 工作区结构

```text
drone_yolo_web_cpp_ws/
  models/
    yolo11n.rknn
    yolov5.rknn
  scripts/
    board/
      start_drone_yolo_cpp_all.sh
      stop_drone_yolo_cpp_all.sh
      start_drone_yolo_web_cpp.sh
      stop_drone_yolo_web_cpp.sh
    windows/
      start_drone_yolo_cpp_all.ps1
      stop_drone_yolo_cpp_all.ps1
  src/
    vision_msgs/
      msg/
    drone_yolo_web_cpp/
      include/drone_yolo_web_cpp/
      launch/
      src/
      third_party/rknpu2/include/
```

根目录只保留三类内容：模型、脚本、ROS2 源码。旧 Python YOLO、ONNX 运行分支不属于当前 C++ 主路径。

## 默认配置

- 输入话题：`/camera/image_mjpeg`
- RKNN 模型：`/home/lckfb/workspace/drone_yolo_web_cpp_ws/models/yolo11n.rknn`
- 检测标签：`drone`，多类别模型可用逗号分隔字符串，例如 `drone,bird`
- YOLO Web 端口：`8092`
- 原始视频来源：`http://127.0.0.1:8081/stream.mjpg`
- 检测框接口：`http://127.0.0.1:8092/detections`
- ROS 检测结果话题：`/yolo/detections`
- FPS 统计窗口：最近 `2.0` 秒内完成推理的帧

## 运行架构

```text
camera_web_cpp
  /dev/video73 -> V4L2 MJPEG -> /camera/image_mjpeg -> http://127.0.0.1:8081/stream.mjpg

drone_yolo_web_cpp
  /camera/image_mjpeg -> JPEG decode -> RKNN C API -> YOLO11 drone postprocess
  -> /detections JSON
  -> /yolo/detections ROS topic

browser
  <img src="http://127.0.0.1:8081/stream.mjpg"> + Canvas detection overlay
```

服务端不生成带框 JPEG 结果流，也没有 `jpeg_quality` 参数。仍然需要 JPEG 解码，因为 RKNN 推理输入需要像素矩阵。

## 代码结构

- `include/drone_yolo_web_cpp/yolo_overlay_node.hpp`：ROS2 节点、订阅和结果缓存
- `include/drone_yolo_web_cpp/yolo11_rknn_detector.hpp`：RKNN C API 推理、YOLO11 后处理和 NMS
- `include/drone_yolo_web_cpp/http_overlay_server.hpp`：轻量 HTTP 服务
- `include/drone_yolo_web_cpp/json_utils.hpp`：JSON 和 health 文本输出
- `src/drone_yolo_web_cpp_node.cpp`：入口函数

## 构建

在开发板上执行：

```bash
cd /home/lckfb/workspace/drone_yolo_web_cpp_ws
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install --packages-up-to drone_yolo_web_cpp
```

## 一键启动和关闭

Windows 侧启动完整 C++ 链路，并自动设置 ADB 端口映射：

```powershell
powershell -ExecutionPolicy Bypass -File .\drone_yolo_web_cpp_ws\scripts\windows\start_drone_yolo_cpp_all.ps1
```

默认使用 n 模型。切换到 s 模型：

```powershell
powershell -ExecutionPolicy Bypass -File .\drone_yolo_web_cpp_ws\scripts\windows\start_drone_yolo_cpp_all.ps1 -Size 1280x720 -Model /home/lckfb/workspace/trained_yolo11s_best_rk3576_i8.rknn
```

切换到 YOLOv5 模型：

```powershell
powershell -ExecutionPolicy Bypass -File .\drone_yolo_web_cpp_ws\scripts\windows\start_drone_yolo_cpp_all.ps1 -Model /home/lckfb/workspace/drone_yolo_web_cpp_ws/models/yolov5.rknn -Labels UAV
```

覆盖标签：

```powershell
powershell -ExecutionPolicy Bypass -File .\drone_yolo_web_cpp_ws\scripts\windows\start_drone_yolo_cpp_all.ps1 -Labels drone
```

Windows 侧关闭完整 C++ 链路，并移除 `8081/8092` 映射：

```powershell
powershell -ExecutionPolicy Bypass -File .\drone_yolo_web_cpp_ws\scripts\windows\stop_drone_yolo_cpp_all.ps1
```

开发板侧启动：

```bash
/home/lckfb/workspace/drone_yolo_web_cpp_ws/scripts/board/start_drone_yolo_cpp_all.sh
```

开发板侧切换模型：

```bash
RKNN_MODEL=/home/lckfb/workspace/trained_yolo11s_best_rk3576_i8.rknn \
/home/lckfb/workspace/drone_yolo_web_cpp_ws/scripts/board/start_drone_yolo_cpp_all.sh --size 1280x720
```

开发板侧切换到 YOLOv5 模型：

```bash
RKNN_MODEL=/home/lckfb/workspace/drone_yolo_web_cpp_ws/models/yolov5.rknn DETECTION_LABELS=UAV \
/home/lckfb/workspace/drone_yolo_web_cpp_ws/scripts/board/start_drone_yolo_cpp_all.sh
```

开发板侧关闭：

```bash
/home/lckfb/workspace/drone_yolo_web_cpp_ws/scripts/board/stop_drone_yolo_cpp_all.sh
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
/home/lckfb/workspace/drone_yolo_web_cpp_ws/scripts/board/start_drone_yolo_web_cpp.sh
```

## Web 接口

- `/` 或 `/index.html`：原始视频 + Canvas 检测框页面
- `/detections`：最新检测框 JSON
- `/health`：轻量健康检查

`/health` 示例：

```text
frames=426 age=0.013 result_fps=24.975 last_pipeline_ms=38.008 last_decode_ms=10.560 last_inference_ms=23.464 last_postprocess_ms=3.985
```

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

字段包括：

```text
header
detections[]
```

每个 `detections[]` 元素包含：

```text
header
results[]
bbox
id
```

其中 `bbox.center.position.x/y` 是检测框中心点，`bbox.size_x/size_y` 是宽高，单位都是原始图像像素。`results[0].hypothesis.class_id` 是类别 ID 字符串，`results[0].hypothesis.score` 是置信度；`id` 保存类别标签文本。FPS 和耗时字段不属于标准 `vision_msgs`，继续通过 HTTP `/detections` 或 `/health` 查看。

验证命令：

```bash
source /opt/ros/jazzy/setup.bash
source /home/lckfb/workspace/drone_yolo_web_cpp_ws/install/setup.bash
ros2 topic echo /yolo/detections --once
```

## FPS 统计口径

`result_fps` 是 Drone YOLO C++ 节点最近滑动窗口内完成推理并更新结果的帧率。它不是摄像头采集 FPS、浏览器刷新 FPS，也不是 `/detections` 的 HTTP 请求频率。

外部验证方法：

```bash
curl http://127.0.0.1:8092/detections
sleep 5
curl http://127.0.0.1:8092/detections
```

用两次 `frame` 差值除以真实耗时，应接近第二次返回的 `result_fps`。

## 常用验证

```bash
curl http://127.0.0.1:8081/health
curl http://127.0.0.1:8092/health
curl http://127.0.0.1:8092/detections
source /opt/ros/jazzy/setup.bash && source /home/lckfb/workspace/drone_yolo_web_cpp_ws/install/setup.bash && ros2 topic list | grep /yolo/detections
ss -ltnp | grep -E ':(8081|8092) '
```

Windows 侧确认映射：

```powershell
adb forward --list
```

## 注意事项

- `8092` 页面的视频来自 `8081`，所以摄像头服务必须先启动。
- `last_pipeline_ms` 包含 JPEG 解码、letterbox、RKNN 推理、输出获取和后处理。
- `last_inference_ms` 只覆盖 RKNN `run + outputs_get`。
- 当前 C++ 主路径不依赖 ONNX、ONNX Runtime 或 Python YOLO 服务。
