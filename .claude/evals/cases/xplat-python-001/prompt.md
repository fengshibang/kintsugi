# 跨平台 Python MCP server 启动方案（避开 Windows Store 别名桩）

## 背景

一个 Claude Code 插件的 `.mcp.json` 需启动一个 Python 写的 stdio MCP server（`server/mcp_server.py`）。`.mcp.json` 当前配置：

```json
{ "my-server": { "command": "python3", "args": ["${CLAUDE_PLUGIN_ROOT}/server/mcp_server.py"] } }
```

问题：`.mcp.json` 是【静态 JSON】，Claude Code 直接读取 `command` 字段去执行，**无法内联 bash 探测逻辑**。而 Windows 原生的 `python3` 通常是 Microsoft Store 别名桩（App Execution Alias），不可靠。

## 真实素材（本机实测）

```
where python3 → C:\Users\My\AppData\Local\Microsoft\WindowsApps\python3.exe   ← Store 别名桩，唯一匹配
where python  → 可能多行：WindowsApps\python.exe（Store 桩，常排第一）/ C:\Python313\python.exe（真实）
where py      → C:\Windows\py.exe（启动器，可靠）/ WindowsApps\py.exe（Store 桩）
```

- Store 别名桩行为：不同启动上下文不一致（可能弹 Microsoft Store / 异常退出码），曾导致服务 `EXIT_CODE 3`。
- Linux/macOS：`python3` 是真实解释器，通常无 `python`（或 `python` = py2）、无 `py` 启动器。

## 任务

设计一个跨平台（Windows 原生 + Linux/macOS）方案，让该 MCP server 可靠启动：

1. Windows 原生下避开 Store 别名桩，用真实 Python。
2. 不破坏 Linux/macOS（那里 `python3` 真实）。
3. 不引入用户需额外安装的依赖（Claude Code 既有依赖如 `node` 可用）。

交付：启动方案（`.mcp.json` 改动 + 必要的启动脚本），并说明跨平台可靠性。
