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

## 五、测试收尾与切换回人工测试规范（Teardown & Switch to Manual Testing）

自动化测试或 Agent 探索执行结束后，收尾的核心目标是**「将测试流程与地图环境平滑切换回人工测试模式」**，使开发者或测试人员能够立即进行手动选人、自由游玩和人工验证，消除自动化钩子的干扰与残留。

Agent 必须遵循以下收尾与切换决策规则：

1. **收尾的核心本质：切换回人工测试模式（`toggle_test(enabled=false)`）**：
   - 自动化测试期间，Agent 会注入剧本并激活适配钩子（自动跳过难度选择、自动锁定选英雄、自动化技能连招施放）。
   - **收尾的核心动作即切换回人工测试**：调用 `toggle_test(enabled=false)` 写入 `_test_off.lua` 并自动重新编译地图。
   - **人工测试模式效果**：
     - ① **UI 交互全权交还**：难度/段位弹窗正常弹出供人工点选，候选英雄台恢复人工双击选择；
     - ② **控制权全权交还**：镜头与单位完全由玩家鼠标键盘控制，绝无自动化剧本劫持；
     - ③ **零开销与无干扰**：测试入口在首行直接 return，不挂载任何测试钩子，保持与发布版一致的手动体验；
     - ④ **保留按需调试通道**：仍保留聊天命令（输入 `-test on`），便于人工测试过程中随时手动按需呼出 Agent 辅助。

2. **收尾与切换的触发决策**：
   - **A. 自主闭环场景（批处理 / CI 回归 / 自动化 TDD 循环）**：
     - 当用例全部通过、逻辑验证完毕，且无需人工在此战局停步观察时：
     - Agent **自主判断工作已完成，主动执行收尾**：调用 `toggle_test(enabled=false)` 切换回人工测试模式，并调用 `cleanup_all` 退出已完成的实机进程，使项目立即可供人工开图测试。
   - **B. 主动询问场景（实机演示 / 演练验收）**：
     - 当用例带有画面演示性质（如技能特效、大字广播、连招结算），战局跑完退回主菜单后：
     - Agent **必须在汇报测试结果的同时，主动询问用户是否切换回人工测试**：
       * 例如：“实机测试已完成，游戏已退至主界面。请问是否需要为您**切换回人工测试模式**（关闭自动化钩子并退出当前窗口，方便您手动开图测试）？”
     - 收到用户确认后立即执行切换。

3. **收尾标准动作清单**：
   - ① **解冻主线程**：若此前使用了 step 步进模式，确保调用 `game_set_mode(mode="free")`；
   - ② **切回人工测试**：调用 `toggle_test(enabled=false)`，清除自动测试入口并自动重编译地图；
   - ③ **释放进程与管道**：调用 `cleanup_all` 或 `stop_game` 终止自动化战局进程并断开命名管道。

