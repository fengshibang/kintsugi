---
name: war3-auto-test
version: 3.0.0
description: "魔兽争霸 3 地图自动化测试与 LLM Agent 实机探索（v3.0 四层测试体系 + Named Pipe 桥接）。支持桌面秒级单测（unit）、实机集成/全流程测试（integration/e2e）、实时命名管道状态查询（inspect_game/exec_game）与 LLM 步进探索/五大 Oracle 自动巡检（game_* 工具）。触发词：自动测试、测试全部、跑测试、/war3-test、测试某模块、实机探索。"
---

# War3 地图自动化测试与 LLM Agent 探索（v3.0）

**核心目标**：一条命令跑完全部测试，AI 自主完成「发现 → 批量执行 → 失败分析 → 修复 → 重验」与「实机步进探索 + 五大 Oracle Bug 巡检」，无需人工逐步盯梢。

---

## 四层测试体系总览

| 层级 | 名称 | 运行环境 | 耗时 | 核心工具 | 适用场景 |
|---|---|---|---|---|---|
| **Tier 1** | **桌面纯逻辑单测 (`unit`)** | 桌面 Lua 5.3 + `jass_mock` | **< 1 秒** | `run_unit_test` / `watch_unit_tests` | 伤害公式、词条计算、残卷配置、数据表校验 |
| **Tier 2** | **实机剧本/集成测试 (`integration` / `e2e`)** | 启动 `War3.exe` 跑 `TestScenario` / `TestRunner` (`\\.\pipe\war3_agent` 回传) | 15 ~ 60 秒 | `test_commit` / `run_test_batch` | 技能释放完整生命周期、Buff 驱散、多波次刷怪、投射物碰撞 |
| **Tier 3** | **Named Pipe 实时交互查询 (`inspect` / `exec`)** | 已运行的 `War3.exe` (`\\.\pipe\war3_agent`) | **~16 毫秒** | `inspect_game` / `exec_game` / `game_setup` | 边玩边查 ECS 实体/组件数据、实时刷怪/跳关/发装备/改属性 |
| **Tier 4** | **LLM Play / Bug 探索 Agent (`agent`)** | 已运行的 `War3.exe` + 步进冻结 (`step`) + 五大 Oracle | 按步实时 | `game_status` / `game_set_mode` / `game_observe` / `game_act` / `game_events` / `game_report_bug` | AI 自主选英雄、放技能、跑图，配合五大 Oracle 自动抓 NaN/卡死/泄露 |

---

## 核心工作流

### 0. 铁律准则：零命令直接启动与 Agent 全权主导 TDD

1. **实机测试“零命令、直接启动”**：
   - 严禁要求用户在聊天框输入 `-test on`、`-agent on` 或任何指令。
   - 所有实机剧本通过 `test_commit` 或 Named Pipe Agent 自动启动、自动拦截屏蔽难度弹窗（`difficulty_skip`）、自动选英雄（`hero_auto_select`）、进图即跑，全屏大字广播进度。
2. **Agent 全权主导 TDD 开发方案**：
   - 任何武学/心法/机制开发必须由 Agent 全权制定方案：
     - 契约设计（Seam、物编 ID、五轴属性、专属分支）
     - 🔴 **Red**：先写 Tier 1 桌面单测 + Tier 2 实机剧本，运行确认失败
     - 🟢 **Green**：编写最小生产代码（纯逻辑放生产目录），桌面单测秒级全绿
     - 🎮 **Verify**：自动拉起实机测试（零命令输入），自动验证与反馈

3. **双轨测试模式（意图识别与黑白盒路由规范）**：
   - **用户意图精准识别与路由**：
     - **显式黑盒意图**（「黑盒」、「拟真」、「玩家模拟」、「非侵入」、「端到端」、「E2E」、「录屏」等）：
       → **强制路由至【模式 A：黑盒拟真模式】**：100% 模拟真实玩家（双击选英雄、界面自选武学、按键施法、敌怪攻击真实受击叠层、冷却自然走完），严禁使用任何侵入式修改或测试钩子置值；
     - **显式白盒意图**（「白盒」、「注入」、「侵入」、「快速」、「压测」、「边界值」、「回归」等）：
       → **强制路由至【模式 B：白盒快速注入模式】**：允许使用测试钩子秒级重置 CD、置入 Buff 层数，极速验证核心数学模型与状态机深层逻辑；
     - **隐式/模糊意图**：若涉及耗时/拟真度显著差异，主动向用户列出选项并提供推荐；若属轻量常规验证，默认采用黑盒拟真以保证最高拟真度。
   - **规范化呈现**：屏幕大字公告必须标明 `【黑盒拟真】` 或 `【白盒注入】`，命名管道上报携带 `mode` 字段。
