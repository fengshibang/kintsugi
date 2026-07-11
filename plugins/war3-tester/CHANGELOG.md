# Changelog — war3-tester

## 0.6.1 — 2026-07-11

### 新增 / 修复（基于 0.6.0 增量）

- **测试完成后自动关闭测试**：`_run_single_test` 用 try/finally 在所有完成路径（成功/失败/超时/早返回）后自动写 `_test_off.lua`，让用户手动进游戏时 auto-test 模块不加载（零干扰）。下次 `test_commit` 的 `_prepare_test_entry` 自动删除它。
- **修复 `test_commit` 误报 env_error**：`_prepare_test_entry` 推断 test_file 时，对已含 `test_` 前缀的 test_name（如 `test_xinfa_faction`）不再追加，避免生成 `test_test_xinfa_faction.lua` 致 require 失败、test_commit 报 env_error"游戏进程从未启动"。
- **framework.lua 异步修复**：原 0.6.0 framework 为同步版（定义全局 RunAutoTest 覆盖异步测试自带的 → 异步测试被同步引导吞掉、空跑假通过）。改为先 require 测试模块后检测 `_G.RunAutoTest`：自带则异步模式（交 init.lua 在 BattleInitCompleted 调用测试的 RunAutoTest），否则同步模式（TestRunner 包装）。
- **framework.lua module_name 优先 test_name + 异步分支 set_current_test_name**：绕过 _target_test 拼写 bug（双保险）；异步分支补 `set_current_test_name`，使 /error、/log 上报能被 MCP 按 test_name 归类（否则 `unknown` 被 /result 过滤掉，game_errors 丢失）。

### 已知不修

- `name 'os' is not defined` 等 os 相关错误：war3 对 os 库做了改造适配（定制 Lua 运行时，见目标项目 CLAUDE.md「对 os 库进行了改造适配」），take_screenshot/analyze_screenshot 等路径偶发；不影响核心测试链路（编译→启动→结果回传），无需修复。

## 0.6.0 — 2026-07-11

### 新增（v2 无人值守测试循环）

- **`run_test_batch`**：顺序运行多个测试（每测试独立游戏会话，天然隔离），一条指令跑完全部，返回结构化汇总（summary/results/failed + failure_type 分类）。入参：test_filter(all/failed/列表/子串)、stop_on_first_failure、max_retries、timeout_per_test、auto_screenshot_on_failure
- **`discover_tests`**：扫描测试目录，返回测试列表 + 分类(sync/async) + 估算耗时
- **`failure_type` 诊断**：compile_error/crash/timeout/assertion/runtime_error/env_error/unknown，配合进程存活监控（游戏崩溃检测）
- **反馈通道分层**：游戏侧 POST `/progress`（逐步骤进度）、`/log`（拦截 log.info+log.error 的分级日志）、`/error`、`/result`；MCP 侧缓冲回填进结果 JSON（新增 `test_batch_runner.py`）
- **`toggle_test`**：一键开关自动测试模式。关闭时写 `_test_off.lua` + 清测试残留 + 重编译，项目侧 `auto-test/init.lua` 顶部 early-return，手动游戏零干扰（无横幅/无 log 拦截/无自动选难度）；`test_commit` 自动删除 `_test_off.lua` 强制开启
- **`analyze_screenshot`**：多模态视觉模型（VLM）分析游戏截图，返回画面判读文本。模型/URL/key 从环境变量 `VLM_MODEL`/`VLM_BASE_URL`/`VLM_API_KEY` 读（普通文本模型看不了图，必须多模态）
- **`SKILL.md` v2**：无人值守循环（发现→批量跑→分析→修复→重验）+ 诊断决策树 + 结果格式 v2

### 验证
- `run_test_batch`：wzns 项目批量测试全流程跑通
- `toggle_test`：手动游戏 SelectState 选难度间隔 71s（原 auto_select 600ms 抢选），auto-test 模块零加载（框架日志无 AutoTest 输出）
- `analyze_screenshot`：实测多模态 VLM 返回正确画面判读（画面状态/UI 元素/数值）

## 0.5.0 — 2026-07-11

### 修复 / 新增

