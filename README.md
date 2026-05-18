# RK3576 Workspace

这是 RK3576 视觉、摄像头、YOLO/RKNN、ROS2 和无人机检测工程区。目录里保留可维护代码、启动脚本、README、少量必要依赖和板端部署说明；数据集、临时训练输出、第三方上游源码和模型文件不作为日常整理对象。

## 项目定位

- `workspace` 是当前 RK3576 视觉项目的主入口，不建议再拆成新的顶层目录。
- 各 `*_ws` 目录已经被 Windows 一键脚本、开发板启动脚本和 README 引用，目录名本身是运行约定。
- 通用 YOLO 和无人机 YOLO 分开维护：通用版本保留 COCO 标签和通用模型，无人机版本只保存无人机识别链路。
- DM-H3510 云台控制单独放在 `gimbal_dm_h3510_ws`；它和视觉工作区联动，但不混入相机或 YOLO 代码。
- C++ Canvas 版是当前 RK3576 实时检测的主推运行形态；Python 版本保留为对照、调试和兼容方案。

## 目录结构

当前采用低风险整理：物理目录保持原位，逻辑分层写入 `docs\workspace-organization.md`。这样既能保持运行路径稳定，又能让相机、YOLO、云台、训练、依赖归档和第三方源码的职责清楚。

| 路径 | 用途 | 维护方式 |
| --- | --- | --- |
| `camera_web_cpp_ws` | RK3576 板端 ROS2 C++ 摄像头 MJPEG Web 服务 | 主用摄像头工作区，可维护 |
| `camera_web_ws` | 早期/备用 ROS2 Python 摄像头 Web 服务 | 保留对照，少改 |
| `yolo_web_cpp_ws` | 通用 YOLO11 RKNN C++ Canvas Web/ROS2 工作区 | 主用通用 YOLO，可维护 |
| `drone_yolo_web_cpp_ws` | 无人机 YOLO11 RKNN C++ Canvas Web/ROS2 专用工作区 | 主用无人机识别，可维护 |
| `gimbal_dm_h3510_ws` | DM-H3510 云台控制、配置、脚本和后续视觉跟踪闭环 | 新增云台工作区，可维护 |
| `yolo_web_py_ws` | Python RKNN 推理并在服务端画框的 Web/ROS2 工作区 | 保留非 Canvas 版本 |
| `yolo_web_py_canvas_ws` | Python RKNN 推理加浏览器 Canvas 叠框的 Web/ROS2 工作区 | 保留 Canvas 对照版本 |
| `drone_pt_detector` | Windows PC 端无人机 `.pt` 数据集、训练、验证和导出工具 | PC 训练/测试入口 |
| `rknn_yolo11` | RKNN YOLO11 独立示例和板端说明 | 示例和验证入口 |
| `scripts` | 当前 workspace 的统一 Windows 入口脚本 | 统一入口优先放这里 |
| `docs` | workspace 目录地图、工件说明和维护约定 | 文档入口 |
| `packages` | 外部安装包、deb、wheel 等归档 | 只归档，不混入源码 |
| `rknn_wheels` | RK3576/aarch64 板端 Python wheel 包 | 依赖归档 |
| `rknn_model_zoo` | Rockchip RKNN Model Zoo 上游参考副本 | 上游参考，避免日常改动 |
| `third_party` | 第三方开源源码副本 | 第三方源码，避免日常改动 |

## 推荐入口

### 摄像头 C++ 原始流

```powershell
powershell -ExecutionPolicy Bypass -File D:\Desktop\rk3576\workspace\scripts\windows\start_camera_cpp.ps1
```

打开：

```text
http://127.0.0.1:8081/
```

关闭：

```powershell
powershell -ExecutionPolicy Bypass -File D:\Desktop\rk3576\workspace\scripts\windows\stop_camera_cpp.ps1
```

### 通用 YOLO C++ Canvas

```powershell
powershell -ExecutionPolicy Bypass -File D:\Desktop\rk3576\workspace\scripts\windows\start_yolo_cpp.ps1
```

打开：

```text
http://127.0.0.1:8092/
```

板端默认模型：

```text
/home/lckfb/workspace/yolo/yolo_web_cpp_ws/models/yolo11.rknn
```

### 无人机 YOLO C++ Canvas

```powershell
powershell -ExecutionPolicy Bypass -File D:\Desktop\rk3576\workspace\drone_yolo_web_cpp_ws\scripts\windows\start_drone_yolo_cpp_all.ps1
```

打开：

```text
http://127.0.0.1:8092/
```

板端默认模型：

