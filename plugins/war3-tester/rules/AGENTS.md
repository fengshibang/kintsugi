# War3 自动化测试与 Named Pipe Agent 运行时规范

本规则约束 AI 在执行 War3 地图自动化测试、实机探索与 TDD 功能开发时的行为准则与故障排查规范。

---

## 一、实机测试“零命令、直接启动”铁律（核心准则）

1. **严禁要求用户输入任何聊天命令**：
   - 严禁要求用户在聊天框中输入 `-test on`、`-agent on` 或任何交互指令。
   - 实机测试必须做到**零命令输入、点开即跑、全自动闭环**。
2. **自动屏蔽 UI 阻塞与自动选人**：
   - Agent 发起实机测试时，必须确保适配钩子自动生效：自动拦截并静默处理段位/难度选择弹窗（`difficulty_skip`），自动锁定候选英雄台完成双击选人（`hero_auto_select`），杜绝任何模态弹窗或待选状态卡死。
3. **全流程可视化演练与大字广播**：
   - 实机剧本必须自动将镜头聚焦到主控英雄并选中（`PanCameraToTimed` / `SelectUnitForPlayerSingle`）。
   - 关键动作与阶段（选人、学技能、施法扣真气、CD转动、叠层满层、周身终极形态）必须通过 `DisplayTextToPlayer` 在屏幕中央输出大号彩色公告，并在步骤间预留充足观察时长（2~3 秒），确保用户与实机录屏清晰可见。

---

## 二、Agent 全权主导的 TDD（测试驱动开发）方案规范

当用户提出任何武学、心法、装备或新系统开发需求时，**方案必须由 Agent 全权设计设定**，遵循标准化 TDD 闭环：

```
[契约与 Seam 明确] 
       ↓
[Red 红阶段] 编写 Tier 1 桌面单测 + Tier 2 实机剧本 → 运行确认失败 (Red)
       ↓
[Green 绿阶段] 编写最小生产代码（纯逻辑放生产目录） → run_unit_test 毫秒级转绿
       ↓
[Verify 实机验收] test_commit 驱动实机直接启动（零命令输入） → 自动选人跑剧本全绿
```

1. **契约设计先行**：明确被测对象的 Public Interface (Seam)、物编 ID、消耗、CD、作用范围、五轴武学坐标与专属分支门槛，先列方案再写代码。
2. **纯逻辑模块放生产目录，严禁放 `test_dir`**：
   - 计算、状态机和公式模块必须与系统同级放在生产目录（如 `map/script/src/data/`），确保地图发布剥离测试目录后生产 `require` 不崩溃。
3. **红绿严格推进**：
   - 🔴 **Red**：先写单测，运行确认报错符合预期，验证断言有效性；
   - 🟢 **Green**：补齐逻辑实现，运行 `run_unit_test` 秒级全绿；
   - 🎮 **实机集成**：自动拉起 `test_commit` 驱动游戏实机验收，零手动命令，直接向用户呈现测试结果与过程。

---

## 三、四层测试体系与工具选型

1. **Tier 1 — 桌面纯逻辑单测 (`unit`)**：
   - 使用 `run_unit_test` / `watch_unit_tests`，通过桌面 Lua 5.3 + `jass_mock` 秒级运行。
2. **Tier 2 — 实机剧本测试 (`integration` / `e2e`)**：
   - 使用 `test_commit` / `run_test_batch` 启动 `War3.exe` 跑 `TestScenario` / `TestRunner`，通过 Windows 命名管道 `\\.\pipe\war3_agent`（`bridge.event('test_progress' | 'test_log' | 'test_error' | 'test_result', ...)`）实时上报进度、日志与结果，**零 TCP/HTTP 端口占用**。
   - `TestScenario:new(name, ...)` 的 `name` 参数必须与 `test_name` 完全一致。
3. **Tier 3 — Named Pipe 实时查询 (`inspect_game` / `exec_game` / `game_setup`)**：
   - 采用 Windows 命名管道 `\\.\pipe\war3_agent`（多开时支持 `\\.\pipe\war3_agent_<pid>`），支持多 IDE / MCP 进程并发连接且零端口冲突。
   - 游戏内通过 `run_game(inject_inspect=True)` 自动注入启动，零命令全自动连通。
