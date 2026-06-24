# Hook case 模板

评估一个 hook（`PreToolUse` / `PostToolUse` / `Stop` / `UserPromptSubmit` 等）
是否在正确时机生效（拦截 / 注入 / 改写行为）。

hook 配置无法仅靠 case 目录表达，需通过**临时 settings** 注入。

## 1. `config.json`

```json
{
  "target": "my-hook",
  "settings": "cases/<id>/settings.json",
  "isolate": true,
  "baseline": false
}
```

`runner.sh` 会透传 `--settings cases/<id>/settings.json`（路径相对主仓库根）。

## 2. `settings.json`（含 hook 定义）

```json
{
  "hooks": {
    "PreToolUse": [
      { "matcher": "Bash", "hooks": [ { "type": "command", "command": "echo BLOCKED; exit 2" } ] }
    ]
  }
}
```

## 3. `prompt.md`

描述会触发 hook 条件的操作（如让 agent 执行某 `Bash` 命令）。

## 4. `rubric.md`

检查 hook 副作用：该拦截时是否真的拦截、该注入时是否注入。
判定依据：`output.json` 里的工具调用结果 / 会话最终行为。

> - hook 会改变被测会话行为，**仍建议 `isolate:true`**（worktree 隔离），避免 hook 配置或
>   其副作用误伤主仓库工作区。
> - 项目当前没有 hooks，故无现成 hook case。
