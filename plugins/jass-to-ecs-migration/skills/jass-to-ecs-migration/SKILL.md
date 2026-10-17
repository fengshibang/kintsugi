---
name: jass-to-ecs-migration
version: 2.1.0
description: Use when migrating JASS triggers to ECS Lua architecture — analyzing war3map.j, generating migration PRDs with ECS readiness, extracting individual trigger analysis, tracking migration progress. Orchestration via jass-migrate-trigger workflow.
---

# JASS → ECS 迁移分析 Skill

**定位**: 分析规划 skill。输出分析结果和 PRD，代码实现交由 `jass-migrate-trigger` Workflow 编排（无 workflow 环境走手动模式）。

**核心原则**: 完全转换到 ECS 架构，不做中间适配层。每个 trigger 的迁移路径：分析 → 用 ECS 组件/系统实现 → 验证 → `DisableTrigger` 原 trigger。

## 项目配置

导出到新项目时，**只需修改下表中的路径**，其余内容通用：

| 配置项 | 本项目值 | 说明 |
|--------|---------|------|
| JASS 源文件 | `map/war3map.j` | 待分析的 war3map.j 路径 |
| Lua 代码目录 | `map/script` | `--lua-dir` 参数，用于 ECS 就绪度分析 |
| 迁移文档目录 | `docs/migrations/` | PRD 与单触发器分析输出位置 |
| 状态文件 | `docs/migrations/migrate_status.json` | `--status-file` 参数 |
| pjass 可执行文件 | `<工具链>/jasshelper/pjass.exe` | 语法检测用，随 `common.j` `blizzard.j` 一起传入 |
| 实现编排 | `jass-migrate-trigger` workflow | 可选；无 workflow 环境用手动模式 |

下文命令示例均使用本项目值，替换为目标的实际路径即可。

---

## 游戏框架目录结构

skill 假定目标项目为上图所示「地图编译源码 + 物编 + 品牌资源 + 完整工具链」布局。项目根 `workspaceRoot/` 的既定结构如下（仅「JASS 源 / 迁移文档目录 / pjass」三项按目标调整，其余为框架既定）：

```
workspaceRoot/
├── map/                              # 地图编译源码
│   ├── war3map.j                     # JASS 源（迁移分析对象）
│   ├── plugin_main.lua               # Lua 引导入口
│   ├── callback                      # YDWE 触发器混淆 JASS（initializePlugin 经 StartCampaignAI 加载）
│   ├── (key)                         # YDWE key（触发器机制）
│   └── script/                       # Lua 框架根
│       ├── lib/                      # ac/ecs/ui/util 框架层
│       └── src/
│           ├── systems/*.lua         # ECS 系统落点（Death/Attack/Item…）
│           ├── components/*.lua      # ECS 组件落点
│           ├── 技能/<skill>.lua      # 技能触发器落点
│           ├── Buffs/ 物品/ 任务/ 副本/ 界面/ …   # 业务模块落点
│           └── …
├── table/                            # 物编数据（源码制，w2l 编译读）
│   ├── ability.ini                   #   技能物编 → 技能 ID 真值源
│   └── buff.ini  item.ini  unit.ini  upgrade.ini  misc.ini  w3i.ini …
├── resource/                         # 品牌/UI 资源
│   ├── wenhao_plugin.tga             #   brand 插件 dll 素材（改名注入加载界面）
│   └── background.tga  war3mapMap.blp  core/  frameworkBase/ …/
├── docs/
│   └── migrations/                   # 迁移 PRD/单触发器分析/状态文件输出
├── tools/                            # 完整工具链
│   ├── w3x2lni/                      # 编译打包（lni→w3x）
│   │   ├── w2l.exe                   #   w2l 主程序
│   │   ├── bin/  data/  template/  config.ini
│   │   └── script/                   #   w2l 编译核心脚本（backend/ core/ ffi/ …）
│   ├── rsa/                          # 地图签名
│   ├── filewatch.dll                 # 语法检查监听
│   ├── 运行.lua 语法检查.lua 配置.lua ydwe.lua  # YDWE 启动/语法脚本
│   └── jasshelper/pjass.exe          # 迁移后 JASS 语法检测（随 common.j/blizzard.j）
└── .claude/
    └── workflows/
        └── jass-migrate-trigger.js   # 迁移编码编排（可选，缺失则降级手动模式）
```

