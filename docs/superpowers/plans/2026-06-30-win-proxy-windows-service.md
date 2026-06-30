# win_proxy Windows 服务一键安装 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: 用 superpowers:executing-plans 逐任务实现。Steps 用 checkbox（`- [ ]`）跟踪。

**Goal:** 把 `win_proxy.py` 用 NSSM 包装成 Windows 服务，提供 `install_service.bat` / `uninstall_service.bat` 一键安装卸载，开机自启、无 UAC、崩溃重启。

**Architecture:** NSSM（自带 `bin/nssm.exe`）把前台运行的 `python win_proxy.py start` 包装为服务 `War3TesterWinProxy`（`SERVICE_AUTO_START` + `AppExit Restart` + 日志轮转）。win_proxy.py 不改一行。两个 bat 脚本（UAC 自动提权 + python 三重探测 + 路径基于 `%~dp0` 通用）。

**Tech Stack:** Windows batch + NSSM 2.24 + Python（探测）。

## Global Constraints（逐字来自 spec）

- `win_proxy.py` **不改一行**
- 所有路径基于 `%~dp0`，**不硬编码** `D:\maps\wzns`
- 服务名 `War3TesterWinProxy`，显示名 `War3 Tester Windows Proxy`
- 启动类型 `SERVICE_AUTO_START`，账户 LocalSystem
- python.exe 三重探测：`PYTHON` 环境变量 → `where python` → `py -3`
- `nssm.exe` 自带进 `bin/`（一键安装无网络依赖）
- 日志 `<插件根>/logs/win_proxy.{out,err}.log`，轮转 1MB
- 失败重启 `AppExit Default Restart`

## 文件结构

| 文件 | 责任 |
|------|------|
| Create: `plugins/war3-tester/bin/nssm.exe` | NSSM 64 位二进制（服务包装器） |
| Create: `plugins/war3-tester/scripts/install_service.bat` | 一键安装服务（UAC + python 探测 + nssm 命令） |
| Create: `plugins/war3-tester/scripts/uninstall_service.bat` | 一键卸载服务 |
| Modify: `plugins/war3-tester/README.md` | 补「服务安装」使用说明 |
| Check: `plugins/war3-tester/.gitignore`（继承根） | 确保 `bin/nssm.exe` 不被忽略（默认不忽略 .exe，无需改） |

> bat 脚本无单元测试框架，TDD 调整为：**写文件 → 静态验证（路径/逻辑 review）→ 实跑验收（用户 Windows 跑）**。实跑验收属 run 层，待用户回填。

---

### Task 1: 获取 nssm.exe 放 bin/

**Files:**
- Create: `plugins/war3-tester/bin/nssm.exe`

**说明：** nssm.exe 是 Windows 二进制，WSL/Linux 环境无法编译，只能下载。当前 nssm.cc 503、github mirror timeout（网络/源问题）。执行时按下列优先级获取；若全失败，**报告阻塞等用户手动提供**（不自行绕过网络问题，按基础设施准则）。

- [ ] **Step 1: 尝试下载 nssm-2.24.zip**

```bash
cd /tmp
curl -sL -o nssm-2.24.zip "https://nssm.cc/release/nssm-2.24.zip" && echo OK || echo FAIL
# 备选源（nssm.cc 不可用时）：
# curl -sL -o nssm-2.24.zip "https://github.com/kirillovm/nssm/releases/download/v2.24/nssm-2.24.zip"
```

- [ ] **Step 2: 解压取 win64/nssm.exe**

```bash
mkdir -p /tmp/nssm_extract && cd /tmp/nssm_extract
unzip -o /tmp/nssm-2.24.zip
ls nssm-2.24/win64/nssm.exe   # 确认存在
```