4. **测试通过必须证据确凿（截图 + 真实数据日志，严禁 AI 臆想通过）**：
   - 每次实机测试结论必须提供双重证据：
     - **视觉截图证据**：调用 `take_screenshot` 保存测试画面（选人/大招/满层/广播大字），作为证据直观呈现给用户肉眼审查；
     - **真实数据与管道日志**：展示命名管道 `\\.\pipe\war3_agent` 回传的真实原始数据、运行耗时与数值前后对比断言（如真气 100 -> 50、减伤 0 -> 0.15）；
   - 若无截图或真实回传数据，**严禁空口判定通过**，必须如实汇报为证据缺失。
5. **黑盒拟真模式四大防作弊红线（违者直接判定伪测试）**：
   - 🔴 **严禁篡改数值**：严禁 `set_level`、`tier='T5'`、`asc_pick.apply` 等直接改内存伪造装备/升华成长，必须经由真实打怪累加金币与商店购买扣除；
   - 🔴 **严禁定身敌怪**：严禁调用 `PauseUnit` 把 Boss/敌怪定身，敌怪必须具备自主普攻、技能与伤害循环；
   - 🔴 **严禁核弹秒杀与强杀**：严禁 `1e12` 等超自然伤害与 `KillUnit`，伤害与斩杀必须走原生普通攻击与技能命中；
   - 🔴 **严禁偷换概念**：严禁将单点 GameOver 状态机广播推断为全流程通关，必须具备完整的【经济因果链】、【战斗因果链】与【时间因果链】。

### A. 无人值守回归循环（Tier 1 & Tier 2）

```
cleanup_all → compile_only → discover_tests → run_test_batch(test_filter="all")
                                                      ↓
                                          全通过？──是──→ 报告完成
                                              │否
                                              ↓
                              按 failure_type 查诊断决策树（至多 3 轮）
                                              ↓
                              codegraph_explore 定位根因 → 修改代码
                                              ↓
                              run_test_batch(test_filter="failed") 重验
```

> **🛡️ 防失控护栏（v0.21.1）**：`run_test_batch` 中 `unit` 层一律走桌面 Lua、绝不启动游戏；`env_error` 不重试且连续 2 次即熔断；单批次最多拉起游戏 `max_game_launches=10` 次、墙钟 `max_batch_seconds=900`；同一时刻只允许一个实机批次。运行中随时可调用 `stop_game` / `cleanup_all` 立即中止（客户端超时取消也会自动熔断）。**跑全部单测请用 `run_test_batch(layer="unit")` 或 `run_unit_test`，不要用无 layer 的 `run_test_batch`。**

### B. Named Pipe 实机步进探索与交互调试（Tier 3 & Tier 4）

> **通信机制**：通过 `agent_bridge.dll` 建立 Windows 命名管道 `\\.\pipe\war3_agent`（以及支持多开的 `\\.\pipe\war3_agent_<pid>`），设置 `PIPE_UNLIMITED_INSTANCES` 与跨权限安全描述符。多个 IDE / MCP 进程可同时连接同一游戏实例，**零 TCP 端口冲突，零轮询延迟**。
>
> **激活方式**：
> 1. 调用 `run_game(inject_inspect=True)` 启动游戏（自动注入 `agent.init` 引导并开启管道）；或
> 2. 手动启动游戏后，在聊天框输入 **`-test on`**（或 `-agent on`）手动热启动管道。

```
game_status（确认管道连通）
  → game_observe(detail="full")（读取英雄/候选英雄台/周围敌友/技能冷却）
  → game_set_mode(mode="step")（切入步进冻结模式，精细控制）
  → 循环：
      game_act(actions=[...], run_seconds=1.0)（下发选英雄/移动/攻击/施法并推进 1 秒）
      检查返回中的 observation 与 events（含五大 Oracle 的 violation 事件）
      若有异常 → game_inspect 深入核查 ECS 状态 → game_report_bug 记录复现步骤
  → 结束探索：务必调用 game_set_mode(mode="free") 解冻游戏恢复正常游玩！
```

> **⚠️ 重要铁律**：使用 `game_set_mode(mode="step")` 冻结游戏做完步进调试后，**结束时必须调用 `game_set_mode(mode="free")` 解冻游戏**，否则游戏画面会一直停留在冻结态等待指令。

