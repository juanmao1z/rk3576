# Workspace Low-Risk Organization Design

## 背景

用户要求使用 superpowers 重新调整 `D:\Desktop\rk3576\workspace` 文件结构，并选择低风险整理。当前 workspace 已经包含相机、YOLO、无人机检测、PC 训练、RKNN 示例、依赖归档、第三方源码和 DM-H3510 云台工作区。

## 目标

在不移动、不重命名现有可运行目录的前提下，让 workspace 的结构更容易理解和维护。

## 约束

- `camera_web_cpp_ws`、`yolo_web_cpp_ws`、`drone_yolo_web_cpp_ws` 等目录已被 Windows 脚本、开发板 shell 脚本、README 和 ROS2 launch 默认路径引用。
- 开发板侧路径存在 `/home/lckfb/workspace/...` 硬编码。
- `8081`、`8090`、`8091`、`8092` 和 `/yolo/detections` 是现有运行约定。
- 该目录不是 git 仓库，不能依赖 commit 作为验证步骤。

## 推荐设计

采用逻辑分层而不是物理移动：

- 保留根目录下现有可运行工作区。
- 新增 `docs/workspace-organization.md`，解释逻辑层级和维护边界。
- 更新 `docs/README.md`，把目录地图、工件边界和组织规则串起来。
- 更新根 `README.md` 和 `docs/workspace-map.md`，明确低风险整理结论和不可移动目录。

## 成功标准

- 现有可运行目录名保持不变。
- 文档中能清楚区分摄像头、通用 YOLO、无人机 YOLO、云台、PC 训练、依赖归档和第三方源码。
- 未来新增云台控制、联动脚本和模型资产时有明确落点。
- 能通过文件搜索确认新文档入口存在，目录没有被移动。

## 不做事项

- 不物理移动核心工作区。
- 不修改板端路径。
- 不修改启动脚本行为。
- 不合并通用 YOLO 和无人机 YOLO。
- 不把 DM-H3510 云台逻辑混入相机或 YOLO 工作区。
