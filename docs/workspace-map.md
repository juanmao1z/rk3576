# Workspace Map

RK3576 项目的目录地图和运行入口说明。该文档只描述自有工作区，不把第三方源码、数据集和构建产物纳入日常维护范围。

## 总体分层

```text
D:\Desktop\rk3576
  workspace\     RK3576/YOLO/ROS 工程代码和运行脚本
  datasets\      外部数据集、原始压缩包、下载结果
  tools\         Windows 侧维护/下载工具
```

## workspace 工程区

```text
D:\Desktop\rk3576\workspace
  camera_web_cpp_ws\         C++ 摄像头原始 MJPEG Web 服务
  camera_web_ws\             Python 摄像头 MJPEG Web 旧版/备用实现
  yolo_web_cpp_ws\           通用 YOLO C++ Canvas 工作区
  drone_yolo_web_cpp_ws\     无人机专用 YOLO C++ Canvas 工作区
  gimbal_dm_h3510_ws\        DM-H3510 云台控制工作区
  yolo_web_py_ws\            YOLO Python 服务端画框版
  yolo_web_py_canvas_ws\     YOLO Python Canvas 版
  drone_pt_detector\         PC 端无人机 PT 验证、训练和导出
  rknn_yolo11\               独立 RKNN YOLO11 示例
  rknn_model_zoo\            Rockchip Model Zoo 参考副本
  rknn_wheels\               板端 Python 依赖 wheel
  packages\                  外部安装包归档
  third_party\               第三方开源源码副本
  scripts\                   workspace 级统一入口脚本
  docs\                      workspace 说明文档
```

## 逻辑分层

低风险整理阶段不移动现有目录。逻辑分层、维护边界和新增文件放置规则见：

```text
D:\Desktop\rk3576\workspace\docs\workspace-organization.md
```

## 推荐入口

| 需求 | 推荐工作区 | 说明 |
| --- | --- | --- |
| 摄像头原始流 | `camera_web_cpp_ws` | C++ 版低开销 MJPEG 转发 |
| 通用 YOLO 实时检测 | `yolo_web_cpp_ws` | C++ + RKNN C API，浏览器 Canvas 叠框 |
| 无人机实时检测 | `drone_yolo_web_cpp_ws` | 专用 drone 模型和默认标签 |
| DM-H3510 云台控制 | `gimbal_dm_h3510_ws` | 云台通信、限位、归中、跟踪控制和后续视觉闭环 |
| Python 结果流对照 | `yolo_web_py_ws` | 服务端画框并重新编码 MJPEG |
| Python Canvas 对照 | `yolo_web_py_canvas_ws` | Python 推理，浏览器叠框 |
| PC 端模型验证/训练 | `drone_pt_detector` | 下载、检测、评估、训练、导出 |

## 端口约定

| 服务 | 端口 | 工作区 |
| --- | --- | --- |
| 摄像头原始流 | `8081` | `camera_web_cpp_ws` |
| YOLO Python 服务端画框 | `8090` | `yolo_web_py_ws` |
| YOLO Python Canvas | `8091` | `yolo_web_py_canvas_ws` |
| YOLO C++ Canvas | `8092` | `yolo_web_cpp_ws` / `drone_yolo_web_cpp_ws` |

同一时间只建议运行一个 YOLO 检测工作区，避免多个节点同时发布 `/yolo/detections`。

## 模型位置

| 模型 | 路径 |
| --- | --- |
| 通用 C++ Web RKNN | `yolo_web_cpp_ws\models\yolo11.rknn` |
| 无人机 C++ Web RKNN | `/home/lckfb/workspace/trained_yolo11n_best_rk3576_i8.rknn` |
| Python Web RKNN | `yolo_web_py_ws\models\yolo11.rknn` |
| Python Canvas RKNN | `yolo_web_py_canvas_ws\models\yolo11.rknn` |
| 独立 RKNN 示例 | `rknn_yolo11\rknn_yolo11\rknn_yolo11_cpp\model\yolo11.rknn` |
| 无人机 PT | `drone_pt_detector\models\flying_objects_yolov8m.pt` |
| DAMO-YOLO UAV PT | `drone_pt_detector\models\damoyolo_tinynasL25_S_uav.pt` |

## ROS 话题

| 话题 | 类型 | 发布者 |
| --- | --- | --- |
| `/camera/image_mjpeg` | `sensor_msgs/msg/CompressedImage` | `camera_web_cpp` |
| `/yolo/detections` | `vision_msgs/msg/Detection2DArray` | 当前运行的 YOLO 工作区 |
| `/gimbal/state` | 待定 | 后续 DM-H3510 云台节点 |
| `/gimbal/cmd` | 待定 | 后续 DM-H3510 云台节点或控制器 |

## 数据集位置

| 数据集 | 路径 | 说明 |
| --- | --- | --- |
| `DroneTrainDataset` / `DroneTestDataset` 原始 VOC | `..\datasets\drone-voc\raw` | 原始图片/XML |
| `DroneTrainDataset.zip` / `DroneTestDataset.zip` | `..\datasets\drone-voc\archives` | 原始压缩包归档 |
| `CenekAlbl/drone-tracking-datasets` full | `..\datasets\drone-tracking\full` | GitHub 数据集全量下载结果 |
| `CenekAlbl/drone-tracking-datasets` metadata | `..\datasets\drone-tracking\metadata` | 轻量元数据/预览图副本 |
| `kc34251/Drone-Detection` | `drone_pt_detector\data\open_datasets\kc34251_drone_detection` | YOLO 格式公开测试集，license 未声明 |
| `Maciullo/DroneDetectionDataset` snippet | `drone_pt_detector\data\open_datasets\maciullo_snippet` | 100 张 test snippet，XML 已转 YOLO |

## 第三方源码

| 项目 | 路径 | 说明 |
| --- | --- | --- |
| DAMO-YOLO | `third_party\DAMO-YOLO-master` | 上游 DAMO-YOLO 源码副本，用于测试 ModelScope UAV checkpoint |
| RKNN Model Zoo | `rknn_model_zoo` | Rockchip 上游参考副本，不作为本轮自有代码维护范围 |

## 不建议移动的目录

- `camera_web_cpp_ws`
- `yolo_web_cpp_ws`
- `drone_yolo_web_cpp_ws`
- `gimbal_dm_h3510_ws`
- `yolo_web_py_ws`
- `yolo_web_py_canvas_ws`
- `drone_pt_detector`

如果后续必须移动，需要同步修改 Windows 脚本、板端 shell 脚本、README 和 ROS2 launch 默认路径。
