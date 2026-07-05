# RK3576 Workspace

这是 RK3576 视觉、摄像头、YOLO/RKNN、ROS2、无人机检测和 DM-H3510 云台工程区。本文档所在目录是 RK3576 项目目录。

这里保留可维护代码、启动脚本、README、少量必要依赖和板端部署说明。数据集、临时训练输出、第三方上游源码、生成文档和模型文件不作为日常源码整理对象。

## 项目定位

- RK3576 项目目录是当前视觉项目的主入口，不建议再拆成新的顶层目录。
- 在 `ROS_CAR_PROJECT` 中，`feature/RK3576` 分支把本项目放在仓库根目录；`main` 分支把本项目放在 `robot_ws/src/rk3576`。
- 下面的 Windows 命令默认从 RK3576 项目目录执行。
- 各 `*_ws` 目录已经被 Windows 一键脚本、开发板启动脚本和 README 引用，目录名本身是运行约定。
- 通用 YOLO 和无人机 YOLO 分开维护：通用版本保留 COCO 标签和通用模型，无人机版本只保存无人机识别链路。
- DM-H3510 ROS2 驱动放在 `dm_h3510_ros_ws`；云台工程资料、PC 烟测和配置记录放在 `gimbal_dm_h3510_ws`。
- 云台和视觉工作区通过 ROS2 话题或上层脚本联动，不混入相机或 YOLO 代码。
- C++ Canvas 版是当前 RK3576 实时检测的主推运行形态；Python 版本保留为对照、调试和兼容方案。

## 目录结构

当前采用低风险整理：物理目录保持原位，逻辑分层写入 `docs\workspace-organization.md`。这样既能保持运行路径稳定，又能让相机、YOLO、云台、训练、依赖归档和第三方源码的职责清楚。

| 路径 | 用途 | 维护方式 |
| --- | --- | --- |
| `camera_web_cpp_ws` | RK3576 板端 ROS2 C++ 摄像头 MJPEG Web 服务 | 主用摄像头工作区，可维护 |
| `camera_web_ws` | 早期/备用 ROS2 Python 摄像头 Web 服务 | 保留对照，少改 |
| `yolo_web_cpp_ws` | 通用 YOLO11 RKNN C++ Canvas Web/ROS2 工作区 | 主用通用 YOLO，可维护 |
| `drone_yolo_web_cpp_ws` | 无人机 YOLO11 RKNN C++ Canvas Web/ROS2 专用工作区 | 主用无人机识别，可维护 |
| `dm_h3510_ros_ws` | DM-H3510 ROS2 Python/C++ 驱动、构建和板端运行脚本 | 云台 ROS2 驱动工作区，可维护 |
| `gimbal_dm_h3510_ws` | DM-H3510 工程资料、PC 烟测、配置和协议记录 | 云台工程资料工作区，可维护 |
| `yolo_web_py_ws` | Python RKNN 推理并在服务端画框的 Web/ROS2 工作区 | 保留非 Canvas 版本 |
| `yolo_web_py_canvas_ws` | Python RKNN 推理加浏览器 Canvas 叠框的 Web/ROS2 工作区 | 保留 Canvas 对照版本 |
| `drone_pt_detector` | Windows PC 端无人机 `.pt` 数据集、训练、验证和导出工具 | PC 训练/测试入口 |
| `rknn_yolo11` | RKNN YOLO11 独立示例和板端说明 | 示例和验证入口 |
| `scripts` | 当前 workspace 的统一 Windows 入口脚本 | 统一入口优先放这里 |
| `docs` | workspace 目录地图、工件说明、维护约定和生成文档输出 | 文档入口 |
| `tmp_gs_usb_rk3576_build` | `gs_usb` 临时构建试验区 | 临时构建区，不作为源码入口 |
| `packages` | 外部安装包、deb、wheel 等归档 | 只归档，不混入源码 |
| `rknn_wheels` | RK3576/aarch64 板端 Python wheel 包 | 依赖归档 |
| `rknn_model_zoo` | Rockchip RKNN Model Zoo 上游参考副本 | 上游参考，避免日常改动 |
| `third_party` | 第三方开源源码副本 | 第三方源码，避免日常改动 |

## 推荐入口

### 摄像头 C++ 原始流

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\start_camera_cpp.ps1
```

打开：

```text
http://127.0.0.1:8081/
```

关闭：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\stop_camera_cpp.ps1
```

### 双路摄像头 C++ 原始流

默认通过 SSH 启动开发板上的 front/left 两路 USB 摄像头：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\start_multi_camera_cpp.ps1
```

打开：

```text
http://192.168.137.217:8081/
http://192.168.137.217:8082/
```

关闭：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\stop_multi_camera_cpp.ps1
```

当前双路实现使用独立设备、独立 ROS2 话题和独立端口。不要让两路摄像头共用 `/camera/image_mjpeg` 或同一个 Web 端口。

