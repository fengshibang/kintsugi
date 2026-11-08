---
name: war3-test
description: "通用 War3 地图自动测试与 Named Pipe Agent 入口：环境安装/修复 → 编译 → 启动 → 测试 / 步进探索"
---

# /war3-test - War3 地图自动测试与环境修复

本命令调用 `war3-auto-test` skill，执行 War3 地图自动测试、Named Pipe 实机探索或环境一键安装/修复。

## 使用方式

```
/war3-test [test_name] [test_file]
/war3-test setup | repair | check
```

## 1. 环境一键安装 / 体检 / 修复（`setup_environment`）

当新项目首次接入、或者测试/命名管道功能异常（如缺少 `agent_bridge.dll`、`agent/*.lua` 被误删、`-test on` 无响应、`_test_off.lua` 残留）时，直接调用 MCP 工具 `setup_environment`：

- **只读体检 (`mode="check"`)**：
  ```json
  {"source_dir": "D:\\maps\\wzns", "war3_dir": "D:\\war3", "mode": "check"}
  ```
- **一键安装/修复全部组件 (`mode="repair"`, 默认)**：
  ```json
  {
    "source_dir": "D:\\maps\\wzns",
    "war3_dir": "D:\\war3",
    "mode": "repair",
    "components": ["socket", "http", "nopause", "agent_bridge", "agent_lua", "entry_hook", "plugin_sync"]
  }
  ```

涵盖七大组件：
1. `socket`：部署 `socket.dll` + `libwinpthread-1.dll` 到 `map/`
2. `http`：安装/验证 Python `flask` + `werkzeug`
3. `nopause`：部署 `nopause.asi` 到 War3 目录
4. `agent_bridge`：部署 `agent_bridge.dll` 到 `map/`（及 War3 目录 `agent_bridge.asi`）
5. `agent_lua`：部署/修复 `<test_dir>/agent/` 下全部 15 个 Lua Agent 与五大 Oracle 脚本（自动适配项目 `test_module_prefix`）及 `_war3_tester` 断言/mock 库
6. `entry_hook`：检查/注入 `<test_dir>/init.lua` 的 `-test on` / `-agent on` 聊天启动钩子，并清除残留 `_test_off.lua`
7. `plugin_sync`：同步插件源码至 Claude 插件缓存目录

## 2. 自动化测试与实机探索流程

1. **桌面秒级单测**：`run_unit_test(test_name="...")`
2. **实机回归测试**：`test_commit(test_name="...")` 或 `run_test_batch(test_filter="all")`
3. **Named Pipe 实机探索**：`game_status` → `game_observe` → `game_set_mode("step")` → `game_act` → `game_set_mode("free")`

详细规范见 `skills/war3-auto-test/SKILL.md`。
