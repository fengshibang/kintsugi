# Changelog — war3-tester

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
