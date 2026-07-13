---
name: war3-auto-test
version: 2.0.0
description: "通用 War3 地图自动测试：发现 → 批量跑 → 分析 → 修复 → 重验 无人值守循环。最小契约（RunAutoTest + POST 8766），不限 Lua 框架。"
---

# War3 Auto Test - 无人值守测试循环（v2.0）

> **触发方式**：用户输入 `/war3-auto-test` 或 agent 通过 Skill 工具调度
> **核心升级（v2.0）**：从「单次手动驱动」升级为「批量自动循环 + 丰富反馈」。
> 一条 `run_test_batch` 指令跑完全部测试，失败自动给出 `failure_type` + `progress` 时间线 + `logs`，Claude 据此直接定位修复，无需逐步人工干预。

---

## 无人值守循环（核心工作流）

```
Phase 1: 准备
  → cleanup_all()                 # 清理残留进程/服务
  → compile_only()                # 验证编译通过（编译失败直接修，不必进游戏）

Phase 2: 发现
  → discover_tests()              # 扫描 auto-test/，返回测试列表 + 分类 + 估算耗时

Phase 3: 执行（一条指令，阻塞等待）
  → run_test_batch(filter="all", auto_screenshot_on_failure=true)
  返回结构化汇总：{summary, results[], failed[]}

Phase 4: 分析
  → 读返回的 summary.pass_rate
  → pass_rate == 1.0  → 报告成功，结束
  → 有 failure        → Phase 5

Phase 5: 修复（循环，最多 3 轮）
  → 按 failure_type 查【诊断决策树】→ codegraph_explore 理解相关代码 → 修复
  → run_test_batch(filter="failed")   # 只重跑上次失败的（内存缓存，不持久化）
  → 全通过 → 报告完成
  → 仍失败 → 报告需人工介入（附 failure_type + progress + logs + 截图）
```

**关键**：Phase 3 一条指令跑完全部，Phase 5 用 `filter="failed"` 只重验修复项。Claude 全程不逐步驱动。

---

## 诊断决策树（按 failure_type 处置）

每个失败测试的结果含 `failure_type`，按下表处置：

