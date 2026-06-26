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

### 多徒弟场景冒烟测试

1. 准备一个 git 项目，配置好模型路由（opus=师傅，haiku=徒弟）
2. 执行一个简单任务（如"加一个函数"），观察师傅判断不拆 → 走一对一流程
3. 执行一个跨模块任务（如"加一个前端组件 + 后端接口"），观察师傅判断拆 → 并行 spawn 多个徒弟 → 集成徒弟合并
4. 观察 worktree 创建/合并/清理日志，确认生命周期正常
5. 观察 cases/ 目录，确认错误沉淀正常（part 级/集成级/拆分判断级）

### 3. 项目数据目录（EVALS_DIR）

每个项目需有可写的数据目录存放 cases/runs/report，默认 `<项目>/.claude/evals`。这是**唯一的外部约定**——所有命令都通过 `EVALS_DIR` env 注入数据目录，插件脚本本身完全只读。

若你的数据目录不叫 `.claude/evals`，命令里显式指定即可：
```bash
EVALS_DIR=/path/to/your/evals bash "${CLAUDE_PLUGIN_ROOT}/framework/run_all.sh"
```

### 4. 领域 skill（CHK 传承载体，各项目自备）

机制需要一个领域 skill 作为知识沉淀载体（含 CHK 自检清单）。本插件不含任何领域知识——请在项目 `.claude/skills/<你的领域>/` 自备。

### 5. 多徒弟场景前置条件（git 项目）

多徒弟编排依赖 git worktree 隔离，要求项目是 git 仓库。非 git 项目退化为串行（无 worktree，每个徒弟串行改）。

**worktree 生命周期**（师傅拥有全生命周期）：
- **创建**：师傅用 `git worktree add <path> -b <branch>` 创建 worktree + 命名分支
- **分配**：师傅 spawn 徒弟时传 worktree 路径 + 分支名
- **合并**：集成徒弟按分支名 `git merge <branch-1> <branch-2> ...` 合并到 main
- **清理**：师傅在集成完成后 `git worktree remove <path>` 清理所有 part worktree

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

### 多徒弟场景度量指标

**多徒弟场景新增指标**：
- **拆分率**：师傅判断拆的任务占比（过高 = 过度拆分，过低 = 拆分不足）
- **集成失败率**：集成徒弟失败的任务占比（过高 = 拆分边界划错）
- **并行度**：平均每个任务拆成几个 part（过高 = 上下文爆炸风险）

**现有指标保持不变**：
- 通过率（升）
- 往返轮数（K=3→K=1）
- eval 规模（先涨后平）

设计依据：被使用项目的 `docs/superpowers/specs/` 下 `mentor-kit-plugin-design.md`。

## 首次迁移回归结论（v0.1.0）

- **路径解耦验证**：✅ 通过。`FRAMEWORK_DIR`（插件 framework）/ `EVALS_DIR`（项目数据）/ `REPO_ROOT` 三者正确分离；框架资源（judge-schema + lib 4 脚本 + templates）在插件可达，case 数据在项目可达，未注入 `EVALS_DIR` 时脚本报错守卫生效。
- **语法**：✅ 全框架 `bash -n` 通过。
- **占位符化**：✅ skills / commands / README 无 glm/qwen/war3 硬编码，无 `cd .claude/evals`。
- **端到端 `run_all.sh` 回归**：⏳ 待补。需在装好插件的环境跑 `EVALS_DIR=<数据目录> bash "${CLAUDE_PLUGIN_ROOT}/framework/run_all.sh"`，确认现有 case 通过率不退化（`PASS_THRESHOLD=0.8`）。开发期已用路径可达性验证替代（真实跑被测 claude 会话成本高，留待首次实际使用时补跑）。
