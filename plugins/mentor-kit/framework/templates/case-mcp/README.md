# MCP case 模板

评估一个 MCP server 是否被**正确选择 + 正确调用 + 正确用结果**。
本目录不放骨架文件，按下面步骤在 `cases/<target>-<seq>/` 建 case。

## 1. 准备 MCP 配置

把被测 MCP server 写成 JSON 文件，如 `cases/<id>/mcp.json`：

```json
{
  "mcpServers": {
    "my-server": { "command": "node", "args": ["path/to/server.js"] }
  }
}
```

## 2. `config.json`

```json
{
  "target": "my-mcp",
  "mcp_config": "cases/<id>/mcp.json",
  "isolate": true,
  "baseline": false,
  "budget_usd": 0.3,
  "timeout_secs": 300
}
```

`runner.sh` 会透传 `--mcp-config cases/<id>/mcp.json`（也接受内联 JSON 字符串）。
注意：路径相对于主仓库根，不是 worktree——worktree 里的 `.claude/evals` 已被删除。

## 3. `prompt.md`

描述一个**必须调用该 MCP 工具**才能完成的任务。

## 4. `rubric.md`（三层检查）

```markdown
## CHECK tool-selected
是否调用了正确的 MCP 工具（工具列表里的 tool_use name）。

## CHECK args-correct
参数是否正确（schema 合规 + 语义正确）。

## CHECK end-to-end
最终答案是否正确（任务目标达成）。
```

> 项目当前没有配置 MCP server，故无现成 MCP case。配置后按上填写即可。