```text
/home/lckfb/workspace/trained_yolo11n_best_rk3576_i8.rknn
```

### YOLO Python 服务端画框

```powershell
powershell -ExecutionPolicy Bypass -File D:\Desktop\rk3576\workspace\scripts\windows\start_yolo_py.ps1
```

打开：

```text
http://127.0.0.1:8090/
```

### YOLO Python Canvas

```powershell
powershell -ExecutionPolicy Bypass -File D:\Desktop\rk3576\workspace\scripts\windows\start_yolo_py_canvas.ps1
```

打开：

```text
http://127.0.0.1:8091/
```

### PC 端无人机 `.pt` 测试

```powershell
powershell -ExecutionPolicy Bypass -File D:\Desktop\rk3576\workspace\drone_pt_detector\scripts\detect.ps1 -Source 0 -Show -DroneOnly
```

### DM-H3510 云台控制

工作区：

```text
D:\Desktop\rk3576\workspace\gimbal_dm_h3510_ws
```

当前只建立结构和维护边界。拿到 DM-H3510 通信方式、设备节点和协议后，在该工作区补充 `config`、`scripts\board`、`scripts\windows` 和 `src`。

## 端口和 ROS 话题

| 服务 | 默认端口 | 说明 |
| --- | --- | --- |
| C++ 摄像头 MJPEG | `8081` | 摄像头原始图像流 |
| YOLO Python 服务端画框 | `8090` | 后端输出已画框 MJPEG |
| YOLO Python Canvas | `8091` | 浏览器 Canvas 叠加检测框 |
| YOLO C++ / Drone C++ Canvas | `8092` | 浏览器 Canvas 叠加检测框 |

统一 ROS2 推理结果话题：

```text
/yolo/detections
```

消息类型：

```text
vision_msgs/msg/Detection2DArray
```

DM-H3510 云台后续建议单独发布/订阅云台相关接口，例如 `/gimbal/state` 和 `/gimbal/cmd`；视觉侧继续只负责 `/yolo/detections`。

摄像头分辨率约定：

- 默认使用 `640x480`，适合低延迟调试。
- `1280x720` 在当前硬件上按 `30 FPS` 请求；不显式设置 FPS 时不要改成低帧率默认值。
- 浏览器页面显示的 FPS 是处理/推理链路统计，不等同于摄像头硬件采集请求 FPS。

## 维护边界

- 不移动或重命名 `camera_web_cpp_ws`、`yolo_web_cpp_ws`、`drone_yolo_web_cpp_ws` 等工作区目录，除非同步改完所有 Windows 和板端脚本。
- 不把通用 YOLO 和无人机 YOLO 合并；两者模型、标签和 README 要保持独立。
- 不把 DM-H3510 云台驱动混入相机或 YOLO 工作区；联动逻辑通过上层脚本或 ROS2 话题组合。
- 不把第三方源码、Model Zoo、数据集、训练输出、临时文件混入主工作区入口。
- 不在 `rknn_model_zoo` 和 `third_party` 里做项目定制逻辑；需要定制时放到对应 `*_ws` 或 `rknn_yolo11`。
- 新增 Windows 一键脚本优先放到 `scripts\windows`，专用项目脚本放到对应工作区的 `scripts\windows`。
- 新增板端脚本优先放到对应工作区的 `scripts\board`，并在 README 中写清楚板端路径。
- 大模型、数据集和训练输出优先放在各项目自己的 `models`、`data`、`runs` 目录，避免散放在 `workspace` 根目录。

## 常用文档

```text
D:\Desktop\rk3576\README.md
D:\Desktop\rk3576\workspace\docs\README.md
D:\Desktop\rk3576\workspace\docs\workspace-map.md
D:\Desktop\rk3576\workspace\docs\workspace-organization.md
D:\Desktop\rk3576\workspace\docs\artifacts.md
D:\Desktop\rk3576\workspace\camera_web_cpp_ws\README.md
D:\Desktop\rk3576\workspace\yolo_web_cpp_ws\README.md
D:\Desktop\rk3576\workspace\drone_yolo_web_cpp_ws\README.md
D:\Desktop\rk3576\workspace\drone_pt_detector\README.md
D:\Desktop\rk3576\workspace\gimbal_dm_h3510_ws\README.md
```

## 整理结论

`workspace` 目录不需要做大规模物理重排。当前更合适的整理方式是保留已被脚本引用的视觉工作区目录，同时为 DM-H3510 新增独立 `gimbal_dm_h3510_ws`，把入口说明、启动方式、端口、话题和维护边界集中到本 README，避免移动目录导致脚本和板端部署路径失效。
