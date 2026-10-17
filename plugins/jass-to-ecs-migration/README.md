# jass-to-ecs-migration

把魔兽争霸 3 地图的 JASS 触发器（`war3map.j`）迁移到 **ac/ecs Lua 框架**（ECS 架构）的分析规划 skill。**完全转换到 ECS，不做中间适配层**。

本插件承载一个 skill：`skills/jass-to-ecs-migration/`。

## 能力

| 能力 | 入口 |
|------|------|
| 全局分析 + 分批迁移 PRD（ECS 就绪度） | `skills/jass-to-ecs-migration/scripts/analyzer.py <war3map.j> -o <PRD> -s ecs-ready --lua-dir <lua-dir>` |
| 单触发器分析（API 依赖 / ECS 映射） | `scripts/extract_trigger.py <war3map.j> <触发器名> -o <输出>` |
| 标记已迁移 / 查看进度 | `analyzer.py --status-file <文件> --mark <名>` / `--status-list` |

脚本仅用 Python 3 标准库，无第三方依赖。

## 数据文件

- `data/api_mapping.yaml` — JASS API → Lua/ac API 映射（160+）
- `data/patterns.yaml` — JASS 模式 → ECS 模式映射（10 种）

> 两个 yaml 的 ECS 侧（事件类/组件命名）绑定 ac/ecs 框架。目标项目框架不同需按自身事件类/组件名重写映射。

## 使用

1. 在目标项目安装此插件（`/plugin install` 或 marketplace 安装）。
2. 按 `skills/jass-to-ecs-migration/SKILL.md`「项目配置」表替换目标项目路径（war3map.j、lua-dir、迁移文档目录、pjass）。
3. 触发 `/jass-to-ecs-migration` skill。

> **workflow 说明**：skill 引用 `jass-migrate-trigger` workflow 做编码+审查编排；当前 zip 未包含该 workflow，无 workflow 环境时 skill 自动降级为手动模式。如需 workflow，将 `jass-migrate-trigger.js` 一并放入目标项目 `.claude/workflows/`。

## 验证

```bash
python skills/jass-to-ecs-migration/scripts/analyzer.py <war3map.j路径> --status-list
python skills/jass-to-ecs-migration/scripts/extract_trigger.py <war3map.j路径> <某触发器Actions函数名>
```