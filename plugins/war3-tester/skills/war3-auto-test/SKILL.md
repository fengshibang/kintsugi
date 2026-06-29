---
name: war3-auto-test
version: 1.0.0
description: "通用 War3 地图自动测试：编译 → 启动 → 注入测试 → HTTP 回传结果。最小契约（RunAutoTest + POST 8766），不限 Lua 框架。"
---

# War3 Auto Test - 通用地图自动测试

> **触发方式**：用户输入 `/war3-auto-test` 或 agent 通过 Skill 工具调度
> **核心原则**：测试由用户按需触发，AI 不自动运行测试循环。所有 Windows 端操作通过 MCP 工具代理。

---

## 最小测试契约

插件与目标项目之间只约定一个最小契约，**不假设任何 Lua 框架**：

### 1. 测试文件结构

目标项目在 `<source_dir>/<test_dir>/` 下提供测试文件（`test_dir` 可配置，默认 `auto-test`）：

```lua
-- <test_dir>/<test_file>.lua
function RunAutoTest()
    -- 执行测试逻辑
    -- 通过 HTTP POST 上报结果（见下文）
end
```

### 2. HTTP 结果上报

测试文件须通过 **HTTP POST** 将结果发送到 `<插件 host>:8766/result`：

```
POST /result
Content-Type: application/json

{
  "test_name": "<测试名称>",
  "success": true|false,
  "details": "<详细说明>",
  "cases": [
    {"name": "<用例名>", "success": true|false, "message": "..."},
    ...
  ]
}
```

### 3. 插件引导机制

插件在编译前自动写入两个文件到 `<source_dir>/<test_dir>/`：

- `_target_test.lua`（配置）：
  ```lua
  return { test_name='<name>', test_file='<test_file>.lua' }
  ```

- `run_auto_test.lua`（通用引导，即 `lua_bootstrap.lua` 内容）：
  - 读取 `_target_test.lua` 配置
  - 按 `test_module_prefix` 加载测试文件
  - 游戏启动后调用 `RunAutoTest()`
  - **严禁出现**：任何项目专属 API（如特定框架的 ECS 类、自定义测试运行器、框架目录路径等）

---

## 配置项说明

### 核心配置（`config.json`）

```json
{
  "test": {
    "test_dir": "auto-test",
    "test_module_prefix": "",
    "test_bootstrap_template": ""
  },
  "compile": {
    "source_dir": ".",
    "output_path": ".",
    "output_name": "map.w3x"
  },
  "ydwe_path": "D:\\war3\\YDWE",
  "kkwe_path": "D:\\KKWE",
  "w2l_path": "tools\\w3x2lni\\w2l.exe"
}
```

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `test.test_dir` | `"auto-test"` | 测试文件所在目录名（相对于 `source_dir/`） |
| `test.test_module_prefix` | `""` | require 时的模块前缀。<br>**空串** = 同目录加载（引导脚本与测试文件同目录）<br>**非空** = `prefix..name` 走 require（如 `'your.framework.prefix.'`） |
| `test.test_bootstrap_template` | `""` | 自定义引导模板路径（支持 `${workspaceRoot}`）。<br>**空串** = 使用通用 `server/lua_bootstrap.lua`（默认行为）<br>**非空** = 用 `_resolve_path` 解析后读取该文件作为 `run_auto_test.lua` 内容；文件不存在时 fallback 到通用模板 |
| `compile.output_name` | `"map.w3x"` | 编译输出的地图文件名 |
| `compile.source_dir` | `"."` | 源码根目录（支持 `${workspaceRoot}`） |
| `ydwe_path` / `kkwe_path` | 自动搜索 | 游戏平台路径（环境变量 `YDWE_PATH` / `KKWE_PATH` 优先） |

### 测试模块加载机制

`test_module_prefix` 控制加载方式：

| 值 | 加载方式 | 适用场景 |
|----|----------|----------|
| `""` (空串) | 引导脚本与测试文件同目录，直接 `require` 相对名 | 通用项目（无框架打包结构） |
| `"your.framework.prefix."` | `require('your.framework.prefix.' .. name)` | 使用框架打包结构的项目 |

> ⚠️ **运行层待验证**：war3 1.27 lua 的 `require` 路径解析机制因项目而异。若项目使用自定义模块加载器（如框架打包），需配置正确的 `test_module_prefix`。

### 自定义引导模板

> **适用场景**：已有完整测试框架的项目（如自带测试运行器 + 初始化事件钩子的项目），通用引导（立即调用 `RunAutoTest`）无法满足执行时机需求。

**配置**：在 `config.json` 的 `test` 段设置 `test_bootstrap_template`：

```json
{
  "test": {
    "test_bootstrap_template": "examples/wzns/run_auto_test.framework.lua"
  }
}
```

**行为**：
- 路径非空 → 用 `config._resolve_path` 解析（支持 `${workspaceRoot}`、相对路径、绝对路径）
- 文件存在 → 读取内容写入 `<test_dir>/run_auto_test.lua`
- 文件不存在 → `logger.warning` + fallback 到通用 `server/lua_bootstrap.lua`
- 路径为空串 → 直接使用通用模板（默认行为，向后兼容）