### 通用 YOLO C++ Canvas

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\start_yolo_cpp.ps1
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
powershell -ExecutionPolicy Bypass -File .\drone_yolo_web_cpp_ws\scripts\windows\start_drone_yolo_cpp_all.ps1
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
powershell -ExecutionPolicy Bypass -File .\scripts\windows\start_yolo_py.ps1
```

打开：

```text
http://127.0.0.1:8090/
```

### YOLO Python Canvas

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\start_yolo_py_canvas.ps1
```

打开：

```text
http://127.0.0.1:8091/
```

### PC 端无人机 `.pt` 测试

```powershell
powershell -ExecutionPolicy Bypass -File .\drone_pt_detector\scripts\detect.ps1 -Source 0 -Show -DroneOnly
```

### DM-H3510 ROS2 驱动

工作区：

```text
.\dm_h3510_ros_ws
```

该目录保存 Python/C++ ROS2 节点、板端构建脚本和部署脚本。它发布 `/gimbal/state`，订阅 `/gimbal/position_cmd` 和 `/gimbal/target_joint_state`。

Windows 部署和板端构建：

```powershell
cd .\dm_h3510_ros_ws
.\scripts\windows\deploy_to_board.ps1
adb shell "bash /home/lckfb/workspace/dm_h3510_ros_ws/scripts/board/build_cpp_ros.sh"
```

### DM-H3510 工程资料和 PC 烟测

工作区：

```text
.\gimbal_dm_h3510_ws
```

该目录保存 PC 侧 USB2CANFD 烟测、工程记录、配置样例和协议资料。它不是 ROS2 主工作区。

PC 端 USB2CANFD 烟测入口：

```powershell
cd .\gimbal_dm_h3510_ws
.\scripts\windows\list_usb2canfd.ps1
.\scripts\windows\run_dm_h3510_control.ps1 -Velocity 1 -DurationMs 2000
```

## 端口和 ROS 话题

| 服务 | 默认端口 | 说明 |
| --- | --- | --- |
| C++ 摄像头 MJPEG | `8081` | 摄像头原始图像流 |
| C++ 双路摄像头 left | `8082` | 第二路摄像头原始图像流 |
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

DM-H3510 ROS2 驱动发布/订阅云台相关接口。视觉侧继续只负责 `/yolo/detections`。

摄像头分辨率约定：

- 默认使用 `640x480`，适合低延迟调试。
- `1280x720` 在当前硬件上按 `30 FPS` 请求；不显式设置 FPS 时不要改成低帧率默认值。
- 浏览器页面显示的 FPS 是处理/推理链路统计，不等同于摄像头硬件采集请求 FPS。

## 维护边界

- 不移动或重命名 `camera_web_cpp_ws`、`yolo_web_cpp_ws`、`drone_yolo_web_cpp_ws` 等工作区目录，除非同步改完所有 Windows 和板端脚本。
- 不把通用 YOLO 和无人机 YOLO 合并；两者模型、标签和 README 要保持独立。
- 不把 DM-H3510 ROS2 驱动混入相机或 YOLO 工作区；联动逻辑通过上层脚本或 ROS2 话题组合。
- 不把 `dm_h3510_ros_ws` 和 `gimbal_dm_h3510_ws` 混成一个入口；前者负责 ROS2 驱动，后者负责工程资料和 PC 烟测。
- 不把第三方源码、Model Zoo、数据集、训练输出、临时文件混入主工作区入口。
- 不在 `rknn_model_zoo` 和 `third_party` 里做项目定制逻辑；需要定制时放到对应 `*_ws` 或 `rknn_yolo11`。
- 新增 Windows 一键脚本优先放到 `scripts\windows`，专用项目脚本放到对应工作区的 `scripts\windows`。
- 新增板端脚本优先放到对应工作区的 `scripts\board`，并在 README 中写清楚板端路径。
- 大模型、数据集和训练输出优先放在各项目自己的 `models`、`data`、`runs` 目录，避免散放在 `workspace` 根目录。

## 常用文档

```text
.\README.md
.\docs\README.md
.\docs\workspace-map.md
.\docs\workspace-organization.md
.\docs\artifacts.md
.\camera_web_cpp_ws\README.md
.\yolo_web_cpp_ws\README.md
.\drone_yolo_web_cpp_ws\README.md
.\drone_pt_detector\README.md
.\dm_h3510_ros_ws\README.md
.\gimbal_dm_h3510_ws\README.md
```

## 整理结论

`workspace` 目录不需要做大规模物理重排。当前更合适的整理方式是保留已被脚本引用的视觉工作区目录，同时把 DM-H3510 的 ROS2 驱动和 PC 工程资料分清楚。入口说明、启动方式、端口、话题和维护边界集中到本 README，避免移动目录导致脚本和板端部署路径失效。
