# war3-tester

> **通用 War3 地图自动测试 MCP 插件** — 编译地图、启动游戏、注入测试脚本、接收游戏内 HTTP 回传结果。不限 Lua 框架，最小契约装上即用。

---

## 是什么

一个 **Claude Code 插件**，提供 stdio MCP server + skill + command，让任何 War3 自定义地图项目都能实现：

```
修改代码 → 编译地图 → 启动游戏 → 注入测试 → HTTP 回传结果 → 输出报告
```

**通用性**：不绑定任何 Lua 框架（ECS / OOP / 纯 JASS 均可）。插件与目标项目之间只约定一个最小契约：

1. 测试文件定义全局函数 `RunAutoTest()`
2. 测试文件通过 HTTP POST 将结果发到 `<host>:8766/result`

## 安装

```bash
/plugin install war3-tester
```

安装后 Claude Code 自动读取 `.mcp.json`，启动 stdio MCP server。首次使用会弹出逐服务器审批。

## 配置

在**目标项目根目录**创建 `config.json`：

```json
{
  "test": {
    "test_dir": "auto-test",
    "test_module_prefix": ""
  },
  "compile": {
    "source_dir": ".",
    "output_path": ".",
    "output_name": "your-map.w3x"
  },
  "ydwe_path": "D:\\path\\to\\YDWE",
  "kkwe_path": "D:\\path\\to\\KKWE"
}
```

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `test.test_dir` | `"auto-test"` | 测试文件所在目录名（相对于 `source_dir/`） |
| `test.test_module_prefix` | `""` | require 时的模块前缀（空串 = 同目录加载） |
| `compile.output_name` | `"map.w3x"` | 编译输出的地图文件名 |
| `compile.source_dir` | `"."` | 源码根目录（支持 `${workspaceRoot}`） |
| `ydwe_path` / `kkwe_path` | 自动搜索 | 游戏平台路径（环境变量 `YDWE_PATH` / `KKWE_PATH` 优先） |

路径查找优先级：**环境变量 > config.json > 默认搜索路径**。

## WSL 部署 win_proxy

WSL 用户需在 **Windows 侧**启动 `win_proxy.py`（纯 TCP 转发器，无框架耦合）：

```powershell
# Windows CMD/PowerShell
cd <plugin_root>
python win_proxy.py start
```

停止：
```powershell
python win_proxy.py stop
```

- 监听 `0.0.0.0:8767`
- 转发命令：w2l 编译、启动 KKWE/YDWE、taskkill、send_key 等
- 原生 Windows 用户无需此步骤（直接 subprocess）

## Windows 服务一键安装（开机自启）

把 `win_proxy.py` 装成 Windows 服务，**开机自启、无 UAC 弹窗、崩溃自动重启**。
适合长期使用（替代上面手动 `python win_proxy.py start`）。

### 安装

1. 以管理员身份双击 `scripts/install_service.bat`（脚本会自动 UAC 提权）
2. 脚本自动：探测 Python → 用 NSSM 创建服务 `War3TesterWinProxy` → 启动
3. 验证：`sc query War3TesterWinProxy`（STATE 应为 `RUNNING`）

### 卸载

以管理员身份双击 `scripts/uninstall_service.bat`。

### 说明

- 服务名 `War3TesterWinProxy`，启动类型「自动」，账户 LocalSystem
- **文件部署**：`install_service.bat` 自动把 `nssm.exe` + `win_proxy.py` 拷到
  `%ProgramData%\War3Tester\`（Windows 本地目录，服务可访问），服务指向本地路径。
  这样即使 Claude Code 把插件缓存在 WSL（`\\wsl.localhost\...`），服务也能正常启动
  （Windows SCM 不能从 WSL/UNC 路径加载 exe）
- 日志：`%ProgramData%\War3Tester\logs\win_proxy.{out,err}.log`（1MB 轮转）
- 崩溃自动重启（NSSM `AppExit Restart`）
- `bin/nssm.exe` 自带（NSSM 2.24，MIT 许可可分发）
- Python 探测顺序：`PYTHON` 环境变量 → `where python`（跳过 WindowsApps Store 别名）→ `py -3`

> **卸载会清理**：`uninstall_service.bat` 删服务 + 删 `%ProgramData%\War3Tester\` 本地目录。

## 最小契约

### 测试文件

在 `<source_dir>/<test_dir>/test_example.lua`：

```lua
function RunAutoTest()
    -- 1. 执行测试逻辑
    -- 2. HTTP POST 结果到 http://<host>:8766/result
