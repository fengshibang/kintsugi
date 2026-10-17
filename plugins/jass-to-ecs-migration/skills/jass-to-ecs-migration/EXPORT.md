# 导出说明 — jass-to-ecs-migration

把本目录复制到目标项目即完成导出。目标项目需使用同一套 **ac/ecs 框架**（`lib/ecs` + `ac` 抽象层）；框架不同则需重写 `data/` 下两个 yaml 的 ECS 侧映射。

## 复制清单

```
<目标项目>/.claude/skills/jass-to-ecs-migration/
├── SKILL.md            # 主文档
├── EXPORT.md           # 本文件（可留作安装指引，也可删）
├── data/
│   ├── patterns.yaml   # JASS 模式 → ECS 映射（10 模式）
│   └── api_mapping.yaml# JASS API → Lua/ac API 映射（160+）
├── scripts/
│   ├── analyzer.py     # 全局分析 + PRD + 进度标记（无第三方依赖，Python 3 标准库）
│   └── extract_trigger.py # 单触发器提取（无第三方依赖）
└── templates/
    ├── migration_prd.md
    └── trigger_analysis.md
```

**不随包导出**（本项目专属）：
- 一次性 `comment_*.py` 注释脚本 → 已归档到本项目 `docs/migrations/scripts/`
- `jass-migrate-trigger` workflow → 在本项目 `.claude/workflows/jass-migrate-trigger.js`，若目标项目也要 workflow 编码+审查，一并复制该文件

## 安装步骤

1. 复制上述目录到 `<目标项目>/.claude/skills/jass-to-ecs-migration/`
2. （可选）复制 `.claude/workflows/jass-migrate-trigger.js` 到目标项目同位置
3. 编辑 SKILL.md 的「**项目配置**」表，替换为目标项目的实际路径：
   - JASS 源文件（war3map.j 位置）
   - Lua 代码目录（`--lua-dir`）
   - 迁移文档目录与状态文件
   - pjass 可执行文件路径
4. 验证：
   ```bash
   python3 .claude/skills/jass-to-ecs-migration/scripts/analyzer.py <war3map.j路径> --status-list
   python3 .claude/skills/jass-to-ecs-migration/scripts/extract_trigger.py <war3map.j路径> <某触发器Actions函数名>
   ```
   两条命令能正常输出即安装成功。

## 环境要求

- Python 3（脚本仅标准库，无 pip 依赖）
- pjass（可选，注释 war3map.j 后做语法检测；随 `common.j`/`blizzard.j` 一起传入）
- 目标项目具备 ac/ecs 框架（`ac.timer`、ECS 事件类、组件/系统结构）
