# Workspace Low-Risk Organization 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 在不移动现有目录的前提下整理 `workspace` 的结构说明、运行入口和维护边界。

**架构：** 用文档表达逻辑分层，保留当前物理目录作为运行约定。根 README 做快速入口，`docs/workspace-map.md` 做目录地图，`docs/workspace-organization.md` 做维护规则。

**技术栈：** Markdown 文档、PowerShell 文件验证、ripgrep 搜索验证。

---

### 任务 1：新增逻辑分层文档

**文件：**
- 创建：`docs/workspace-organization.md`

- [x] **步骤 1：写入逻辑分层**

记录摄像头、YOLO、无人机 YOLO、云台、PC 训练、RKNN 示例、统一脚本、依赖归档和第三方源码的职责。

- [x] **步骤 2：写入不移动目录清单**

列出低风险整理阶段保持原地的目录。

- [x] **步骤 3：写入新增文件放置规则**

明确脚本、云台配置、模型、数据集、第三方源码的推荐位置。

### 任务 2：更新文档入口

**文件：**
- 修改：`docs/README.md`
- 修改：`docs/workspace-map.md`
- 修改：`README.md`

- [x] **步骤 1：在 docs README 增加 organization 文档入口**

- [x] **步骤 2：在 workspace-map 增加逻辑分层文档引用**

- [x] **步骤 3：在根 README 增加低风险整理说明**

### 任务 3：验证

**文件：**
- 读取：`workspace` 根目录
- 搜索：`docs`, `README.md`

- [x] **步骤 1：确认核心目录仍在原位**

运行：`Get-ChildItem D:\Desktop\rk3576\workspace -Directory`

- [x] **步骤 2：确认新文档引用存在**

运行：`rg -n "workspace-organization|低风险|逻辑分层" D:\Desktop\rk3576\workspace\README.md D:\Desktop\rk3576\workspace\docs`

- [x] **步骤 3：确认未依赖 git**

运行：`git -C D:\Desktop\rk3576 status --short`
预期：不是 git 仓库，最终报告说明无法用 git diff 验证。