### C. 测试收尾与切换回人工测试规范（Teardown & Switch to Manual Testing）

自动化测试或 Agent 探索完成后的核心收尾动作是**「平滑切换回人工测试模式」**，杜绝自动化钩子（跳过选难度、自动选英雄）对人工测试的干扰：
- **核心机制**：调用 `toggle_test(enabled=false)` 写入 `_test_off.lua` 并重新编译地图，彻底交还 UI 交互（难度弹窗正常弹出）与英雄挑选权，使地图与环境立即可供人工开图测试。
- **自动闭环场景**：CI 回归、批量测试或 TDD 纯逻辑验证通过后，Agent 自主判定工作完成，自动调用 `toggle_test(enabled=false)` 还原环境并执行 `cleanup_all`。
- **实机演示场景**：演练完成退回主菜单后，Agent 汇报结果并主动询问用户：“实机测试已完成，是否为您**切换回人工测试模式**（关闭自动化钩子并关闭当前窗口）？”收到确认后执行切换。


---

## MCP 工具清单（共 34 个）

### 1. 编译、启动与批量测试工具

| 工具 | 用途 | 关键参数 |
|---|---|---|
| `compile_only` / `compile_map` | 仅编译地图（`w2l.exe slk`） | `source_dir` |
| `discover_tests` | 扫描测试目录，返回列表+分类+估算耗时 | `filter`, `layer` |
| `run_unit_test` | **桌面秒级跑纯逻辑单测**（不启动游戏） | `test_name`, `timeout=10` |
| `test_commit` | 单测实机执行（编译+启动+等待+诊断） | `test_name`, `timeout=60`, `auto_screenshot_on_failure=True` |
| `run_test_batch` | **批量顺序运行测试**，返回结构化汇总 | `test_filter="all"\|"failed"\|[...]`, `layer="all"\|"unit"\|"integration"\|"e2e"` |
| `run_game` | 启动游戏（默认自动注入 Named Pipe Agent 引导） | `inject_inspect=True`, `source_dir` |
| `launch_only` | 仅启动游戏，不编译不注入 | `map_path`, `platform` |
| `toggle_test` | **一键开关自动测试模式**（关闭时写 `_war3_tester/_test_off.lua` 重编译，手动玩零干扰） | `enabled: true\|false` |
| `setup_environment` | **一键部署环境组件**（`socket.dll` / `Flask` / `nopause.asi` / `agent_bridge.dll`） | `components=["socket","http","nopause","agent_bridge"]` |
| `cleanup_all` / `stop_game` | 关闭 `War3.exe` 进程、命名管道与 HTTP 服务 | - |
| `take_screenshot` / `send_key` | 截取游戏窗口 PNG / 发送键盘按键（含组合键） | `test_name` / `key` |
| `get_project_info` / `get_debug_output` | 静态扫描脚本结构 / 聚合游戏日志与运行时错误 | `source_dir`, `level`, `limit` |
| `scaffold_test` / `tdd_red` / `tdd_green` | TDD 骨架生成与红绿阶段验证 | `module`, `layer`, `test_name` |
| `watch_unit_tests` / `stop_watch` / `get_watch_results` | 后台监控文件改动自动重跑 `unit` 单测 | `test_name` |
| `save_adapter_hook` | 保存项目专属适配钩子（如跳过难度弹窗）到 `_war3_tester/adapters/` | `name`, `content` |

### 2. Named Pipe 实时查询与 LLM Agent 工具（`\\.\pipe\war3_agent`）

| 工具 | 用途 | 关键参数 |
|---|---|---|
| `inspect_game` | **实时执行 Lua 表达式**（走命名管道，毫秒级返回） | `expr`, `timeout=5`, `pid?` |
| `exec_game` | **实时执行带副作用的 Lua 语句块**（走命名管道） | `code`, `timeout=5`, `pid?` |
| `game_status` | 查询 `agent_bridge` 状态、版本、Lua 帧钟与冻结态 | `pid?` |
| `game_set_mode` | 切换运行模式：`'step'`（步进冻结）或 `'free'`（自由运行并自动解冻） | `mode="step"\|"free"`, `pid?` |
| `game_observe` | 获取结构化语义视界快照（英雄属性/技能/背包、周围敌友、可选英雄列表） | `detail="full"\|"brief"`, `radius=1200`, `pid?` |
| `game_act` | 下发批量语义动作并推进 `run_seconds` 秒 | `actions=[...]`, `run_seconds=1.0`, `pid?` |
| `game_events` | 增量拉取游戏事件（`unit_damaged`, `unit_died`, `violation` 等） | `since_seq=0`, `kinds?`, `pid?` |
| `game_inspect` | 对游戏内 Lua 表达式求值并返回结构化 JSON | `expr`, `pid?` |
| `game_setup` | 场景快速预置（刷怪/设等级/发物品/加钱/回满/刷CD/传送/清场） | `cmd`, `args={...}`, `pid?` |
| `game_report_bug` | 提交探索发现的 Bug 报告，写入 `logs/agent_bugs.md` | `title`, `severity`, `steps`, `evidence_seqs` |