- [ ] **Step 3: 放到插件 bin/**

```bash
mkdir -p /mnt/d/kintsugi-dev/plugins/war3-tester/bin
cp /tmp/nssm_extract/nssm-2.24/win64/nssm.exe /mnt/d/kintsugi-dev/plugins/war3-tester/bin/nssm.exe
ls -la /mnt/d/kintsugi-dev/plugins/war3-tester/bin/nssm.exe  # ~330KB
```

- [ ] **Step 4: 若下载全失败 → 报告阻塞**

输出（不自行修复网络）：
```
❌ [nssm.exe 下载] 失败
   nssm.cc: 503 Service Temporarily Unavailable
   github mirror: 连接超时
   影响：Task 1 无法完成，后续 bat 脚本无 nssm.exe 可用
   建议：① 稍后 nssm.cc 恢复重试；② 用户手动从 https://nssm.cc/download 下载
        nssm-2.24.zip，解压取 win64\nssm.exe 放 plugins/war3-tester/bin\
   等待指示
```

---

### Task 2: 写 install_service.bat

**Files:**
- Create: `plugins/war3-tester/scripts/install_service.bat`

**Interfaces:**
- Consumes: `bin/nssm.exe`（Task 1）、`win_proxy.py`、python.exe（探测）
- Produces: Windows 服务 `War3TesterWinProxy`

- [ ] **Step 1: 写 install_service.bat（完整内容）**

Create `plugins/war3-tester/scripts/install_service.bat`:

```bat
@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul

:: ========================================
:: War3Tester WinProxy - Windows Service Installer (NSSM)
:: 一键安装 win_proxy.py 为 Windows 服务（开机自启/无UAC/崩溃重启）
:: ========================================

:: === UAC 自动提权 ===
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] 需要管理员权限，正在提权...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

:: === 定位插件根（脚本在 scripts/，上级是插件根）===
set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
for %%I in ("%SCRIPT_DIR%\..") do set "PLUGIN_ROOT=%%~fI"
set "NSSM=%PLUGIN_ROOT%\bin\nssm.exe"
set "WIN_PROXY=%PLUGIN_ROOT%\win_proxy.py"
set "LOGS_DIR=%PLUGIN_ROOT%\logs"
set "SERVICE_NAME=War3TesterWinProxy"

:: === 检查 nssm.exe ===
if not exist "%NSSM%" (
    echo [ERROR] 未找到 nssm.exe: %NSSM%
    echo         请从 https://nssm.cc/download 下载 nssm-2.24.zip，
    echo         解压取 win64\nssm.exe 放到 %PLUGIN_ROOT%\bin\
    pause
    exit /b 1
)

:: === 检查 win_proxy.py ===
if not exist "%WIN_PROXY%" (
    echo [ERROR] 未找到 win_proxy.py: %WIN_PROXY%
    pause
    exit /b 1
)

:: === 探测 python.exe（PYTHON 环境变量 → where python → py -3）===
set "PYTHON_EXE=%PYTHON%"
if not defined PYTHON_EXE (
    where python >nul 2>&1
    if !errorlevel! equ 0 (
        for /f "delims=" %%P in ('where python') do set "PYTHON_EXE=%%P"
    ) else (
        where py >nul 2>&1
        if !errorlevel! equ 0 (
            for /f "delims=" %%P in ('py -3 -c "import sys; print(sys.executable)"') do set "PYTHON_EXE=%%P"
        )
    )
)
if not defined PYTHON_EXE (
    echo [ERROR] 未找到 python.exe。请装 Python，或设 PYTHON 环境变量指向 python.exe
    pause
    exit /b 1
)
echo [INFO] Python: %PYTHON_EXE%

:: === 创建日志目录 ===
if not exist "%LOGS_DIR%" mkdir "%LOGS_DIR%"

:: === 若服务已存在，先移除 ===
sc query %SERVICE_NAME% >nul 2>&1
if %errorlevel% equ 0 (
    echo [INFO] 服务已存在，先停止并移除旧服务...
    "%NSSM%" stop %SERVICE_NAME% >nul 2>&1
    "%NSSM%" remove %SERVICE_NAME% confirm >nul 2>&1
)

:: === NSSM 安装与配置 ===
echo [INFO] 安装服务 %SERVICE_NAME% ...
"%NSSM%" install %SERVICE_NAME% "%PYTHON_EXE%" "win_proxy.py start"
"%NSSM%" set %SERVICE_NAME% AppDirectory "%PLUGIN_ROOT%"
"%NSSM%" set %SERVICE_NAME% Start SERVICE_AUTO_START
"%NSSM%" set %SERVICE_NAME% AppStdout "%LOGS_DIR%\win_proxy.out.log"
"%NSSM%" set %SERVICE_NAME% AppStderr "%LOGS_DIR%\win_proxy.err.log"
"%NSSM%" set %SERVICE_NAME% AppRotateFiles 1
"%NSSM%" set %SERVICE_NAME% AppRotateBytes 1048576
"%NSSM%" set %SERVICE_NAME% AppExit Default Restart
"%NSSM%" set %SERVICE_NAME% DisplayName "War3 Tester Windows Proxy"
"%NSSM%" set %SERVICE_NAME% Description "War3 Tester Windows Proxy (TCP 8767, NSSM-managed)"

:: === 启动 ===
echo [INFO] 启动服务...
"%NSSM%" start %SERVICE_NAME%

:: === 验证 ===
timeout /t 2 >nul
sc query %SERVICE_NAME% | findstr "STATE"
echo.
echo [OK] 服务安装完成: %SERVICE_NAME%
echo      查询状态: sc query %SERVICE_NAME%
echo      启动/停止: nssm start/stop %SERVICE_NAME%
echo      卸载: 运行 uninstall_service.bat
echo.
pause
```

- [ ] **Step 2: 静态验证（路径/逻辑 review）**

检查项：
- `%~dp0` 定位插件根，无硬编码 `D:\maps\wzns` ✓
- python 三重探测：`PYTHON` → `where python` → `py -3` ✓
- 服务配置覆盖 spec 全部项（Start/AppStdout/AppRotateFiles/AppExit/DisplayName/Description）✓
- 服务已存在时先移除（幂等）✓
- 无 `start_win_proxy.bat` 的 `chcp` 乱码问题（`chcp 65001` 已设）✓

- [ ] **Step 3: 实跑验收（用户 Windows run 层）**

用户管理员双击 `install_service.bat`：
- 期望：服务 `War3TesterWinProxy` 创建 + STATE=RUNNING + win_proxy 监听 8767
- 回填：`sc query War3TesterWinProxy` 输出 + `netstat -ano | findstr :8767`

---

### Task 3: 写 uninstall_service.bat

**Files:**
- Create: `plugins/war3-tester/scripts/uninstall_service.bat`

**Interfaces:**
- Consumes: `bin/nssm.exe`（缺失时用 `sc` 兜底）、服务 `War3TesterWinProxy`

- [ ] **Step 1: 写 uninstall_service.bat（完整内容）**

Create `plugins/war3-tester/scripts/uninstall_service.bat`:

```bat
@echo off
setlocal
chcp 65001 >nul

:: ========================================
:: War3Tester WinProxy - Windows Service Uninstaller
:: 一键卸载 win_proxy 服务
:: ========================================

:: === UAC 自动提权 ===
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] 需要管理员权限，正在提权...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
for %%I in ("%SCRIPT_DIR%\..") do set "PLUGIN_ROOT=%%~fI"
set "NSSM=%PLUGIN_ROOT%\bin\nssm.exe"
set "SERVICE_NAME=War3TesterWinProxy"

sc query %SERVICE_NAME% >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] 服务 %SERVICE_NAME% 不存在，无需卸载
    pause
    exit /b 0
)

echo [INFO] 停止服务...
if exist "%NSSM%" (
    "%NSSM%" stop %SERVICE_NAME% >nul 2>&1
    echo [INFO] 移除服务...
    "%NSSM%" remove %SERVICE_NAME% confirm
) else (
    :: nssm.exe 缺失，用 sc 兜底
    sc stop %SERVICE_NAME% >nul 2>&1
    sc delete %SERVICE_NAME%
)

echo.
echo [OK] 服务 %SERVICE_NAME% 已卸载
echo.
pause
```

- [ ] **Step 2: 静态验证**

- nssm.exe 缺失时 `sc` 兜底（容错）✓
- 服务不存在时直接退出（幂等）✓
- 路径基于 `%~dp0` ✓

- [ ] **Step 3: 实跑验收（用户 Windows run 层）**

用户管理员双击 `uninstall_service.bat`：
- 期望：服务删除 + 端口 8767 释放
- 回填：`sc query War3TesterWinProxy`（应「指定的服务未安装」）+ `netstat -ano | findstr :8767`（空）

---

### Task 4: README 补服务安装说明 + 提交

**Files:**
- Modify: `plugins/war3-tester/README.md`

- [ ] **Step 1: 读 README 现有结构，定位「安装/使用」章节**

Run: `grep -n "^##\|安装\|win_proxy\|服务" plugins/war3-tester/README.md`

- [ ] **Step 2: 在合适位置追加「Windows 服务一键安装」章节**

追加内容（Markdown）：

```markdown
## Windows 服务一键安装（开机自启）

把 `win_proxy.py` 装成 Windows 服务，开机自启、无 UAC 弹窗、崩溃自动重启。
适合长期使用（替代手动 `python win_proxy.py start`）。

### 安装

1. 以管理员身份双击 `scripts/install_service.bat`（脚本会自动 UAC 提权）
2. 脚本自动：探测 Python → 用 NSSM 创建服务 `War3TesterWinProxy` → 启动
3. 验证：`sc query War3TesterWinProxy`（STATE 应为 RUNNING）

### 卸载

以管理员身份双击 `scripts/uninstall_service.bat`。

### 说明

- 服务名 `War3TesterWinProxy`，启动类型「自动」，账户 LocalSystem
- 日志：`logs/win_proxy.out.log` / `win_proxy.err.log`（1MB 轮转）
- 崩溃自动重启（NSSM `AppExit Restart`）
- `bin/nssm.exe` 自带（NSSM 2.24，MIT 许可可分发）
- Python 探测顺序：`PYTHON` 环境变量 → `where python` → `py -3`
```

- [ ] **Step 3: 提交**

```bash
cd /mnt/d/kintsugi-dev
git add plugins/war3-tester/bin/nssm.exe \
        plugins/war3-tester/scripts/install_service.bat \
        plugins/war3-tester/scripts/uninstall_service.bat \
        plugins/war3-tester/README.md
git commit -m "feat(war3-tester): win_proxy Windows 服务一键安装（NSSM）

- bin/nssm.exe: NSSM 2.24 64位（自带，免网络）
- scripts/install_service.bat: UAC提权 + python三重探测 + nssm配置服务
  开机自启/无UAC/崩溃重启/日志轮转，路径基于%dp0通用
- scripts/uninstall_service.bat: 一键卸载（nssm缺失时sc兜底）
- README: 补「Windows 服务一键安装」章节"
```

---

## Self-Review

**1. Spec coverage:** spec 的组件（bin/nssm.exe / install_service.bat / uninstall_service.bat）→ Task 1/2/3 ✓；通用性（路径 %~dp0、python 三重探测）→ Task 2 ✓；服务配置项（Start/AppStdout/AppRotateFiles/AppExit/DisplayName/Description）→ Task 2 nssm 命令 ✓；验收 5 条（装/开机自启/崩溃重启/卸载/通用）→ Task 2/3 实跑 + 用户重启验证 ✓；README 说明 → Task 4 ✓。

**2. Placeholder scan:** 无 TBD/TODO；bat 脚本完整代码已内联；nssm 下载失败的处理路径明确（报告阻塞）。

**3. Type consistency:** 服务名 `War3TesterWinProxy` 在 install/uninstall/README 一致；路径变量 `PLUGIN_ROOT`/`NSSM`/`SERVICE_NAME` 在两 bat 一致。

**已知阻塞：** nssm.exe 下载（nssm.cc 503 / github timeout）。Task 1 执行时若全失败，按基础设施准则报告等用户，不自行绕过。
