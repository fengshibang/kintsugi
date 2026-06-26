---
name: mentor-protocol
description: Use when supervising apprentice-model-produced code (apprentice is the doer spawned via Agent model:haiku, the main-session model via opus slot is the supervisor/mentor) — when apprentice output has runtime crashes, features not working, or convention violations, or when systematically improving apprentice quality via check/rework/case-sedimentation instead of one-off manual fixes. 领域中立，任何项目装上即用。
---

# 师徒协议 — 师傅监督徒弟（试错式沉淀）

## Overview

师傅**不亲自改代码**，而是**监督徒弟改**，在返工中把错误根因沉淀进 eval case 库（崩溃级错误晋升为硬红线）。机制补徒弟的**纪律**，不补能力——徒弟查得动源码，但不会每次都查；eval case 库把"偶尔想到"变成"每次必查"。

**模型路由**（用户 `~/.claude/settings.json` env 配置）：`opus` 槽 = 师傅（主会话/检查者），`haiku`/`sonnet` 槽 = 徒弟（子代理/产出者）。spawn 徒弟 = `Agent({ model:"haiku" })`，零额外配置。具体哪个模型占哪个槽由用户 env 决定，本协议只认这个抽象映射。

## 拆分判断（默认不拆）

**默认行为**：不拆分，走现有 mentor-protocol 一对一师徒循环。

**什么时候拆**（满足任一即可）：
- 任务天然跨多个独立模块/层（如"加一个前端组件 + 后端接口 + 数据库表"）
- 任务内有明显可并行的独立子任务（如"迁移 A 模块 + 迁移 B 模块"，互不依赖）
- 任务规模大，单徒弟容易上下文爆炸或反复失败

**什么时候不拆**（护栏，防止过度拆分）：
- 一个徒弟能在合理范围内独立完成 + 独立验证 → 不拆
- 子任务之间耦合紧密（改 A 必须同步改 B 才能跑通）→ 不拆
- 任务本身很小（几分钟能搞定）→ 不拆
- 探索性/调研性任务 → 不拆（走师傅直接做）

**师傅的判断输出**：
- 决定不拆 → 直接走现有 mentor-protocol 一对一流程（零变化）
- 决定拆 → 输出结构化 decomposition 计划（表格/JSON：part 列表、依赖关系、并行组）

## When to Use

**启用**：徒弟产出的重复类任务（<你的重复任务领域>）有质量问题；用户说"带徒弟""监督返工""优化 skill"；徒弟代码出现运行崩溃 / 功能失效 / 规范违背。

**不启用**：探索调研、读码问答、紧急修复 → 师傅直接做。

## 核心循环

① 检查（师傅三层审徒弟产出，定位根因）→ ② 监督返工（师傅喂问题+判定标准+根因给徒弟，绝不亲手改）→ ③ 错误沉淀（这错值得沉淀成 eval case 吗？崩溃级/反复犯/CHK 未覆盖 → 入 cases/）→ 循环。

**灵魂动作**：徒弟每次犯错，师傅强制自问——"这错，值得沉淀成 eval case 吗？"

## 多徒弟编排流程（拆分时）

**不拆分时**：走现有 mentor-protocol 一对一流程（零变化）

**拆分时**：
1. 师傅判断是否拆 → 不拆走一对一，拆则继续
2. 师傅输出结构化 decomposition 计划（JSON 格式，见下方模板，每个 part 含 `branch` 字段）
3. 师傅先手动 `git worktree add <path> -b <branch>` 创建 N 个 worktree（每个 worktree 一个命名分支），然后并行 spawn 多个徒弟：`Agent({ model:"haiku", subagent_type:"general-purpose", prompt:<徒弟模板> })`（prompt 里传 worktree 路径 + 分支名）
4. 每个徒弟在各自 worktree 的命名分支上完成 part → commit → 师傅逐个三层审查
5. 审完所有 part → spawn 集成徒弟：`Agent({ model:"haiku", subagent_type:"general-purpose", prompt:<集成徒弟模板> })`
6. 集成徒弟按分支名 `git merge <branch-1> <branch-2> ...` 合并所有 part + 解决冲突 + 跑通整体
7. 师傅对集成徒弟的产出做最终三层审查
8. 错误沉淀：每个徒弟 + 集成徒弟各自沉淀自己的 case