- **`w2l.exe` 按「项目目录相对位置」查找**：每个地图项目自带 `w3x2lni/w2l.exe`，故查找以项目目录为最高优先级（`<项目>/w3x2lni/w2l.exe`、`<项目>/tools/w3x2lni/w2l.exe`），不再只在插件目录下找
- **编译时按实际项目目录动态查找**：两个 `compile` 方法（win_proxy 版 / 本地版）改用编译时传入的 `source_dir` 调用 `find_w2l_exe`，Config 初始化时的 `w2l_path` 仅作兜底——修掉「初始化算死、与真实项目目录脱节」导致永远找不到项目自带 w2l.exe 的根因
- **`.env` 文件支持（纯标准库，零依赖）**：项目根目录 `.env`（优先）+ 插件目录 `.env`（兜底），启动时注入 `os.environ`，不覆盖系统变量。支持 `#` 注释、空行、引号、`export` 前缀
- **`validate()` 把 `w2l` 未找到从 error 降为 warning**（编译时按项目目录动态查找，初始化时找不到不等于不能编译）
- 路径跨平台自适应：`find_w2l_exe` 经 `_resolve_path` 归一化 Windows/WSL 路径

### 验证
- 真实项目命中：`D:\maps\MoeHero` / `dotadm` / `cszhg` 均自动找到各自 `tools/w3x2lni/w2l.exe`
- `.env` 行为：注入 / 系统变量不覆盖 / 项目级优先 / 无 `.env` 不报错，全通过

## 0.4.1 — 2026-07-11

修复 **w2l.exe 找不到导致地图编译失败**：原查找只在插件自身目录的固定路径下找，但 w2l.exe 实际在用户的地图项目目录里。

### 根因
`_find_w2l_exe` 只检查 `<插件目录>/tools/w3x2lni/w2l.exe` 等固定路径——插件目录里根本没有，用户的 w3x2lni 通常解压在地图项目内 → 永远搜不到 → 编译报「未找到 w2l.exe」。

### 修复
- **`_find_w2l_exe` 改三段式查找**：① 环境变量 `W2L_PATH` ② 固定候选路径（`project_root` / 插件目录 / `compile_source_dir` 下的 `tools/w3x2lni/`、`w3x2lni/`）③ **项目内递归搜索兜底**
- **新增 `_search_w2l_in_project`**：DFS 限深 6 层，跳过 `node_modules`/`.git`/`logs`/`__pycache__` 等噪声目录，匹配 `w2l.exe` 与 `w2l`
- **调用时机后移**：`_find_w2l_exe()` 从 `_load_config` 第 3 步挪到 `compile_source_dir` 解析之后，确保递归搜的是真实项目目录
- 同步更新 `validate()` 与 `env_bridge.py` 编译失败提示，告知已搜范围与放置建议
- 顺手清理 `_find_w2l_exe` 里 `is_wsl`/非 WSL 两分支完全相同的冗余

### 验证
- 静态：`py_compile` config.py / env_bridge.py 全过
- 行为（临时目录）：浅层命中 ✅、跳过 `node_modules` ✅、深度 7 超 `max_depth=6` 不命中而放宽到 8 命中 ✅、非约定子目录靠递归兜底命中 ✅、`W2L_PATH` 最高优先级 ✅

## 0.4.0 — 2026-07-10

支持 **Windows 原生**下 MCP server 可靠启动（不再被 Microsoft Store 别名桩卡住）；原生 Windows 无需 win_proxy。

### 根因
`.mcp.json` 用 `"command": "python3"`。Windows 原生的 `python3` 通常是 Microsoft Store 别名桩（App Execution Alias），不同启动上下文行为不一致（可能弹 Store / 异常退出码），MCP server 起不来 = 整个插件不可用。

### 修复
- **新增跨平台启动 wrapper `scripts/start_mcp.js`**：`.mcp.json` 是静态 JSON，无法内联探测逻辑，故用 node wrapper（node 是 Claude Code 既有依赖，用户无需额外装）解析 Python 解释器
- **`.mcp.json` 改 `command: "node"`**，args 指向 `${CLAUDE_PLUGIN_ROOT}/scripts/start_mcp.js`
- **解释器解析顺序**：`PYTHON_BIN` 覆盖 → `python3`（跳过 WindowsApps）→ `python`（跳过 WindowsApps）→ `py` → 兜底；Linux/macOS 直接用真实 `python3`

### 实施中修复的 2 个 Store 别名桩避坑 bug（师徒试错沉淀）
- **PATH 探测只取第一行**：`where python` 第一行常是 Store 桩、真实 python 在后面 → 改为遍历全部候选行、跳过 WindowsApps，取第一个真实路径
- **完整路径降级回命令名**：`resolvePython` 返回命令名（`'python'`）而非完整路径 → `spawn` 重新按 PATH 查找会再中 Store 桩 → 改为完整路径一路传递到 spawn（`sys.executable` 实测确认用真实解释器）