#### `game_act` 支持的语义动作 (`op`)
- `{"op": "select_hero", "unit_id": 1048902}`：双击选中候选英雄完成选人
- `{"op": "move", "x": 500, "y": -300}`：移动到坐标
- `{"op": "attack", "target_id": 1049100}`：攻击指定单位 handle
- `{"op": "attack_move", "x": 500, "y": -300}`：A 地板进攻移动
- `{"op": "cast", "slot": "Q", "target": "none"|"point"|"unit", "x": ..., "y": ..., "target_id": ...}`：释放技能（支持按槽位 `"Q"/"W"/"E"/"R"/"D"/"F"` 或物编 `"id": "A000"`）
- `{"op": "use_item", "slot": 1, "target": ...}`：使用背包槽位（1~6）物品
- `{"op": "stop"}` / `{"op": "chat", "text": "-test status"}` / `{"op": "wait"}`

#### 五大内置实时 Oracle（自动挂靠 `game_events`）
1. **`numeric`（数值异常）**：检测英雄 HP/MP/金币/等级 NaN、无穷大、负数或单帧异常暴涨（`> 1e7`）。
2. **`error_log`（运行时报错）**：拦截 `log.error` / `error_handle` 并记录完整堆栈。
3. **`stuck`（状态卡死）**：监控英雄存活且连续下达移动/施法指令却连续 15 秒坐标/状态零变化。
4. **`consistency`（ECS 一致性）**：校验 `engine.entities` 存活实体的 JASS 句柄有效性，以及死亡超过 5 秒未清理的残留实体。
5. **`perf`（性能泄露）**：监控 Lua 内存增量（`collectgarbage("count")`）与实体总数暴涨。

---

## 失败类型与诊断决策树（`test_commit` / `run_test_batch`）

| `failure_type` | 含义 | 自动截图 | 诊断动作 |
|---|---|---|---|
| `compile_error` | `w2l` 编译失败 | 否 | 读 `error` 输出 → 定位物编/语法错误 → 修复重编译 |
| `crash` | `War3.exe` 进程消失 | 是 | 读 `crash_log` + 框架日志末尾 → 查 native 崩溃常见诱因（无效 handle / 除零 / 无限递归） |
| `timeout` | 超时未收到 `/result` | 是 | ① 看 `progress` 最后完成的 step → 定位卡住的步骤；② 视觉 MCP 判读截图是否卡在弹窗/暂停；③ 查 `logs` 最后输出 |
| `assertion` | 断言失败 | 否 | 读 `details` + `logs` → `codegraph_explore` 查被测函数实现 → 定位逻辑偏差并修复 |
| `runtime_error` | Lua 运行时抛错 | 否 | 读 `game_errors[].traceback` → 定位文件:行号 → 查 nil 解引用/类型错误 |
| `env_error` | 基础设施异常 | 否 | 检查 `setup_environment` 四大组件是否已部署 |

---

## 可测性约定与纯逻辑分离

1. **纯逻辑模块放生产目录，严禁放 `test_dir`**：
   - 被生产代码运行时 `require` 的纯计算模块必须放在生产目录（与被测系统同目录），防止正式版剥离 `test_dir` 后崩溃。
   - 检查命令：`grep -rn "require.*auto-test" map/script/src/` 应零命中（除入口引导外）。
2. **数据结构与模块风格对齐项目实际**：
   - 测试输入/输出使用项目真实数据表与组件类，禁止凭空捏造玩具结构。
3. **测试产物隔离在 `<test_dir>/_war3_tester/`**：
   - `_target_test.lua`、`_test_off.lua`、`assertions.lua`、`jass_mock.lua`、`adapters/` 均归拢在 `_war3_tester/` 下。
