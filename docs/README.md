# Workspace Docs

RK3576 workspace 的总说明文档目录。这里不放运行代码，只记录目录地图、生成物边界和维护约定。

## 文档列表

| 文件 | 说明 |
| --- | --- |
| `workspace-map.md` | 工作区目录地图、推荐入口、端口和模型位置 |
| `workspace-organization.md` | 低风险逻辑分层、维护边界和新增文件放置规则 |
| `artifacts.md` | 大文件、生成物、核心资产和低风险清理建议 |
| `superpowers/specs/` | 使用 superpowers 形成的设计规格 |
| `superpowers/plans/` | 使用 superpowers 形成的执行计划 |

## 使用方式

- 找运行入口时先看 `workspace-map.md`。
- 判断目录职责和新增文件位置时看 `workspace-organization.md`。
- 清理文件前先看 `artifacts.md`。
- 具体项目的构建和启动命令以各工作区 README 为准。
