# mentor-kit

> 师徒试错机制 + eval 框架的 Claude Code 插件。**领域中立**——师傅监督徒弟改代码，把错误沉淀成 eval case，回归验证。任何项目装上即用。

## 它解决什么

弱模型（徒弟）是日常产出主力但错误系统性复发。本机制让强模型（师傅）在监督返工中把"徒弟为什么犯错"一条条固化进 eval case 库，返工率随迭代单调下降。机制补**纪律**，不补能力。

## 安装

### 已发布（GitHub marketplace）

```
/plugin marketplace add fengshibang/kintsugi
/plugin install mentor-kit@mentor-kit
```

### 开发期（本机 directory source）

在 `~/.claude/settings.json` 配置（`path` 换成本机插件实际路径）：

```jsonc
{
  "enabledPlugins": { "mentor-kit@mentor-kit": true },
  "extraKnownMarketplaces": {
    "mentor-kit": { "source": { "source": "directory", "path": "<插件安装路径，如 /home/<user>/.claude/plugins-dev/mentor-kit>" } }
  }
}
```

重启 Claude Code，命令以 `/mentor-kit:mentor` 等形式可用。

## 命令

| 命令 | 用途 |
|---|---|
| `/mentor-kit:mentor <任务>` | 带徒弟做任务，走试错循环 |
| `/mentor-kit:evals [filter]` | 跑 eval 回归，看通过率 / baseline delta |
| `/mentor-kit:rework <case-id>` | 对 fail case 跑三阶段渐进纠正 |
| `/mentor-kit:new-case <target-seq>` | 引导沉淀新 eval case |

## 前置条件

1. **模型路由**：主会话（师傅）跑强模型，子代理（徒弟 `Agent({ model:"haiku" })`）跑弱模型。详见 [`docs/README.md`](docs/README.md#前置条件)。
2. **项目数据目录**：每个项目需可写 `EVALS_DIR`（默认 `<项目>/.claude/evals`），存 cases / runs / report。这是唯一的外部约定——插件脚本本身完全只读。
3. **领域 skill**：机制需要一个领域 skill 作 CHK 传承载体，各项目自备（本插件不含任何领域知识）。

## 机制有效性

机制是否有效 = **徒弟返工率随 eval 迭代单调下降**。三条曲线：通过率（升）/ 往返轮数（K=3→K=1）/ eval 规模（先涨后平）。若返工率不降反升 → 某 case 写错了，回滚（数据入 git 可回滚）。

## 文档

- [`docs/README.md`](docs/README.md) — 完整说明：前置条件、冒烟测试、度量、首次落地清单
- [`docs/SOP-沉淀新case.md`](docs/SOP-沉淀新case.md) — 沉淀新 eval case 的标准流程（任何开发领域）

## License

[MIT](LICENSE)
