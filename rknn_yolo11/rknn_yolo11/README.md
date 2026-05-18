# RKNN YOLO11 使用总览

本目录用于统一管理 RK3576 开发板上的 YOLO11 相关内容。

建议在开发板上使用的总目录为：

```sh
/home/lckfb/rknn_yolo11
```

目录结构如下：

- `rknn_yolo11_cpp`
- `rknn_yolo11_demo`
- `rknn_yolo11_python`

## 1. 目录说明

### 1.1 `rknn_yolo11_cpp`

保存 C++ 版实时推理相关内容，包括：

- C++ 源码副本
- `build_native`
- `lib`
- `model`
- `rknn_yolo11_demo_camera_native`

主要可执行文件：

```sh
/home/lckfb/rknn_yolo11/rknn_yolo11_cpp/rknn_yolo11_demo_camera_native
```

### 1.2 `rknn_yolo11_demo`

保存原始 C++ Demo 编译产物，包括：

- `rknn_yolo11_demo`
- `rknn_yolo11_demo_zero_copy`
- `lib`
- `model`

### 1.3 `rknn_yolo11_python`

保存 Python 版脚本和使用说明，包括：

- `rknn_yolo11_camera_realtime_v2.py`
- `rknn_yolo11_python_usage.md`

## 2. 模型路径

统一使用以下模型路径：

```sh
/home/lckfb/rknn_yolo11/rknn_yolo11_cpp/model/yolo11.rknn
```

## 3. C++ 运行方式

进入目录：

```sh
cd /home/lckfb/rknn_yolo11/rknn_yolo11_cpp
export LD_LIBRARY_PATH=/home/lckfb/rknn_yolo11/rknn_yolo11_cpp/lib:$LD_LIBRARY_PATH
```

### 3.1 摄像头实时检测

```sh
./rknn_yolo11_demo_camera_native model/yolo11.rknn /dev/video73
```

### 3.2 摄像头实时检测但不显示窗口

```sh
./rknn_yolo11_demo_camera_native model/yolo11.rknn /dev/video73 --no-display
```

### 3.3 视频文件基准测试

```sh
./rknn_yolo11_demo_camera_native model/yolo11.rknn /home/lckfb/Videos/pedestrian_detection_test_video_1.flv \
  --no-display \
  --benchmark \
  --warmup 30 \
  --max-frames 330
```

## 4. Python 运行方式

Python 脚本依赖 RKNN 虚拟环境：

```sh
/home/lckfb/.venvs/rknn/bin/python
```

### 4.1 摄像头实时检测

```sh
/home/lckfb/.venvs/rknn/bin/python /home/lckfb/rknn_yolo11/rknn_yolo11_python/rknn_yolo11_camera_realtime_v2.py \
  --model /home/lckfb/rknn_yolo11/rknn_yolo11_cpp/model/yolo11.rknn \
  --source /dev/video73 \
  --backend v4l2
```

### 4.2 视频文件检测

```sh
/home/lckfb/.venvs/rknn/bin/python /home/lckfb/rknn_yolo11/rknn_yolo11_python/rknn_yolo11_camera_realtime_v2.py \
  --model /home/lckfb/rknn_yolo11/rknn_yolo11_cpp/model/yolo11.rknn \
  --source /home/lckfb/Videos/pedestrian_detection_test_video_1.flv \
  --backend v4l2 \
  --no-show
```

### 4.3 保存结果视频

```sh
/home/lckfb/.venvs/rknn/bin/python /home/lckfb/rknn_yolo11/rknn_yolo11_python/rknn_yolo11_camera_realtime_v2.py \
  --model /home/lckfb/rknn_yolo11/rknn_yolo11_cpp/model/yolo11.rknn \
  --source /home/lckfb/Videos/pedestrian_detection_test_video_1.flv \
  --backend v4l2 \
  --no-show \
  --save /home/lckfb/yolo11_result.mp4
```

更详细的 Python 使用说明见：

```sh
/home/lckfb/rknn_yolo11/rknn_yolo11_python/rknn_yolo11_python_usage.md
```

## 5. 常见问题

### 5.1 摄像头被占用

查看占用者：

```sh
fuser -v /dev/video73
```

### 5.2 正确退出程序

退出请使用：

```sh
Ctrl+C
```

不要使用：

```sh
Ctrl+Z
```

因为 `Ctrl+Z` 只是挂起进程，不会释放摄像头。

### 5.3 查看 CPU / NPU 利用率

查看 CPU：

```sh
top
```

查看 NPU：

```sh
cat /sys/class/devfreq/27700000.npu/load
cat /sys/kernel/debug/rknpu/load
```

## 6. 推荐入口

如果你只记一个总目录，请使用：

```sh
cd /home/lckfb/rknn_yolo11
```