| failure_type | 判定依据 | Claude 处置 |
|---|---|---|
| `compile_error` | w2l.exe 返回非 0 | 运行 `compile_only` 看详细错误 → 修物编/配置 |
| `crash` | 游戏进程在测试期间消失（曾启动后丢失） | 看 `progress` 最后一步 + `logs` → `codegraph_explore` 查最近修改的 API；崩溃日志 `crash_log`（读 War3 根目录 `Errors\`）P1 提供 |
| `timeout` | 超过 `timeout_per_test` 无 `/result` | 看 `progress` 卡在哪步 → 检查 `waitFor` 条件是否可达、是否卡对话框 |
| `assertion` | `success=false` 且有失败断言 | 看 `assertions` + `progress` 的 failed 步 → `codegraph_explore` 追溯数据来源 |
| `runtime_error` | `game_errors` 非空且有 traceback | 看 traceback 定位行号 → `codegraph_explore` 查该行 API |
| `env_error` | HTTP 不通 / 端口占用 / 进程从未启动 | 运行 `cleanup_all` → 重跑 |
| `unknown` | 无法归类 | 触发截图（已自动） + 报告需人工介入 |

> **截图策略（设计文档 4.7）**：仅 `crash` / `timeout` / `unknown` 自动截图（`auto_screenshot_on_failure=true` 时）；`assertion` / `runtime_error` / `compile_error` 不截图（日志已足够诊断）。

---

## 结果格式 v2

单测试结果（`run_test_batch` 返回的 `results[]` 每项，`test_commit` 返回同结构）：

```json
{
  "test_name": "test_skill_a00d",
  "success": false,
  "failure_type": "assertion",
  "elapsed": 18,
  "duration_ms": 18340,
  "result": { ... },            // 游戏侧 /result 原始数据（含 progress/logs 已由 MCP 回填）
  "result_file": ".../test_skill_a00d.json",
  "progress": [                 // 逐步骤进度时间线（游戏侧 TestScenario:step 上报）
    {"step": "wait_hero", "phase": "done", "elapsed_ms": 1200},
    {"step": "cast_skill", "phase": "done", "elapsed_ms": 5100},
    {"step": "assert_damage", "phase": "failed", "detail": {"expected":">100","actual":52}}
  ],
  "logs": [                     // 结构化分级日志（游戏侧 log.info/log.error 拦截上报）
    {"level": "info", "category": "", "message": "..."},
    {"level": "error", "category": "runtime", "message": "...", "context": {"traceback":"..."}}
  ],
  "game_errors": [ ... ],       // /error 端点缓存（runtime_error 判定依据）
  "crash_log": null,            // 崩溃日志（P1：读 Errors\<时间戳> Crash.txt）
  "screenshots": [".../test_xxx_failure.png"],
  "error": "部分断言失败"
}
```

批量汇总（`run_test_batch` 顶层）：

```json
{
  "success": false,
  "message": "批量测试完成：18/24 通过，通过率 75%",
  "summary": {
    "total": 24, "passed": 18, "failed": 6, "pass_rate": 0.75,
    "stop_on_first_failure": false,
    "failure_types": {"assertion": 4, "timeout": 1, "crash": 1}
  },
  "results": [ ... ],           // 每个测试的 v2 结果
  "failed": ["test_skill_a00d", "..."]   // 供 filter="failed" 复用
}
```

---

## MCP 工具清单

| 工具 | 说明 |
|---|---|
| **`run_test_batch`** | **核心（v2 新增）**：顺序运行多个测试（每测试独立游戏会话），返回结构化汇总。入参：`test_filter`（`"all"`/`"failed"`/列表/子串）、`stop_on_first_failure`、`max_retries`(默认1)、`timeout_per_test`(默认90)、`auto_screenshot_on_failure`(默认true)、`platform`、`source_dir` |
| **`discover_tests`** | **v2 新增**：扫描测试目录，返回 `[{test_name, file, type(sync/async), est_seconds}]` + 总估算 |
| `test_commit` | 单测：编译+启动+等待结果（v2 增强：崩溃检测/`failure_type`/失败截图/`game_errors`）。入参新增 `auto_screenshot_on_failure` |
| `compile_map` / `compile_only` | 编译地图（同步等待 w2l.exe） |
| `run_game` / `launch_only` | 仅启动游戏 |
| `stop_game` | 关闭 War3 进程 |
| `take_screenshot` | 截取游戏窗口（PrintWindow） |
| `send_key` | 向 War3 窗口发送键盘事件 |
| `cleanup_all` | 关闭 war3.exe 进程和 HTTP 服务器 |
| `stop_http_server` | 仅关闭 HTTP 测试服务器 |

### 反馈通道分层（设计文档第三节）

| 优先级 | 通道 | 模式 | 用途 |
|---|---|---|---|
| ① 主 | `POST /progress`、`/log`、`/error`、`/result` | PUSH（游戏→MCP） | 活信息实时采集 |
| ② 主 | MCP notification | PUSH（MCP→Claude） | batch 运行中实时回传（渲染效果待实测，P0 不依赖） |
| ③ 辅 | 读 `Errors\` 文件 | PULL | 仅崩溃兜底（P1） |
| ④ 兜底 | PrintWindow 截图 | PULL | 最终手段（仅 crash/timeout/unknown） |

---

## 最小测试契约（通用，不限 Lua 框架）

插件与目标项目只约定一个最小契约：

1. **测试文件**：`<source_dir>/<test_dir>/test_*.lua`，定义全局 `RunAutoTest()`（或用框架适配器桥接，见下）。
2. **HTTP 上报**：测试完成后 `POST http://<host>:8766/result`，JSON 含 `test_name`、`success`、`assertions` 等。
3. **进度/日志上报（v2 可选，推荐）**：
   - `POST /progress`：逐步骤进度 `{test_name, step, phase(start/done/failed), detail, elapsed_ms}`
   - `POST /log`：分级日志 `{test_name, level(info/warn/error), category, message, context}`
4. **引导机制**：`test_commit` 编译前写 `_target_test.lua`（配置）+ `run_auto_test.lua`（引导模板）到 `<test_dir>/`。

### 自定义引导模板（已有测试框架的项目用）

通用引导加载后立即调用 `RunAutoTest()`。若项目已有测试框架（如自带测试运行器 + 初始化事件钩子，执行时机不同），用 `test_bootstrap_template` 指向自定义适配器：

```json
{
  "test": {
    "test_dir": "auto-test",
    "test_module_prefix": "",
    "test_bootstrap_template": "path/to/your_adapter.lua"
  }
}
```

适配器契约：读 `_target_test.lua` 的通用字段（`test_name/test_file/test_module/test_module_prefix/http_host/http_port`）→ 按项目机制加载测试、执行 → HTTP 上报 → 正常游戏时静默降级。范例见插件 `examples/`。

