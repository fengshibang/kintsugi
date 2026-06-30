# win_proxy Windows 服务一键安装 — 设计

> 日期：2026-06-30
> 范围：kintsugi-dev `plugins/war3-tester/` 通用插件（wzns 等所有 war3 项目复用）

## 背景与现状

`win_proxy.py` 是 war3-tester 通用插件的 Windows 侧 TCP 代理（端口 8767）。WSL 通过它转发命令到
Windows 执行（编译地图 / 启动游戏 / 截图等）—— WSL 侧 `WinProxyExecutor` 连 `172.17.176.1:8767`。

现状（wzns `scripts/win_proxy_install.bat`）：用**启动文件夹快捷方式 + UAC 提权**自启。缺点：
- 每次登录弹 UAC，需手动确认
- 依赖用户登录（非真正开机启动，登录前服务没跑）
- `start_win_proxy.bat` / `win_proxy_admin.bat` 硬编码 `D:\maps\wzns\scripts`，不通用
- `uninstall.bat` 端口写死 8765（实际 8767），且 GBK 乱码

## 目标

`win_proxy.py` **一键安装为 Windows 服务**，实现：
- 开机自启（`SERVICE_AUTO_START`，登录前启动）
- 无 UAC 弹窗（服务以服务账户运行）
- 崩溃自动重启
- **win_proxy.py 代码不改一行**

## 非目标

- 不改 `win_proxy.py`（前台 `start_server` 已适配，无需改造）
- 不支持 Linux/Mac（win_proxy 本就是 Windows 侧代理）
- 不做服务管理 GUI（命令行 bat 足够）

## 方案：NSSM 包装

`win_proxy.py` 的 `start_server()` 是**前台运行**（`while True: server.accept()` 主线程阻塞，
子线程处理连接，无 fork/daemon）——完美适配 NSSM。

NSSM（Non-Sucking Service Manager）把任意前台程序包装为 Windows 服务：管理进程生命周期、
失败重启、日志重定向、开机自启。

### 为什么选 NSSM（对比）

| 方案 | 包装层 | 代价 |
|------|--------|------|
| **NSSM** | `nssm.exe`（300KB，免装，自带） | 带个 exe，**win_proxy.py 不改** |
| pywin32 | `pip install pywin32` + 改造 `win_proxy.py` 为服务类 | 不带 exe，但改代码 + 依赖库 |
| srvany + sc.exe | `srvany.exe` + 改注册表 | 无第三方 exe，但配置繁琐易错 |

选 NSSM：最省事、最成熟、不动 win_proxy.py。

## 组件

放 `plugins/war3-tester/`（war3-tester 通用插件）。

### 1. `bin/nssm.exe`
- NSSM 64 位二进制（MIT 许可可分发，~300KB）
- **自带进仓库**（一键安装无网络依赖）
- 64 位（现代 Windows；32 位后续按需补）

### 2. `scripts/install_service.bat`
管理员一键安装。流程：
1. **UAC 自动提权**：检测非管理员 → `powershell Start-Process -Verb RunAs` 重跑自身
2. **定位插件根**：`%~dp0..\`（脚本在 `scripts/`，插件根是上级）—— 不硬编码路径
3. **探测 python.exe**：`where python` → 失败回退 `py -3` launcher；支持 `PYTHON` 环境变量覆盖
   （适配 conda / 虚拟环境）；都没有则报错退出
4. **NSSM 安装与配置**：
   ```bat
   nssm install War3TesterWinProxy "<python.exe>" "win_proxy.py" "start"
   nssm set War3TesterWinProxy AppDirectory "<插件根>"
   nssm set War3TesterWinProxy Start SERVICE_AUTO_START
   nssm set War3TesterWinProxy AppStdout "<插件根>\logs\win_proxy.out.log"
   nssm set War3TesterWinProxy AppStderr "<插件根>\logs\win_proxy.err.log"
   nssm set War3TesterWinProxy AppRotateFiles 1
   nssm set War3TesterWinProxy AppRotateBytes 1048576
   nssm set War3TesterWinProxy AppExit Default Restart
   nssm set War3TesterWinProxy DisplayName "War3 Tester Windows Proxy"
   nssm set War3TesterWinProxy Description "War3 Tester Windows Proxy (TCP 8767, NSSM-managed)"
   ```
5. `nssm start War3TesterWinProxy`
6. 输出结果 + 提示查询命令（`sc query War3TesterWinProxy`）

### 3. `scripts/uninstall_service.bat`
管理员一键卸载。流程：
1. UAC 提权
2. `nssm stop War3TesterWinProxy`（容忍「已停止」错误）
3. `nssm remove War3TesterWinProxy confirm`
4. 输出结果

## 通用性

- 所有路径基于 `%~dp0`（脚本自身位置），**不硬编码** `D:\maps\wzns`
- 任何 war3 项目装 war3-tester 插件即可用同一套脚本

## 服务配置

| 项 | 值 |
|----|-----|
| 服务名 | `War3TesterWinProxy` |
| 显示名 | `War3 Tester Windows Proxy` |
| 启动类型 | 自动（`SERVICE_AUTO_START`） |
| 服务账户 | LocalSystem（NSSM 默认，最高权限，不需密码） |
| 日志 | `<插件根>/logs/win_proxy.{out,err}.log`（轮转 1MB） |
| 失败重启 | `AppExit Default Restart` |

## 与现有 `win_proxy_install.bat`（启动文件夹）关系

- 新 `install_service.bat` 是**真正服务版**（推荐）
- 旧 `win_proxy_install.bat`（启动文件夹 + UAC）保留作「非服务手动启动」备选
- 两者不冲突，但**不要同时跑两个 win_proxy 实例**（端口 8767 冲突）

## 验收标准

1. `install_service.bat` 管理员运行 → 服务 `War3TesterWinProxy` 创建 + 启动 + win_proxy 监听 8767
2. 重启 Windows → 服务自动启动（无需登录）+ win_proxy 监听 8767
3. `taskkill` win_proxy 进程 → 服务自动重启
4. `uninstall_service.bat` 运行 → 服务删除 + 端口 8767 释放
5. wzns 项目用插件的 `install_service.bat` 也能装（通用性验证）

## 测试

- Windows 实跑 `install_service.bat` / `uninstall_service.bat`（用户验证，run 层）
- WSL 侧 `check_connectivity` 验证服务在跑（`test_commit` 能连 8767）
- 重启 Windows 验证开机自启

## 风险与缓解

- **nssm.exe 被杀软误报**：NSSM 偶有此情况。缓解：来源官方 nssm.cc；运行时若被拦记录并提示加白名单。
- **python.exe 探测失败**：conda / 虚拟环境 / py launcher 用户。缓解：`where python` → `py -3` → `PYTHON` 环境变量覆盖三重探测。