**模板契约要求**：自定义模板必须遵守以下契约：

1. **读取通用字段**：从 `_target_test.lua` 读取配置，通用字段包括：
   - `test_name`（测试名称）
   - `test_file`（测试文件名）
   - `test_module`（完整模块名，已含 `test_module_prefix`）
   - `test_module_prefix`（模块前缀）
   - `http_host`（HTTP 上报地址）
   - `http_port`（HTTP 上报端口）

2. **加载测试文件并调用测试**：按项目自身机制加载测试、执行用例

3. **HTTP 上报结果**：测试完成后 POST 到 `http://<http_host>:<http_port>/result`，格式：
   ```json
   { "test_name": "<name>", "success": true|false, "details": "...", "cases": [...] }
   ```

4. **静默降级**：正常游戏时 `_target_test.lua` 不存在，模板必须静默退出，不阻断游戏加载

**范例**：`examples/` 目录提供了特定框架的自定义模板实现范例，展示如何桥接框架特有的测试机制（如自定义测试运行器、初始化事件钩子等）。

---

## 自适应环境桥

插件自动检测运行环境，屏蔽 WSL/原生 Windows 差异：

| 环境 | 编译/启动/截图 | 实现路径 |
|------|----------------|----------|
| **WSL**（`is_wsl()==True`） | 经 `win_proxy`（TCP 8767）转发到 Windows 执行 | `env_bridge.WinProxyExecutor` |
| **原生 Windows** | 直接 `subprocess` 跑 exe | `env_bridge.LocalExecutor` |

### WSL 模式部署 win_proxy

WSL 用户需在 Windows 侧启动 `win_proxy.py`：

```powershell
# Windows CMD/PowerShell
cd <plugin_root>
python win_proxy.py start
```

停止：
```powershell
python win_proxy.py stop
```

> `win_proxy.py` 是纯 TCP 转发器，无框架耦合，已通用。监听 `0.0.0.0:8767`。

---

## MCP 工具清单

| 工具 | 说明 |
|------|------|
| `compile_map` | 编译地图（同步等待 w2l.exe） |
| `compile_only` | 仅编译地图，不启动游戏 |
| `run_game` | 仅启动游戏，不编译 |
| `launch_only` | 同 `run_game` |
| `stop_game` | 关闭 War3 游戏进程 |
| `test_commit` | **核心工具**：预清理 → 编译 → 启动 → 轮询等待 HTTP 结果 → 后清理 |
| `take_screenshot` | 截取游戏窗口截图 |
| `send_key` | 向 War3 窗口发送键盘事件（Enter/Space/数字键等） |
| `cleanup_all` | 关闭 war3.exe 进程和 HTTP 服务器 |
| `stop_http_server` | 仅关闭 HTTP 测试服务器（不关闭游戏） |

### test_commit 内部流程

```
1. 预清理：stop_game（确保干净状态）
2. 写入 _target_test.lua + run_auto_test.lua 到 <test_dir>/
3. 编译地图（同步等待 w2l.exe）
4. 删除旧结果文件
5. 启动游戏（异步）
6. 轮询等待 HTTP 测试结果（默认超时 60 秒）
7. 后清理：stop_game
```

**默认超时**：60 秒

---

## 快速开始

### 1. 配置插件

在项目根目录创建 `config.json`：

```json
{
  "test": {
    "test_dir": "auto-test",
    "test_module_prefix": ""
  },
  "compile": {
    "output_name": "your-map.w3x"
  }
}
```

### 2. 编写测试文件

在 `<source_dir>/<test_dir>/test_example.lua`：

```lua
function RunAutoTest()
    print('[Test] 开始执行测试...')
    
    -- 执行测试逻辑
    local success = true
    local details = '所有断言通过'
    local cases = {
        {name = '断言1', success = true, message = '通过'},
        {name = '断言2', success = true, message = '通过'},
    }
    
    -- HTTP 上报结果
    -- ⚠️ 此处 API 因项目而异，需从目标项目提取或运行层验证
    -- 参考方向：使用你项目的 HTTP 客户端 POST JSON 到 http://127.0.0.1:8766/result
    -- 示例伪代码：YourProject.http.post('http://127.0.0.1:8766/result', data, {timeout=10})
    
    print('[Test] 测试完成')
end
```

### 3. 执行测试

```bash
# 编译 + 启动 + 等待结果
mcp__war3-tester__test_commit --test_name test_example --test_file test_example.lua
```

---

## HTTP 上报 API（运行层待验证）

> ⚠️ **诚实标注**：war3 1.27 lua 的 HTTP 上报 API 因项目而异，插件**不强制**具体实现。以下为参考方向，**需从目标项目提取或运行层验证**。

### 参考实现方向

不同项目可能有不同的 HTTP 客户端实现。以下是一个**概念示例**（具体 API 需从目标项目提取）：

