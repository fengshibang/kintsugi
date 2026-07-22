# mentor-kit

> 师傅审查基建 + eval 框架的 Claude Code 插件。**领域中立**——强模型（师傅）审查弱模型产出，把错误沉淀成 eval case，反复 fail 的崩溃级模式晋升硬红线、内联进 spawn prompt。任何项目装上即用。

## 它解决什么

弱模型（子代理）产出错误系统性复发，但它无状态、权重不可调——**无法训练**。本机制让强模型（师傅）在审查中把"错在哪、为什么"一条条固化进 eval case 库，反复 fail 的崩溃级模式晋升为硬红线、内联进下次 spawn prompt（唯一能影响无状态弱模型的通道）。机制补**师傅的审查纪律**，不补弱模型的能力。

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
| `/mentor-kit:mentor <任务>` | 审查弱模型产出，走审查→沉淀→硬红线传承 |
| `/mentor-kit:evals [filter]` | 跑 eval 回归，看通过率 / baseline delta / 规范库增益 |
| `/mentor-kit:new-case <target-seq>` | 引导沉淀新 eval case |

## 前置条件

1. **模型路由**：主会话（师傅）跑强模型，子代理（弱模型 `Agent({ model:"haiku" })`）跑弱模型。详见 [`docs/README.md`](docs/README.md#前置条件)。
2. **项目数据目录**：每个项目需可写 `EVALS_DIR`（默认 `<项目>/.claude/evals`），存 cases / runs / report。这是唯一的外部约定——插件脚本本身完全只读。
3. **领域 skill**：机制需要一个领域 skill 作 CHK 传承载体，各项目自备（本插件不含任何领域知识）。

## 机制有效性

机制是否有效 = **eval 回归通过率随规范库（硬红线 + rubric）迭代而升，崩溃级 case 被 `## RED` / 硬红线覆盖**。若通过率不升 → 规范库没覆盖到根因，补 case 或强化硬红线（数据入 git 可回滚）。

## 文档

- [`docs/README.md`](docs/README.md) — 完整说明：前置条件、冒烟测试、度量、首次落地清单
- [`docs/SOP-沉淀新case.md`](docs/SOP-沉淀新case.md) — 沉淀新 eval case 的标准流程（任何开发领域）

## License

[MIT](LICENSE)