**要点**
- `map/war3map.j` + `table/` 是地图的两半数据源：物编（技能 ID 等）以 `table/*.ini` 为真值，`check-skill-id` 类治理应指向 `table/ability.ini`。
- `map/callback` / `map/(key)` 是 `initializePlugin` 引导链依赖，非模板噪音，勿删。
- 工具链闭环 = 编译打包（`tools/w3x2lni/w2l.exe` + `rsa` 签名）+ 语法检测（`tools/jasshelper/pjass.exe`）；迁移后语法校验依赖 pjass，缺则迁移闭环不完整。

---

## 核心能力

| 能力 | 命令 | 说明 |
|------|------|------|
| 全局分析 + PRD | `analyzer.py <war3map.j> -o <输出> [-s <策略>] [--lua-dir <目录>] [--status-file <文件>]` | 解析全部触发器，生成分批迁移 PRD |
| 单触发器分析 | `extract_trigger.py <war3map.j> <触发器名> [-o <输出>]` | 提取指定触发器的 API 依赖、变量、ECS 映射 |
| 标记已迁移 | `analyzer.py --status-file <文件> --mark <触发器名>` | 标记触发器为已迁移 |
| 查看进度 | `analyzer.py --status-file <文件> --status-list` | 显示迁移进度摘要 |

**策略选项**（`-s`）:
- `event-type` — 按事件类型分批（UNIT_DEATH, UNIT_ATTACKED 等）
- `complexity` — 从低复杂度到高复杂度
- `severity` — 按问题严重度（有 bug 的优先）
- `ecs-ready` — **推荐**：优先迁移 ECS 已就绪的事件类型

**复杂度评分**综合考量：代码行数、控制流复杂度、PolledWait 阻塞、Hashtable 操作、Helper function 调用链、API 类别多样性。

---

## 工作流程

### 推荐方式：直接调用工作流

用户选择要迁移的触发器后，调用 workflow：

```javascript
Workflow({ name: 'jass-migrate-trigger' }, { triggerName: '<触发器名称>' })
```

工作流自动完成：触发器分析 → 规范+Pre-flight → ECS 编码 → Self-review → 多维审查。

### 手动方式（脚本命令）

**首次分析（生成 PRD）**

1. 运行全局分析：
   ```bash
   python3 <skill目录>/scripts/analyzer.py map/war3map.j \
     -o docs/migrations/YYYY-MM-DD-jass-to-ecs.md \
     -s ecs-ready \
     --lua-dir map/script \
     --status-file docs/migrations/migrate_status.json
   ```

2. 展示 PRD 概要（触发器数量、事件分布、ECS 就绪度、已知问题）

3. 询问用户选择第一批要迁移的触发器（优先选 ECS 已就绪 ✅ 的低复杂度触发器）

**单个触发器迁移（手动模式）**

1. 提取触发器分析：
   ```bash
   python3 <skill目录>/scripts/extract_trigger.py \
     map/war3map.j <触发器名> \
     -o docs/migrations/analysis-<触发器名>.md
   ```

2. 展示分析结果（API 依赖、变量、ECS 映射、已知问题）

3. 按 MIG 规则实现 ECS 代码（有 workflow 则调用工作流）

4. 完成后标记为已迁移：
   ```bash
   python3 <skill目录>/scripts/analyzer.py map/war3map.j \
     --status-file docs/migrations/migrate_status.json \
     --mark <触发器名> \
     --mark-notes "迁移完成，已 DisableTrigger"
   ```

5. 按「war3map.j 注释规范」注释原触发器，并跑 pjass 语法检测

6. **检查迁移配额** — 已迁移 3 个触发器或总复杂度 ≥ 15 时，暂停展示进度，询问是否继续

### 查看迁移进度

```bash
python3 <skill目录>/scripts/analyzer.py \
  --status-file docs/migrations/migrate_status.json \
  --status-list
```

---

## 强制规则