### decomposition 计划模板

```json
{
  "task": "<原始任务描述>",
  "parts": [
    {
      "id": "part-1",
      "branch": "part-1",
      "desc": "<part 1 具体目标>",
      "files": ["<预计改动的文件/目录>"],
      "deps": [],
      "verify": "<独立验证方式>"
    },
    {
      "id": "part-2",
      "branch": "part-2",
      "desc": "<part 2 具体目标>",
      "files": ["<预计改动的文件/目录>"],
      "deps": ["part-1"],
      "verify": "<独立验证方式>"
    }
  ],
  "parallel_groups": [["part-1"], ["part-2"]]
}
```

### 徒弟 prompt 模板（多徒弟场景）

复用现有徒弟 prompt 模板，但每个徒弟只负责一个 part：

```
【任务】<part 的具体目标 + 基线参照>
【崩溃级硬红线】<仅极少数会导致静默失效/全局崩的硬约束，≤10 条>
【自检】产出后跑 <你的自动检查命令>，报告一并返回
【输出】①改动清单 ②自检报告 ③不确定处明确标出
【worktree】你工作在独立 worktree（<worktree 路径>），分支 <part-N>，改动只在本 worktree 的该分支，不要动 main 分支
【分支】在本 worktree 的分支 <part-N> 上 commit 你的改动
```

### 集成徒弟 prompt 模板

集成徒弟专门负责 merge + 冲突解决 + 跑通整体：

```
【任务】将以下 part 的改动合并到 main 分支，解决冲突，确保整体跑通
【part 列表】
- part-1: <改动清单>，分支: part-1
- part-2: <改动清单>，分支: part-2
【合并前检查】
1. 确认每个 part 的分支已 commit（在各自 worktree 检查 git status）
【合并策略】
1. 按分支名逐个 git merge <branch-1> <branch-2> ... 到 main
2. 遇到冲突：按 part 的依赖关系解决（依赖方优先）
3. 合并后跑 <整体验证命令>，确保整体跑通
【输出】①合并日志 ②冲突解决记录 ③整体验证结果 ④不确定处明确标出
```

### worktree 生命周期

师傅拥有 worktree 全生命周期：

- **创建**：师傅用 `git worktree add <path> -b <branch>` 创建 worktree + 命名分支（每个 part 一个 worktree）
- **分配**：师傅 spawn 徒弟时传 worktree 路径 + 分支名
- **合并**：集成徒弟按分支名 `git merge <branch-1> <branch-2> ...` 合并到 main
- **清理**：师傅在集成徒弟完成后 `git worktree remove <path>` 清理所有 part worktree

徒弟只负责在分配的 worktree 分支上 commit，不参与 worktree 创建/清理。

**非 git 项目退化**：
- 无 worktree，每个徒弟串行改（师傅审完一个再下一个）
- 集成徒弟退化为"汇总徒弟"（汇总所有改动，确保不冲突）

## 三层检查（不同问题用不同手段）

| 层 | 问题类型 | 手段 | 执行者 |
|---|---|---|---|
| 静态 | 规范/API 违背 | judge.sh `auto-pass`/`auto-fail` + 徒弟自检（<你的自动检查命令>） | 机器判 + 徒弟自检 |
| 逻辑 | 功能不对 | 师傅对照 <领域 skill 规范> + 项目同类实现深审 | 师傅 |
| 运行 | 崩溃/报错 | <你的运行验证手段，如跑测试/跑应用> | **用户**（师傅跑不了的部分） |

任一层失败 → 回到 ②监督返工。

## 徒弟 prompt 模板（试错版·不给答案）

子代理不一定可靠加载 skill，必须兜底。**不给预设答案、不强制预读 CHK 清单**——只给任务和必要上下文，让徒弟裸做、碰壁：
```
【任务】<具体目标 + <基线参照（如 基线文件:行号 / 验收标准）>>
【崩溃级硬红线】<仅极少数会导致静默失效/全局崩的硬约束，从 §硬红线清单 取，≤10 条；其余一律不给>
【自检】产出后跑 <你的自动检查命令>，报告一并返回
【输出】①改动清单 ②自检报告 ③不确定处明确标出
```

## 监督返工：三阶段渐进（机制化）

由 `framework/mentor-rework.sh` 执行（师傅不亲自改代码）：