### 验证
- 静态：`py_compile` 全过、`.mcp.json` 合法、`node --version` 在 PATH（claude CLI 经 npm 装必有 node）
- 逻辑：师傅独立复刻 resolvePython+spawn，`sys.executable = C:\Python313\python.exe`（真身，非 Store 桩）
- 运行：wrapper→spawn→真实 python 链路通（MCP server 冒烟、8766 端口开）；完整 `/mcp` 握手待用户实跑

### 已沉淀
- eval case `xplat-python-001`（2 条 RED 硬线：遍历跳过 Store + 完整路径传递）

## 0.3.1 — 2026-06-30

修复 **WSL 插件缓存路径导致服务无法启动**（Claude Code 把插件装进 WSL 时）。

### 根因
Claude Code 可能把插件缓存在 WSL（`\\wsl.localhost\Ubuntu\...`）。原 install.bat
直接用插件路径装服务 → `BINARY_PATH_NAME` 指向 WSL UNC 路径 → Windows SCM 无法加载
（"网络找不到"）→ 服务启动失败被 DISABLED。

### 修复
- **install_service.bat 改为「拷到本地再装」**：把 `nssm.exe` + `win_proxy.py` 拷到
  `%ProgramData%\War3Tester\`（Windows 本地，LocalSystem 可访问），服务指向本地路径。
  这样无论插件缓存在 WSL 还是本地盘，服务都能正常启动。
- **uninstall_service.bat 用本地 nssm.exe**：即使插件缓存已删，仍可卸载（清本地目录）。

## 0.3.0 — 2026-06-30

新增 **win_proxy Windows 服务一键安装**（开机自启、无 UAC、崩溃自动重启）。

### 新增
- `bin/nssm.exe`：NSSM 2.24 win64（自带，免网络）
- `scripts/install_service.bat`：UAC 提权 + python 探测 + NSSM 装服务 `War3TesterWinProxy`
  （`SERVICE_AUTO_START` + `AppExit Restart` + 日志轮转，路径基于 `%~dp0` 通用）
- `scripts/uninstall_service.bat`：一键卸载（NSSM 缺失时 `sc` 兜底）
- README「Windows 服务一键安装」章节

### 实施中修复的 4 个 bat/服务化 bug
- **install.bat UTF-8 乱码闪退**：UTF-8 + 中文 echo，cmd GBK 解析错位 → 命令切碎。修复：bat 纯 ASCII（Windows bat 铁律）
- **服务 EXIT_CODE 1066**：nssm install 参数 `"win_proxy.py start"` 合并成一串 → python 找不到脚本。修复：脚本名与参数拆分 + 显式 `AppParameters`
- **服务 EXIT_CODE 3**：`where python` 命中 WindowsApps Store 别名（LocalSystem 跑不了）。修复：`findstr` 跳过 `WindowsApps` 路径，取真 python
- **端口冲突**：旧 `WinProxy.lnk`（启动文件夹）占 8767。需手动清理（README/文档说明）

## 0.2.0 — 2026-06-30

首个**全链路实跑验证通过**的可用版本（test_skill_a00d 测试通过，端到端 29.6s 自动）。

### 修复（实跑发现的 3 个对接 bug）
- **framework.lua**：`require('_target_test')` 裸名 → 完整点分路径 `script.src.auto-test._target_test`
  （wzns 等点分 require 框架下裸名找不到模块，致 `__auto_test_mode=false` 测试被静默跳过）
- **http_receiver `/result`**：严格 `request.json` → 容错 `get_json(force=True, silent=True)` + `get_data`+`json.loads` 兜底
  （对接非标准 HTTP 客户端时 strict 模式判 400）
- **mcp_server `test_module`**：含前缀完整路径 + framework.lua 又拼 prefix → 双重前缀模块找不到；
  改为写不含前缀的 base，由引导脚本拼一次 prefix

### 新增
- eval case `war3-plugin-bridge-001`（沉淀上述通用插件对接真实项目的崩溃级坑）
- 设计 spec：win_proxy Windows 服务一键安装（NSSM 方案，待实现）—— 见 `docs/superpowers/specs/`

## 0.1.0 — 2026-06-29
- 初始版本：通用 MCP 层（server/）+ war3-auto-test skill + wzns 框架适配器范例
- marketplace 双注册（mentor-kit + war3-tester）