end
```

### HTTP 上报格式

```
POST /result
Content-Type: application/json

{
  "test_name": "test_example",
  "success": true|false,
  "details": "详细说明",
  "cases": [
    {"name": "用例1", "success": true, "message": "..."}
  ]
}
```

### HTTP 上报 API

> ⚠️ war3 1.27 lua 的 HTTP 客户端实现因项目而异，需从目标项目提取或运行层验证。插件不强制具体 API。

## MCP 工具

| 工具 | 说明 |
|------|------|
| `compile_map` / `compile_only` | 编译地图（同步等待 w2l.exe） |
| `run_game` / `launch_only` | 启动游戏（异步） |
| `stop_game` | 关闭 War3 进程 |
| `test_commit` | **核心**：预清理 → 编译 → 启动 → 等待 HTTP 结果 → 后清理 |
| `take_screenshot` | 截取游戏窗口 |
| `send_key` | 发送键盘事件 |
| `cleanup_all` | 关闭所有资源 |
| `stop_http_server` | 仅关闭 HTTP 测试服务器 |

## 已知风险

| 风险 | 缓解 |
|------|------|
| war3 lua HTTP 上报 API 因项目而异 | 契约最小化 + 文档化参考方向 + 运行层验证，不臆造 |
| 模块加载机制（`require` 路径）因项目而异 | `test_module_prefix` 可配置 + `examples/` 范例 |
| [issue #41137](https://github.com/anthropics/claude-code/issues/41137) plugin install/update 偶发擦除 mcpServers | 若工具消失，检查 `.mcp.json` 是否被改写，`/mcp` 重连或重启 Claude Code |
| w2l.exe / KKWE / YDWE 路径因机器而异 | 全部走 config（环境变量 > 配置文件 > 搜索），无硬编码 |

## 插件级 .mcp.json 格式备注

插件根目录 `.mcp.json` 使用**顶层 server map** 格式（无 `mcpServers` 包裹）：

```json
{
  "war3-tester": {
    "command": "node",
    "args": ["${CLAUDE_PLUGIN_ROOT}/scripts/start_mcp.js"],
    "env": { "PYTHONUTF8": "1" }
  }
}
```

> 这与**项目级** `.mcp.json`（需 `mcpServers` 包裹）不同。`${CLAUDE_PLUGIN_ROOT}` 由 Claude Code 自动替换为插件安装目录，保证可移植。
>
> **MCP server 经 Node.js wrapper 启动**（`scripts/start_mcp.js`）。
> **node 是 Claude Code 既有依赖**（claude CLI 经 npm 全局安装，装 claude 就有 node），用户无需额外安装。
>
> wrapper 负责跨平台解析 Python 解释器：
> - Windows 原生：`python3` 常是 Microsoft Store 别名桩（不可靠），wrapper 遍历 `where` 输出的所有候选，跳过 WindowsApps 路径，选中第一个真实解释器；回退到 `python` 或 `py` 启动器
> - Linux/macOS：`python3` 是真实解释器，直接使用
> - 可用 `PYTHON_BIN` 环境变量强制覆盖
>
> ⚠️ 若格式有歧义，用 `/mcp` 命令实测确认。

## 目录结构

```
plugins/war3-tester/
├── .claude-plugin/plugin.json     # 插件清单
├── .mcp.json                      # MCP server 声明
├── scripts/
│   └── start_mcp.js               # 跨平台 Python 解释器解析 + 启动
├── server/                        # 通用 MCP 层（Python stdio JSON-RPC）
│   ├── mcp_server.py              # 入口
│   ├── config.py                  # 配置管理
│   ├── env_bridge.py              # 环境桥（WSL/Windows）
│   ├── http_receiver.py           # 8766 接收游戏回传
│   ├── logger.py                  # 日志
│   └── lua_bootstrap.lua          # 通用测试引导模板
├── win_proxy.py                   # Windows TCP 桥（WSL 模式部署）
├── skills/war3-auto-test/SKILL.md # 通用 skill 文档
├── commands/war3-test.md          # /war3-test 入口命令
├── examples/                      # 框架适配器范例
├── README.md                      # 本文件
└── requirements.txt               # Python 依赖（仅标准库）
```

## 许可

MIT