---

## 配置（`config.json`，插件 project_root 下）

```json
{
  "test": {
    "test_dir": "auto-test",
    "test_module_prefix": "",
    "test_bootstrap_template": ""
  },
  "compile": { "source_dir": ".", "output_path": ".", "output_name": "map.w3x" },
  "http_server": { "host": "0.0.0.0", "port": 8766 },
  "ydwe_path": "D:\\war3\\YDWE",
  "kkwe_path": "D:\\KKWE"
}
```

| 配置项 | 默认 | 说明 |
|---|---|---|
| `test.test_dir` | `"auto-test"` | 测试目录（相对 `source_dir/`） |
| `test.test_module_prefix` | `""` | require 模块前缀（空=同目录加载；非空=`prefix..name`） |
| `test.test_bootstrap_template` | `""` | 自定义引导模板路径（空=用通用 `server/lua_bootstrap.lua`） |
| `compile.output_name` | `"map.w3x"` | 编译输出地图名 |
| `compile.source_dir` | `"."` | 源码根（支持 `${workspaceRoot}`） |

> 路径类配置也可用环境变量 `.env`（`YDWE_PATH`/`KKWE_PATH`/`W2L_PATH` 等），见插件 CHANGELOG。

---

## 自适应环境桥

| 环境 | 编译/启动/截图 | 实现 |
|---|---|---|
| **WSL** | 经 `win_proxy`（TCP 8767）转发到 Windows | `env_bridge.WinProxyExecutor` |
| **原生 Windows** | 直接 `subprocess` | `env_bridge.LocalExecutor` |

WSL 用户需在 Windows 侧 `python win_proxy.py start`（监听 8767）。

---

## TDD 工作流（M3 新增）

> **目标**：秒级 Red-Green-Refactor 循环，测试驱动开发。

### 测试分层（unit / integration / e2e）

| 层 | 文件名约定 | 运行方式 | 反馈速度 | 适用场景 |
|---|---|---|---|---|
| **unit** | `test_unit_*.lua` | 桌面 lua5.3（`run_unit_test`） | 秒级（<2s） | 纯逻辑（配置校验、算法、数据处理） |
| **integration** | `test_int_*.lua` | 游戏内（`test_commit`） | 30s+ | 依赖游戏 API（单位、技能、Buff） |
| **e2e** | `test_e2e_*.lua` | 游戏内（`test_commit`） | 60s+ | 全流程（副本、任务链、多系统交互） |

**文件命名约定**（优先级）：
1. 文件名前缀：`test_unit_*` / `test_int_*` / `test_e2e_*`
2. 文件首行注释标记：`-- @layer unit` / `-- @layer integration` / `-- @layer e2e`
3. 默认：`integration`

### Red-Green-Refactor 决策树

```
1. scaffold_test(module="xxx", layer="unit")
   → 生成测试骨架（Arrange-Act-Assert 三段式）

2. tdd_red(test_name="test_unit_xxx", layer="unit")
   → 预期失败，确认测试有效
   → 区分「预期 assertion fail」（Red 成立）vs「意外 env_error」（Red 不成立，测试写错）

3. 写最少实现代码

4. tdd_green(test_name="test_unit_xxx", layer="unit")
   → 预期通过，确认 Green 成立

5. refactor（重构代码）

6. run_test_batch(layer="unit")
   → 回归测试，确保不破坏
```

### 何时用哪层测试

| 场景 | 推荐层 | 理由 |
|---|---|---|
| 配置校验（天赋、数值表） | unit | 纯数据，秒级反馈 |
| 算法逻辑（伤害计算、属性加成） | unit | 纯函数，易 mock |
| 技能效果（Buff 应用、CD 管理） | integration | 依赖游戏 API |
| 副本流程（多波次、Boss 机制） | e2e | 全流程验证 |
| 任务链（多步骤、状态机） | e2e | 跨系统交互 |

### 可测性约定（纯逻辑与 jass 调用分离）

**问题**：项目代码深度耦合 jass（`CreateUnit`、`GetUnitX` 等），桌面跑不了。

**解决**：
1. **纯逻辑模块**：不直接调 jass，用参数传入依赖（依赖注入）
   ```lua
   -- 可测：纯逻辑
   function TalentSystem.calculate_bonus(talent_config, hero_level)
       return talent_config.base * hero_level
   end

   -- 不可测：耦合 jass
   function TalentSystem.apply_bonus(hero)
       local unit = hero:getUnit()  -- jass 调用
       SetUnitX(unit, 100)          -- jass 调用
   end
   ```