| 轮次 | 反馈给徒弟 | 意图 |
|---|---|---|
| R1 | 原任务，不给任何 fail 信息 | 摸索、碰壁 |
| R2 | + fail 项的判定标准（不给根因/正解） | 知道错在哪，自己查 |
| R3 | + 根因提示 + expected 正解 | 完整示范 |

- 每任务最多 **K=3 轮**。
- 超 3 轮未通过 → 师傅接手完成，**必须**把"为何反复失败"沉淀成新 eval case。
- 师傅**绝不**在返工阶段亲自改代码——否则丢掉错误模式素材。
- run 层 pending（待用户运行验证）不参与 rework 反馈，独立走 `judge.sh --merge-user` 回填。

## 硬红线清单（崩溃级，≤10 条，从 eval 案例晋升）

> 不预先堆砌。从 eval 库"反复 fail 且代价=静默失效/全局崩"的 `## RED` check 晋升。
> 超 10 条 = skill 表述缺陷，重构而非新增。

（初始为空，随 eval 案例积累由师傅提炼填充）

## Quick Reference

| 操作 | 命令/位置 |
|---|---|
| 当场纠正（三阶段） | `EVALS_DIR=<数据目录> bash "${CLAUDE_PLUGIN_ROOT}/framework/mentor-rework.sh" cases/<case-id>` |
| 批量回归 | `EVALS_DIR=<数据目录> bash "${CLAUDE_PLUGIN_ROOT}/framework/run_all.sh" [filter]` |
| 运行层回填 | run-dir 放 `user-verdict.json` → `bash "${CLAUDE_PLUGIN_ROOT}/framework/judge.sh" <case> <run-dir> --merge-user` |
| 沉淀新 case | 流程见 `docs/SOP-沉淀新case.md` |
| 评判标准语法 | 见 spec §5（layer/auto-pass·auto-fail/## RED） |

## Common Mistakes

| 错误 | 纠正 |
|---|---|
| 师傅亲自改徒弟的代码 | 监督徒弟改——否则丢掉错误模式素材，eval 库无法迭代 |
| 只做静态检查就放行 | 必过逻辑层(对照领域规范) + 运行层(用户实跑) |
| 修了错不沉淀 | 每个错必走灵魂动作 → 沉淀成 eval case（入 cases/） |
| 盲信徒弟注释"已验证" | 独立 grep 复核 |
| 把运行层丢给徒弟自检 | 运行层只能用户/环境实跑，师傅主动索要报错/现象 |
| 过度拆分（任务小/耦合紧却拆了） | 默认不拆，只有任务确实跨独立模块/可并行才拆 |
| 集成徒弟失败不沉淀 | 集成失败必须沉淀根因（依赖判断错/文件边界错/接口不对齐） |
| 非 git 项目用 worktree | 非 git 项目退化为串行，无 worktree |

## 毕业标准

徒弟在纯徒弟会话连续通过 **N=5** 个同类**新 case**，每个均在 **K=1**（首轮裸做即过）通过三层：
- 静态层：`auto-pass`/`auto-fail` 全 pass
- 逻辑层：LLM rubric 全 pass
- 运行层：用户运行回填全 pass（无 pending）

任一 case 任一层失败 → 回退协作期，补 eval case 或强化硬红线。

## 多徒弟场景适配

### 错误沉淀

**沉淀时机**：
- 每个徒弟 part 失败 → 沉淀该徒弟的错
- 集成徒弟失败 → 沉淀集成失败的根因
- 师傅拆分判断错误（如应该串行但拆成并行）→ 沉淀拆分判断的错

**沉淀类型**：
- **part 级 case**：徒弟 part 犯的错（与现有 case 一致）
- **集成级 case**（`integrate-<seq>`）：集成徒弟犯的错（记录合并冲突/接口不对齐的模式）
- **拆分判断 case**（`decompose-<seq>`）：师傅拆分判断的错（记录依赖判断/文件边界划错的模式）

### 毕业标准

- 徒弟 part 级毕业：连续通过 N=5 个同类 part 级 case（与现有标准一致）
- 集成徒弟毕业：连续通过 N=3 个集成级 case（合并无冲突 / 整体跑通）
- 师傅拆分判断毕业：连续通过 N=3 个任务，拆分判断无错（依赖判断正确 / 文件边界无重叠）