4. **Tier 4 — LLM Play / Bug 探索 Agent (`game_*` 工具集)**：
   - 使用 `game_status`、`game_set_mode`、`game_observe`、`game_act`、`game_events`、`game_inspect`、`game_setup`、`game_report_bug` 进行步进式实机探索与五大 Oracle 自动巡检。
   - **⚠️ 步进模式解冻铁律**：一旦调用 `game_set_mode(mode="step")` 冻结了游戏主线程，在探索或调试结束时**必须调用 `game_set_mode(mode="free")`**，严禁将用户游戏留在冻结卡死状态。
5. **一键环境安装 / 体检 / 修复 (`setup_environment`)**：
   - 当测试或命名管道异常时，优先调用 `setup_environment(mode="check")` 体检，或 `setup_environment(mode="repair")` 一键修复。

---

## 四、wzns 项目 ECS 与 Agent 编写陷阱防护

1. **`HeroComp` 实体集合遍历必须用 `pairs()`**：
   - `engine:getEntitiesWithComponent('HeroComp')` 返回的是以 `entity.id` 为键的字典（哈希表），而非连续数组。使用 `ipairs()` 会永远返回空，**必须使用 `pairs()`**。
2. **`engine.entities` 阵营判断前必须过滤 `UnitModelComp`**：
   - `engine.entities` 中包含 `PlayerObj` 等非单位实体。调用 `hero:isEnemy(ent)` / `hero:isAlly(ent)` 前必须先检查 `ent:get('UnitModelComp') ~= nil`，否则在 `PlayerObj:isEnemy` 内会触发 `attempt to index a nil value (local 'dest')`。
3. **ECS 事件监听器必须继承 `System`**：
   - `EventManager:addListener` 要求监听器实例包含 `listener.class.name` 字段。在 `auto-test` 或 `agent` 中注册 ECS 事件监听时，必须定义为 `class("XxxSystem", System)` 并通过 `engine:addSystem` 与 `em:addListener` 注册。
4. **选人阶段动作**：
   - 刚进入地图尚未双击选英雄时，`game_observe` 的 `hero` 为 `nil`，但会在 `nearby_units` 中列出候选英雄台（`selectable_hero = true`）。此时应先下发 `{"op": "select_hero", "unit_id": <id>}` 完成选人。

---

## 五、测试收尾与生命周期环境清理规范（Teardown & Cleanup Lifecycle）

实机自动化测试或探索结束后，为避免占用系统资源、挂起游戏进程或干扰后续正常游玩，Agent 必须遵循以下收尾决策规则：

1. **自主收尾清理（工作闭环场景）**：
   - 当 Agent 在执行无需用户人工介入的自动化任务（如：CI 自动化回归、批量单测/集成测试 `run_test_batch`、TDD 红绿循环中的快速验证）：
   - 一旦测试用例全部执行通过、断言验证完毕，**Agent 应自行判断工作已完成，主动调用 `cleanup_all` / `stop_game` 释放游戏进程与命名管道**，并按需调用 `toggle_test(enabled=false)` 将地图还原为纯净游玩模式，无需等待用户手动输入。

2. **主动询问收尾清理（人工观察/演练验收场景）**：
   - 当执行的是带有可视化展示性质的实机测试（如展示技能特效、全流程演练、录屏调试），战局结束退回到魔兽主界面后：
   - Agent **必须在汇报测试结果的同时，主动询问用户是否进行收尾清理**（例如：“实机测试演练完成，游戏已退至主界面。请问是否需要为您关闭魔兽窗口并清理测试环境（`cleanup_all`）？”）。
   - 用户确认或告知已看完后，Agent 立即调用 `cleanup_all` 清理。

3. **清理动作标准清单**：
   - ① **解冻主线程**：若此前使用了 step 步进模式，确保调用 `game_set_mode(mode="free")`；
   - ② **关闭游戏进程与管道**：调用 `cleanup_all` 或 `stop_game`，终止 `War3.exe` 并关闭 `\\.\pipe\war3_agent`，释放句柄；
   - ③ **还原纯净环境**：若用户后续需要手动进入地图正常体验游戏，调用 `toggle_test(enabled=false)` 恢复难度选择弹窗与手动选人。
