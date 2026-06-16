# Artifacts And Generated Files

workspace 大文件、生成物和核心资产说明。清理目录前先看这里，避免误删模型、数据集或上板依赖。

## 可重建或可重新下载

| 路径 | 说明 |
| --- | --- |
| `drone_pt_detector\.venv` | Windows Python 虚拟环境，可用 `drone_pt_detector\scripts\setup_env.ps1` 重建 |
| `drone_pt_detector\runs` | YOLO 预测、验证、训练输出，可重新运行生成 |
| `drone_pt_detector\models\_hf_cache` | Hugging Face 下载缓存，可重新下载 |
| `drone_pt_detector\data\open_datasets\kc34251_drone_detection` | 公开 Hugging Face 测试集，可用 `download_dataset.ps1` 重下 |
| `drone_pt_detector\data\open_datasets\maciullo_snippet\downloads` | Maciullo snippet 原始 zip，可重新下载 |
| `drone_pt_detector\runs\damoyolo_*` | DAMO-YOLO 测试和评估输出，可用 `test_damoyolo_uav.ps1` 重建 |
| `third_party\DAMO-YOLO-master.zip` | DAMO-YOLO 源码压缩包，源码目录存在时可删除 |
| `rknn_model_zoo\rknn_model_zoo\build` | Model Zoo 构建输出，可重建 |
| `rknn_model_zoo\rknn_model_zoo\install` | Model Zoo 安装输出，可重建 |
| `docs\generated` | 文档生成项目和输出，可由对应生成流程重建 |
| `tmp_gs_usb_rk3576_build` | `gs_usb` 临时构建试验区，可按内核源码和 Makefile 重建 |
| `gimbal_dm_h3510_ws\cpp_v1_1_smoke\build` | PC 烟测 C++ 构建输出，可由 CMake 重建 |

## 核心资产

| 路径 | 说明 |
| --- | --- |
| `drone_pt_detector\models\flying_objects_yolov8m.pt` | 当前无人机预训练 `.pt` 模型 |
| `drone_pt_detector\models\damoyolo_tinynasL25_S_uav.pt` | ModelScope DAMO-YOLO UAV checkpoint |
| `drone_pt_detector\models\flying_objects_yolov8m.onnx` | 已导出的 ONNX 模型 |
| `yolo_web_cpp_ws\models\yolo11.rknn` | 通用 C++ Web 工作区使用的 RKNN 模型 |
| `yolo_web_py_ws\models\yolo11.rknn` | Python Web 工作区使用的 RKNN 模型 |
| `yolo_web_py_canvas_ws\models\yolo11.rknn` | Python Canvas 工作区使用的 RKNN 模型 |
| `/home/lckfb/workspace/trained_yolo11n_best_rk3576_i8.rknn` | 开发板侧无人机 C++ 默认模型 |
| `/home/lckfb/workspace/trained_yolo11s_best_rk3576_i8.rknn` | 开发板侧无人机 C++ 可选 s 模型 |
| `rknn_yolo11\rknn_yolo11\rknn_yolo11_cpp\model\yolo11.rknn` | 独立 C++ 示例使用的 RKNN 模型 |
| `packages\ros\ros-jazzy-vision-msgs_4.1.1-3noble.20260412.091152_arm64.deb` | ROS Jazzy `vision_msgs` arm64 安装包 |
| `dm_h3510_ros_ws\python\src\dm_h3510_ros_py` | DM-H3510 Python ROS2 驱动源码 |
| `dm_h3510_ros_ws\cpp\src\dm_h3510_ros_cpp` | DM-H3510 C++ ROS2 驱动源码 |
| `gimbal_dm_h3510_ws\cpp_v1_1_smoke\vendor\dm_device_sdk\dm_device.lib` | PC 烟测依赖的达妙 SDK 库文件 |

## 低风险清理顺序

1. 删除 `drone_pt_detector\runs`。
2. 删除 Python `__pycache__`。
3. 删除 `drone_pt_detector\models\_hf_cache`。
4. 删除 `third_party\DAMO-YOLO-master.zip`，前提是源码目录还在。
5. 删除 `rknn_model_zoo\rknn_model_zoo\build` 和 `install`，前提是当前不需要这些构建产物。
6. 删除 `docs\generated`，前提是已确认不需要当前生成的 DOCX 输出。
7. 删除 `tmp_gs_usb_rk3576_build`，前提是当前不再继续调试 `gs_usb` 构建。
8. 删除 `gimbal_dm_h3510_ws\cpp_v1_1_smoke\build`，前提是保留源码和 SDK 依赖。

## 不建议清理

- `models` 目录里的 `.rknn`、`.pt`、`.onnx`。
- `dm_h3510_ros_ws` 里的 Python/C++ ROS2 驱动源码、配置和脚本。
- `gimbal_dm_h3510_ws\config` 和 `gimbal_dm_h3510_ws\docs`，后续会保存云台标定、接线和协议记录。
- `gimbal_dm_h3510_ws\cpp_v1_1_smoke\vendor`，PC 烟测依赖这里的 SDK 文件。
- `src/vision_msgs`，它是各 YOLO 工作区的 ROS 消息依赖。
- `scripts/board` 和 `scripts/windows`，它们是上板和 ADB 转发入口。
- `third_party\DAMO-YOLO-master`，除非确认不再测试 DAMO-YOLO checkpoint。
