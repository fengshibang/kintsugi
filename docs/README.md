# mentor-kit

师徒试错机制 + eval 框架的 Claude Code 插件。**领域中立**——师傅监督徒弟改代码，把错误沉淀成 eval case，回归验证。任何项目装上即用。

## 它解决什么

弱模型（徒弟）是日常产出主力但质量参差、错误系统性复发。本机制让强模型（师傅）在监督返工中把"徒弟为什么犯错"一条条固化进 eval case 库，返工率随迭代单调下降。机制补**纪律**，不补能力。

## 前置条件

### 1. 模型路由（~/.claude/settings.json env）

主会话跑强模型（师傅），子代理跑弱模型（徒弟）：

```jsonc
{
  "env": {
    "ANTHROPIC_DEFAULT_OPUS_MODEL":   "<STRONG_MODEL>",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL":  "<WEAK_MODEL>",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "<WEAK_MODEL>",
    "ANTHROPIC_MODEL": "<WEAK_MODEL>"
  }
}
```
师傅吃 `opus` 槽（主会话），徒弟用 `Agent({ model:"haiku" })` 吃 `haiku` 槽。

> ⚠️ 安全：导出/分享配置时务必抹掉真实 token 与网关地址，只留占位符。

### 2. 冒烟测试（启动前必跑一次）

```
Agent({ model: "haiku", subagent_type: "general-purpose", prompt: "只回复你当前实际运行的模型名，不要做别的。" })
```
返回值应是 `<WEAK_MODEL>`。若返回强模型，说明路由没生效，先修配置。

### 3. 项目数据目录（EVALS_DIR）

每个项目需有可写的数据目录存放 cases/runs/report，默认 `<项目>/.claude/evals`。这是**唯一的外部约定**——所有命令都通过 `EVALS_DIR` env 注入数据目录，插件脚本本身完全只读。

若你的数据目录不叫 `.claude/evals`，命令里显式指定即可：
```bash
EVALS_DIR=/path/to/your/evals bash "${CLAUDE_PLUGIN_ROOT}/framework/run_all.sh"
```

### 4. 领域 skill（CHK 传承载体，各项目自备）

机制需要一个领域 skill 作为知识沉淀载体（含 CHK 自检清单）。本插件不含任何领域知识——请在项目 `.claude/skills/<你的领域>/` 自备。

## 安装

本地 marketplace（开发期）。在 `~/.claude/settings.json` 配置（`path` 换成本机插件实际路径）：
```jsonc
{
  "enabledPlugins": { "mentor-kit@local-dev": true },
  "extraKnownMarketplaces": {
    "local-dev": { "source": { "source": "directory", "path": "<插件安装路径，如 /home/<user>/.claude/plugins-dev/mentor-kit>" } }
  }
}
```
重启 Claude Code，命令以 `/mentor-kit:mentor` 等形式可用。

## 命令

| 命令 | 用途 |
|---|---|
| `/mentor-kit:mentor <任务>` | 带徒弟做任务，走试错循环 |
| `/mentor-kit:evals [filter]` | 跑 eval 回归，看通过率/baseline delta |
| `/mentor-kit:rework <case-id>` | 对 fail case 跑三阶段渐进纠正 |
| `/mentor-kit:new-case <target-seq>` | 引导沉淀新 eval case |

## 首次落地 Checklist

- [ ] 配好模型路由（opus=师傅/haiku=徒弟），跑冒烟测试
- [ ] 项目有可写 EVALS_DIR 数据目录
- [ ] 项目有领域 skill 作 CHK 载体
- [ ] 从下一批重复类任务开始 `/mentor-kit:mentor`，每犯一错走灵魂动作

## 机制有效性度量

机制是否有效 = **徒弟返工率随 eval 迭代单调下降**。三条曲线：通过率（应升）/ 往返轮数（K=3→K=1）/ eval 规模（先涨后平）。若返工率不降反升 → 某 case 写错了，回滚（数据入 git 可回滚）。

设计依据：被使用项目的 `docs/superpowers/specs/` 下 `mentor-kit-plugin-design.md`。