2. **jass mock**：桌面测试时，插件内置 `jass_mock.lua` 自动 stub 高频 jass 函数
   - `CreateUnit`、`GetUnitTypeId`、`SetUnitX` 等返回假 handle
   - 记录调用日志供断言

3. **测试隔离**：unit 层测试不启动游戏，integration/e2e 层才启动游戏

### TDD 工具清单

| 工具 | 说明 |
|---|---|
| `scaffold_test(module, layer, name?)` | 生成 TDD 三段式测试骨架 |
| `tdd_red(test_name, layer)` | 跑测试预期失败，确认测试有效（区分 assertion fail vs env_error） |
| `tdd_green(test_name, layer)` | 跑测试预期通过 |
| `run_unit_test(test_name)` | 桌面秒级跑纯逻辑测试（unit 层） |
| `test_commit(test_name)` | 游戏内跑测试（integration/e2e 层） |
| `run_test_batch(layer="unit")` | 按层批量跑测试 |

### TDD 检查清单

- [ ] `scaffold_test` 生成测试骨架
- [ ] `tdd_red` 确认 Red 成立（failure_type=assertion）
- [ ] 写最少实现
- [ ] `tdd_green` 确认 Green 成立
- [ ] refactor 后 `run_test_batch(layer="unit")` 回归
- [ ] integration/e2e 层用 `test_commit` 验证

---

## 错误分析与调试

### 日志来源

1. **游戏运行日志**（`print` 输出）：位置取决于平台/项目配置（通常在平台安装目录的日志文件夹）。含全部游戏内 `print()`。
2. **测试结果 JSON**（HTTP 上报）：`<plugin_root>/logs/test_results/<test_name>.json`，含 `progress`/`logs`/`assertions`。
3. **结构化日志（v2）**：`logs[]` 字段，游戏侧 `log.info`/`log.error` 拦截上报（带级别/category/traceback）。

### 常见错误

| 错误类型 | 处置 |
|---|---|
| 编译失败 | `compile_only` 看错误 → 修物编/配置 |
| 测试失败 | 按 `failure_type` 查诊断决策树 |
| 游戏卡对话框 | `take_screenshot` → 判读 → `send_key` 继续 |
| HTTP 上报失败 | 检查 8766 端口、游戏内 HTTP 客户端、网络连通 |
| `discover_tests` 找不到测试 | 检查 `test_dir` 配置是否与实际目录一致 |

---

## 操作约束

**⚠️ 严禁 AI 直接操作 Windows 端**：所有编译/启动/截图/按键都通过 MCP 工具代理，不直接 `net start`/访问 Windows 路径/手动启停 War3。

---

## 已知风险与待验证项（诚实标注）

| 项 | 状态 | 处置 |
|---|---|---|
| MCP notification 实时回传渲染 | ⚠️ 未验证 | P0 不依赖它（主依赖 batch 返回报告）；P2 实测，不理想则退化 |
| `/log` 高频 POST 对游戏性能 | ⚠️ 未验证 | 游戏侧节流（同类 0.2s 合并）+ MCP 侧上限防爆；实测后调参 |
| 崩溃日志读取（`Errors\`） | P1 | P0 已做进程消失检测（`failure_type=crash`）；`crash_log` 字段 P1 填充 |
| War3 根目录定位 | ✅ 已验证 | 注册表 `InstallPath` = `D:\war3`（设计文档 4.6） |
| `name 'os' is not defined` 等 os 相关错误 | ℹ️ 已知不修 | war3 对 os 库做了改造适配（见目标项目 CLAUDE.md「内部定制版 Lua 运行时，对 os 库进行了改造适配」），take_screenshot/analyze_screenshot 等路径偶发；不影响核心测试链路（编译→启动→结果回传），无需修复 |

---

## 检查清单

- [ ] `cleanup_all` → `compile_only` 验证编译通过
- [ ] `discover_tests` 确认测试列表
- [ ] `run_test_batch(filter="all")` 跑完，读 summary
- [ ] 失败按 `failure_type` 查决策树 → `codegraph_explore` → 修复
- [ ] `run_test_batch(filter="failed")` 重验（最多 3 轮）
- [ ] 全通过报告完成 / 仍失败报告需人工介入（附证据）