```lua
-- 概念示例：使用项目现有的 HTTP 客户端（伪代码）
local http_client = require('your.project.http')  -- 需替换为实际模块
local HTTP_SERVER_URL = 'http://127.0.0.1:8766/result'

local data = {
    test_name = 'test_example',
    success = true,
    details = '所有断言通过',
    cases = {
        {name = '断言1', success = true, message = '通过'},
    }
}

local ok, result = http_client.post(HTTP_SERVER_URL, data, {timeout = 10})
```

### 通用方向

不同项目可能有不同的 HTTP 客户端实现：
- 自定义 Lua socket 库
- JASS 原生 `HttpRequest`（若支持）
- 第三方库（如 `lua-curl`）

**建议**：从目标项目现有代码中提取 HTTP 客户端实现，或参考 `examples/` 目录下的适配器范例。

---

## 测试文件加载机制（运行层待验证）

> ⚠️ **诚实标注**：war3 lua 获取"脚本自身目录"的原语因项目而异。通用引导使用 `test_module_prefix` 配置项显式指定路径，**不假设**项目存在"获取当前脚本路径"之类的自定义全局函数。

### 加载策略

| `test_module_prefix` | 加载方式 | 示例 |
|----------------------|----------|------|
| `""` (空串) | `require(test_file:gsub('%.lua$', ''))` | 测试文件与引导脚本同目录 |
| `"your.framework.prefix."` | `require('your.framework.prefix.' .. name)` | 使用框架打包结构的项目 |

### 若项目使用自定义模块加载器

若目标项目使用框架打包结构（如自定义模块加载器、自定义 `require` 路径），需：
1. 配置正确的 `test_module_prefix`
2. 或修改 `lua_bootstrap.lua` 适配项目加载机制

**参考**：`examples/` 目录提供特定框架适配器范例。

---

## 错误分析与调试

### 日志来源

1. **游戏运行日志**（游戏自动输出）：
   - 日志位置取决于所使用的游戏平台（KKWE / YDWE）和项目配置，通常位于平台安装目录下的日志文件夹
   - WSL 用户：对应 Windows 路径可通过 `/mnt/<盘符>/...` 访问
   - 包含所有游戏内 `print()` 输出
   - 具体路径请根据你的平台环境定位，插件不硬编码特定目录

2. **测试结果 JSON**（HTTP 上报）：
   - 插件接收后保存到 `<plugin_root>/logs/test_results/<test_name>.json`
   - 包含测试断言结果和部分日志

### 常见错误处理

| 错误类型 | 处理方式 |
|---------|---------|
| 测试脚本不存在 | 提示用户先创建测试文件 |
| 编译失败 | 显示 w2l.exe 错误日志，不执行测试 |
| 测试失败 | 查看游戏日志 → 分析失败断言 → 修复代码 |
| 游戏卡在对话框 | 用 `take_screenshot` 截图 → 自行查看画面状态 → `send_key` 继续 |
| HTTP 上报失败 | 检查游戏内 HTTP 客户端实现、网络连通性、8766 端口监听 |

### 截图调试

```bash
# 截图并查看
mcp__war3-tester__take_screenshot --test_name test_xxx
# 截图文件保存在 logs/screenshots/ 目录，可手动查看
```

---

## 操作约束

**⚠️ 严禁 AI 直接操作 Windows 端**

| 禁止行为 | 说明 |
|---------|------|
| `net start` / `sc start` | 禁止直接启动/停止 Windows 服务 |
| 直接访问 Windows 路径 | 文件操作由 MCP 工具代理完成 |
| 手动启动/停止 War3 | 通过 `mcp__war3-tester__*` 工具代理 |

**正确做法**：通过 MCP 工具与 Windows 服务通信。

---

## 推荐工作流

```
修改代码 → compile_only（快速验证编译） → test_commit（完整测试）
```

`test_commit` 内部自动执行：`stop_game → 编译 → 启动游戏 → 等待结果 → stop_game`。

---

## 已知风险与待验证项

| 风险/待验证 | 缓解/说明 |
|------------|-----------|
| war3 1.27 lua HTTP 上报 API 因项目而异 | 契约最小化 + 文档化参考方向 + 运行层验证，不臆造 |
| 模块加载机制（`require` 路径解析）因项目而异 | `test_module_prefix` 可配置 + `examples/` 范例 |
| 插件级 `.mcp.json` 格式歧义 | README 备注两种写法，`/mcp` 实测确认 |
| issue #41137 mcpServers 被擦除 | README 故障排查章节 |
| w2l.exe / KKWE / YDWE 路径因机器而异 | 全部走 config（环境变量 > 配置文件 > 搜索），去硬编码 |

---

## 检查清单

- [ ] 配置 `config.json`（test_dir / test_module_prefix / compile）
- [ ] 编写测试文件（定义 `RunAutoTest()` + HTTP 上报）
- [ ] 调用 `test_commit` 执行测试
- [ ] 等待测试完成（最多 timeout 秒）
- [ ] 查看测试结果 JSON
- [ ] 资源已清理（游戏进程、HTTP 服务器）
- [ ] **测试失败时**：查看游戏日志 → 分析失败断言 → 修复代码 → 重新测试
