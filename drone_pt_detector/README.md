# drone_pt_detector

Windows PC 端无人机 `.pt` 模型验证、数据集准备、训练和导出工作区。它用于在上板前确认模型效果，生成或筛选适合 RK3576 部署的 YOLO 模型。

## 项目定位

- 主用途：验证“识别天空中的无人机”的 `.pt` 模型。
- 数据用途：下载开源测试集，转换本地 VOC/XML 数据为 YOLO 格式。
- 训练用途：用自有无人机数据继续微调 YOLO。
- 部署关系：本目录不直接跑板端 C++ Web 服务，板端无人机实时检测使用 `drone_yolo_web_cpp_ws`。

## 目录结构

```text
drone_pt_detector/
  models/                 PT/ONNX/RKNN 模型文件
  scripts/                Windows PowerShell 任务脚本
  src/                    模型下载、检测、数据集工具入口
  data/                   数据集模板、下载数据和转换结果
  runs/                   预测、验证、训练输出
```

## 默认模型

| 模型 | 说明 |
| --- | --- |
| `flying_objects_yolov8m` | Hugging Face `Javvanny/yolov8m_flying_objects_detection`，适合地面摄像头识别空中目标 |
| `visdrone_yolov8n` | 用于无人机航拍视角下识别地面目标，不是识别无人机本体 |
| `damoyolo_tinynasL25_S_uav.pt` | ModelScope DAMO-YOLO UAV checkpoint，不是 Ultralytics YOLO 格式 |

`flying_objects_yolov8m` 的无人机类别是 `0` 和 `4`，`-DroneOnly` 会只保留这两个类别。

## 环境安装

在 Windows PowerShell 里执行：

```powershell
cd .\drone_pt_detector
powershell -ExecutionPolicy Bypass -File .\scripts\setup_env.ps1
```

脚本会创建 `.venv` 并安装 Ultralytics、OpenCV、Hugging Face 下载工具。

## 模型下载和查看

下载默认 `.pt`：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\download_model.ps1
```

查看内置模型：

```powershell
.\.venv\Scripts\python.exe .\src\drone_pt_detector.py models
```

## 检测图片、视频和摄像头

摄像头实时预览：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\detect.ps1 -Source 0 -Show
```

检测视频：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\detect.ps1 -Source .\samples\test_video.mp4
```

检测图片：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\detect.ps1 -Source .\samples\test.jpg
```

只保留无人机类别：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\detect.ps1 -Source .\samples\test_video.mp4 -DroneOnly
```

输出目录：

```text
.\runs\detect\
```

## 开源测试数据集

默认下载 Hugging Face `kc34251/Drone-Detection`。它已经是 YOLO 图片和 `.txt` 标签格式，适合快速测试；该数据集数据卡/API 未声明明确 license，用于论文、产品或再发布前需要重新核对来源许可。

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\download_dataset.ps1
```

只下载前 50 张图片用于快速试跑：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\download_dataset.ps1 -Limit 50
```

下载后直接跑检测：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\detect.ps1 -Source .\data\open_datasets\kc34251_drone_detection\images\test -DroneOnly
```

用标注文件评估当前 `.pt`：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\validate.ps1 -Data .\data\open_datasets\kc34251_drone_detection\data.yaml -DroneOnly
```

## 自有 VOC 数据转换

如果使用本机的 Anti-UAV XML 数据：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\prepare_drone_voc_dataset.ps1 -Clean
```

转换后的 YOLO 数据集在：

```text
.\data\prepared\DroneTrainDataset_yolo
```

`DroneTrainDataset` 会划分为 `train` 和 `val`，`DroneTestDataset` 会作为 `test`；`DroneTestDataset` 中没有 XML 的 `VS_N*` 图片保留为空标签负样本。

## 训练

训练自定义数据集：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\train.ps1 -Data .\data\custom\drone\data.yaml -Epochs 100 -ImgSize 960 -Batch 8
```

用开源小数据集做连通性测试：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\train.ps1 -Data .\data\open_datasets\kc34251_drone_detection\data.yaml -Epochs 1 -ImgSize 640 -Batch 4
```

训练输出目录：

```text
.\runs\train\
```

## DAMO-YOLO UAV 测试

`models\damoyolo_tinynasL25_S_uav.pt` 的 checkpoint 键是 `state_dict`，不是 Ultralytics 的 `model` 键，不能用 `detect.ps1` 或 `validate.ps1` 直接跑。

专用测试脚本：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\test_damoyolo_uav.ps1
```

只跑检测可视化：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\test_damoyolo_uav.ps1 -DetectOnly -Source data\open_datasets\maciullo_snippet\images\test -Conf 0.25
```

只跑 YOLO 标签评估：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\test_damoyolo_uav.ps1 -EvalOnly -Data data\open_datasets\maciullo_snippet\data.yaml -Conf 0.25
```

当前测试结论：这个 checkpoint 能加载和推理，但对当前两个开源测试集泛化差，暂不适合作为 RK3576 部署主模型。

## 导出

导出 ONNX：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\export.ps1 -Format onnx -ImgSize 960
```

RKNN 导出通常建议在 x86 Linux 环境完成：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\export.ps1 -Format rknn -RknnTarget rk3576 -ImgSize 960
```

## 建议参数

- 小目标无人机建议 `ImgSize` 使用 `960` 或 `1280`。
- 误报多时先提高 `Conf`，例如 `-Conf 0.4`。
- 鸟类误检多时，不建议只训练无人机单类别，最好保留 `bird` 负样本或相近类别。
- 部署到 RK3576 前，建议用自己的摄像头场景微调 `n` 或 `s` 级别模型。
