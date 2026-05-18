# RKNN YOLO11 Python 使用说明

本目录用于集中保存 `rknn_yolo11*` 相关文件。

当前包含：

- `rknn_yolo11_camera_realtime_v2.py`
- `rknn_yolo11_python_usage.md`

## 1. 脚本用途

`rknn_yolo11_camera_realtime_v2.py` 用于在 RK3576 开发板上运行 YOLO11 的 Python 实时推理。

支持：

- USB 摄像头实时检测
- 视频文件检测
- 结果窗口显示
- 保存检测后的视频

## 2. 运行环境

在开发板上，不要直接使用系统自带的 `python3`。

应使用已经安装 `rknnlite` 的虚拟环境：

```sh
/home/lckfb/.venvs/rknn/bin/python
```

## 3. 模型路径

示例模型路径：

```sh
/home/lckfb/rknn_yolo11_cpp/model/yolo11.rknn
```

## 4. 摄像头实时检测

使用 USB 摄像头 `/dev/video73`：

```sh
/home/lckfb/.venvs/rknn/bin/python /home/lckfb/rknn_yolo11/rknn_yolo11_camera_realtime_v2.py \
  --model /home/lckfb/rknn_yolo11_cpp/model/yolo11.rknn \
  --source /dev/video73 \
  --backend v4l2 \
  --camera-width 1280 \
  --camera-height 720 \
  --camera-fps 30
```

如果不想显示窗口：

```sh
/home/lckfb/.venvs/rknn/bin/python /home/lckfb/rknn_yolo11/rknn_yolo11_camera_realtime_v2.py \
  --model /home/lckfb/rknn_yolo11_cpp/model/yolo11.rknn \
  --source /dev/video73 \
  --backend v4l2 \
  --no-show
```

## 5. 使用视频文件测试

对视频文件 `/home/lckfb/Videos/pedestrian_detection_test_video_1.flv` 做检测：

```sh
/home/lckfb/.venvs/rknn/bin/python /home/lckfb/rknn_yolo11/rknn_yolo11_camera_realtime_v2.py \
  --model /home/lckfb/rknn_yolo11_cpp/model/yolo11.rknn \
  --source /home/lckfb/Videos/pedestrian_detection_test_video_1.flv \
  --backend v4l2 \
  --no-show
```

## 6. 保存检测结果视频

将结果保存为 MP4：

```sh
/home/lckfb/.venvs/rknn/bin/python /home/lckfb/rknn_yolo11/rknn_yolo11_camera_realtime_v2.py \
  --model /home/lckfb/rknn_yolo11_cpp/model/yolo11.rknn \
  --source /home/lckfb/Videos/pedestrian_detection_test_video_1.flv \
  --backend v4l2 \
  --no-show \
  --save /home/lckfb/yolo11_result.mp4
```

## 7. 常用参数说明

- `--model`：RKNN 模型路径，必填
- `--labels`：自定义类别文件，每行一个类别名
- `--source`：摄像头设备、数字索引或视频文件路径
- `--backend`：输入后端，可选 `v4l2` 或 `gst`
- `--width`：模型输入宽度，默认 `640`
- `--height`：模型输入高度，默认 `640`
- `--camera-width`：摄像头采集宽度，默认 `1280`
- `--camera-height`：摄像头采集高度，默认 `720`
- `--camera-fps`：摄像头采集帧率，默认 `30`
- `--conf`：置信度阈值，默认 `0.25`
- `--iou`：NMS 阈值，默认 `0.45`
- `--window`：窗口标题
- `--save`：保存输出视频路径
- `--no-show`：关闭 `cv2.imshow`

## 8. 查看帮助

```sh
/home/lckfb/.venvs/rknn/bin/python /home/lckfb/rknn_yolo11/rknn_yolo11_camera_realtime_v2.py --help
```

## 9. 常见问题

### 9.1 提示 `No module named 'rknnlite'`

说明你用了错误的 Python 解释器。请改用：

```sh
/home/lckfb/.venvs/rknn/bin/python
```

### 9.2 提示 `Device or resource busy`

说明摄像头设备仍被其他进程占用。可以先检查：

```sh
fuser -v /dev/video73
```

然后结束占用进程后再重试。

### 9.3 使用 `Ctrl+Z` 后摄像头无法再次打开

`Ctrl+Z` 只是挂起任务，不会释放摄像头。

退出程序请使用：

```sh
Ctrl+C
```

## 10. 建议目录

如果要在开发板上统一保存这类 Python 文件，建议目录为：

```sh
/home/lckfb/rknn_yolo11
```

可以将本目录中的文件复制到该路径后再运行。
