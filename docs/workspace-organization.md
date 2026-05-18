# Workspace Organization

RK3576 workspace 的低风险整理方案。该方案只调整说明、索引和维护边界，不移动、不重命名已被脚本和开发板路径引用的工作区目录。

## 整理原则

- 保留所有可运行工作区的现有目录名。
- 用逻辑分层解释目录职责，而不是用物理移动表达分层。
- 运行入口统一从 `README.md`、`docs/workspace-map.md` 和 `scripts/README.md` 查找。
- 专用逻辑留在对应工作区，聚合脚本只做转发、ADB 映射和健康检查。
- 第三方源码、Model Zoo、wheel、deb、数据集和训练输出不混入主运行入口。

## 逻辑分层

| 层级 | 目录 | 说明 |
| --- | --- | --- |
| 摄像头采集 | `camera_web_cpp_ws` | 当前主用 C++ 摄像头 MJPEG 服务 |
| 摄像头对照 | `camera_web_ws` | 早期 Python 摄像头服务，保留对照 |
| 实时检测主线 | `yolo_web_cpp_ws` | 通用 YOLO11 RKNN C++ Canvas 运行链路 |
| 无人机检测主线 | `drone_yolo_web_cpp_ws` | 无人机专用 YOLO11 RKNN C++ Canvas 运行链路 |
| 云台控制 | `gimbal_dm_h3510_ws` | DM-H3510 云台通信、配置、控制和后续跟踪闭环 |
| Python 对照 | `yolo_web_py_ws`, `yolo_web_py_canvas_ws` | Python 推理和 Canvas 对照实现 |
| PC 训练验证 | `drone_pt_detector` | Windows PC 端无人机数据集、训练、检测和导出 |
| RKNN 示例 | `rknn_yolo11` | 独立 RKNN YOLO11 示例和板端说明 |
| 统一入口 | `scripts` | workspace 级 Windows 转发入口 |
| 说明文档 | `docs` | 目录地图、工件边界、逻辑分层和维护规则 |
| 依赖归档 | `packages`, `rknn_wheels` | 板端安装包、wheel、deb 等归档 |
| 上游参考 | `rknn_model_zoo`, `third_party` | 上游源码副本，不放项目定制逻辑 |

## 不移动目录

这些目录包含硬编码路径、板端路径、ADB 启动脚本或 ROS2 默认配置，低风险整理阶段保持原地：

- `camera_web_cpp_ws`
- `yolo_web_cpp_ws`
- `drone_yolo_web_cpp_ws`
- `gimbal_dm_h3510_ws`
- `yolo_web_py_ws`
- `yolo_web_py_canvas_ws`
- `drone_pt_detector`

## 运行边界

| 边界 | 保持方式 |
| --- | --- |
| 摄像头原始流 | `camera_web_cpp_ws` 独立维护，端口 `8081` |
| 通用 YOLO | `yolo_web_cpp_ws` 独立维护，端口 `8092` |
| 无人机 YOLO | `drone_yolo_web_cpp_ws` 独立维护，端口 `8092`，同一时间只运行一个 YOLO 发布者 |
| 云台控制 | `gimbal_dm_h3510_ws` 独立维护，后续通过 ROS2 或聚合脚本联动 |
| 统一检测话题 | YOLO 系列继续发布 `/yolo/detections` |
| 未来云台话题 | 云台工作区预留 `/gimbal/state` 和 `/gimbal/cmd` |

## 新增或修改文件放置规则

| 文件类型 | 推荐位置 |
| --- | --- |
| workspace 级 Windows 启停脚本 | `scripts/windows` |
| 某个工作区专用 Windows 脚本 | `<workspace>/scripts/windows` |
| 某个工作区板端脚本 | `<workspace>/scripts/board` |
| DM-H3510 协议、接线、标定记录 | `gimbal_dm_h3510_ws/docs` |
| DM-H3510 参数 | `gimbal_dm_h3510_ws/config` |
| 模型、训练输出、数据集 | 对应项目自己的 `models`、`runs`、`data`，或上级 `datasets` |
| 第三方源码 | `third_party` |
| 上游 RKNN 参考 | `rknn_model_zoo` |

## 后续升级路径

如果未来确实需要物理重排，应先完成以下事项：

1. 列出所有 Windows PowerShell 脚本中的本机路径。
2. 列出所有板端 shell 脚本中的 `/home/lckfb/workspace/...` 路径。
3. 列出 ROS2 launch、C++ 默认参数和 README 中的模型路径。
4. 逐个工作区迁移并验证启动、健康检查、ROS2 话题和 ADB 映射。
5. 每次只迁移一个工作区，避免同时破坏相机、YOLO 和云台链路。
