# mentor-kit

师傅审查基建 + eval 框架的 Claude Code 插件。**领域中立**——强模型（师傅）审查弱模型产出，把错误沉淀成 eval case，反复 fail 的崩溃级模式晋升硬红线、内联进 spawn prompt。任何项目装上即用。

## 它解决什么

弱模型（子代理）产出错误系统性复发，但它无状态、权重不可调——**无法训练**。本机制让强模型（师傅）在审查中把"错在哪、为什么"一条条固化进 eval case 库，反复 fail 的崩溃级模式晋升为硬红线、内联进下次 spawn prompt（唯一能影响无状态弱模型的通道）。机制补**师傅的审查纪律**，不补弱模型的能力。

## 前置条件

### 1. 模型路由（~/.claude/settings.json env）

主会话跑强模型（师傅），子代理跑弱模型：

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
师傅吃 `opus` 槽（主会话），弱模型用 `Agent({ model:"haiku" })` 吃 `haiku` 槽。

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

机制需要一个领域 skill 作为知识沉淀载体（含 CHK 自检清单）。本插件不含任何领域知识——请在项目 `.claude/skills/<你的领域>/` 自备。**硬红线最终晋升进这个领域 skill**，是传承通道的落点。

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
| `/mentor-kit:evals [filter]` | 跑 eval 回归，看通过率/baseline delta/规范库增益 |
| `/mentor-kit:new-case <target-seq>` | 引导沉淀新 eval case |

## 首次落地 Checklist

- [ ] 配好模型路由（opus=师傅/haiku=弱模型），跑冒烟测试
- [ ] 项目有可写 EVALS_DIR 数据目录
- [ ] 项目有领域 skill 作 CHK 载体（硬红线晋升落点）
- [ ] 从下一批重复类任务开始 `/mentor-kit:mentor`，每发现一错走灵魂动作

## 机制有效性度量

机制是否有效 = **eval 回归通过率随规范库（硬红线 + rubric）迭代而升，崩溃级 case 被 `## RED` / 硬红线覆盖**。若通过率不升 → 规范库没覆盖到根因，补 case 或强化硬红线（数据入 git 可回滚）。

设计依据：被使用项目的 `docs/superpowers/specs/` 下 `mentor-kit-plugin-design.md`。

## 首次迁移回归结论（v0.1.0）

- **路径解耦验证**：✅ 通过。`FRAMEWORK_DIR`（插件 framework）/ `EVALS_DIR`（项目数据）/ `REPO_ROOT` 三者正确分离；框架资源（judge-schema + lib 脚本 + templates）在插件可达，case 数据在项目可达，未注入 `EVALS_DIR` 时脚本报错守卫生效。
- **语法**：✅ 全框架 `bash -n` 通过。
- **占位符化**：✅ skills / commands / README 无 glm/qwen/war3 硬编码，无 `cd .claude/evals`。
- **端到端 `run_all.sh` 回归**：⏳ 待补。需在装好插件的环境跑 `EVALS_DIR=<数据目录> bash "${CLAUDE_PLUGIN_ROOT}/framework/run_all.sh"`，确认现有 case 通过率不退化（`PASS_THRESHOLD=0.8`）。