| 规则 | 说明 |
|------|------|
| MIG-001 | **优先调用工作流** — 选择触发器后优先用 workflow 完成编码+审查；本 skill 不直接生成 ECS 代码，只输出分析结果和状态标记 |
| MIG-002 | **每次迁移询问用户** — 不自动批量迁移，用户选择范围和策略 |
| MIG-003 | **保留原始 JASS 不变** — 分析阶段不修改 war3map.j |
| MIG-004 | **迁移后标记** — 每个触发器迁移完成后用 `--mark` 标记状态 |
| MIG-005 | **PolledWait 必须标注** — 所有 PolledWait 调用在分析中突出显示，强制要求改为 ac.timer |
| MIG-006 | **完全转换** — 不做中间适配层/桥接层，逻辑直接落在 ECS 系统里 |
| MIG-007 | **单次迁移限 3 个触发器** — 每次迁移会话最多 3 个触发器（或总复杂度 ≤ 15，以先到者为准），完成后暂停让用户 review，避免失去专注力 |
| MIG-008 | **迁移后 war3map.j 完整注释** — 按下节规范注释四处代码 |

---

## war3map.j 注释规范

每个已迁移触发器在 `war3map.j` 中有四处需要注释，统一用 `// [ECS_MIGRATED] <类型> -- <名称>` 开头、`// [END_ECS_MIGRATED]` 结尾：

### 1. 全局变量声明 (行内注释)

```jass
// trigger gg_trg____________________047= null  -- [ECS_MIGRATED] 战鼓之歌
```

### 2. Actions 函数 (完整注释)

```jass
//===========================================================================
// [ECS_MIGRATED] Actions 函数 -- 战鼓之歌
// function Trig____________________047Actions takes nothing returns nothing
//     ... 原始代码逐行加 // 前缀，保留缩进 ...
// endfunction
// [END_ECS_MIGRATED]
```

### 3. InitTrig 函数定义 (完整注释)

```jass
// [ECS_MIGRATED] InitTrig 函数 -- 战鼓之歌
// function InitTrig____________________047 takes nothing returns nothing
//     set gg_trg____________________047=CreateTrigger()
//     call TriggerRegisterAnyUnitEventBJ(gg_trg____________________047, EVENT_PLAYER_UNIT_PICKUP_ITEM)
//     call TriggerAddAction(gg_trg____________________047, function Trig____________________047Actions)
// endfunction
// [END_ECS_MIGRATED]
```

### 4. InitTrig 调用 (行内注释)

```jass
// call InitTrig____________________047()  -- [ECS_MIGRATED] 战鼓之歌
```

**注释脚本模式**: 优先写 Python 脚本自动完成四处注释。脚本通过触发器编号（如 `047`）定位四处代码，不破坏其他触发器的代码。历史一次性脚本可归档到迁移文档目录的 `scripts/` 下，不属于本 skill。

**pjass 语法检测**: 每次注释完成后运行：

```bash
pjass.exe common.j blizzard.j war3map.j
```

- **先建基线再比对**: 注释前先跑一次记录已有 error 数，注释后只修**新增** error（遗留地图常有 pre-existing 错误，与本 skill 无关）
- 如有新 error，立即定位并修复注释

---

## 数据文件与模板

| 文件 | 用途 |
|------|------|
| `data/patterns.yaml` | JASS 模式 → ECS 模式映射（10 种常见模式），含推荐组件/系统/文件位置 |
| `data/api_mapping.yaml` | JASS API → Lua/ac API 映射（160+ 个 API） |
| `templates/migration_prd.md` | 全局迁移 PRD 文档模板 |
| `templates/trigger_analysis.md` | 单个触发器分析模板 |

> 这两个 yaml 的 ECS 侧（事件名/组件名/文件提示）绑定 ac/ecs 框架。目标项目若用同一套框架可直接复用；若框架不同，按目标项目的事件类/组件命名重写映射。

## 分析器能力概要

- **事件注册全覆盖**: 识别 15+ 种事件类型（死亡/攻击/施法/拾取/使用物品/计时器/进区域/聊天/选择/单位进入范围/可破坏物死亡/对话框等）
- **ECS 就绪度分析**: `--lua-dir` 扫描现有 Lua 代码，PRD 中标注每类事件 ✅ 已就绪 / 🟡 部分就绪（缺系统）/ ❌ 未就绪（需新建）
- **迁移进度追踪**: `--status-file` 维护 JSON 状态文件，支持增量分析与进度可视化

---

## 衔接提示格式

每个触发器分析末尾附实现衔接提示（有 workflow 引导调用 workflow，无 workflow 则给手动实现要点）：

```markdown
---
> 实现要点:
> 触发器功能描述: {描述}
> 建议文件: <Lua目录>/src/systems/{SystemName}.lua
> 建议组件: <Lua目录>/src/components/{CompName}.lua
> 注意事项: PolledWait 改为 ac.timer，hashtable 改为 Component
```
