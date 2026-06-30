# Changelog — war3-tester

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
