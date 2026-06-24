---
name: mentor-protocol
description: Use when supervising apprentice-model-produced code (apprentice is the doer spawned via Agent model:haiku, the main-session model via opus slot is the supervisor/mentor) — when apprentice output has runtime crashes, features not working, or convention violations, or when systematically improving apprentice quality via check/rework/case-sedimentation instead of one-off manual fixes. 领域中立，任何项目装上即用。
---

# 师徒协议 — 师傅监督徒弟（试错式沉淀）

## Overview

师傅**不亲自改代码**，而是**监督徒弟改**，在返工中把错误根因沉淀进 eval case 库（崩溃级错误晋升为硬红线）。机制补徒弟的**纪律**，不补能力——徒弟查得动源码，但不会每次都查；eval case 库把"偶尔想到"变成"每次必查"。

**模型路由**（用户 `~/.claude/settings.json` env 配置）：`opus` 槽 = 师傅（主会话/检查者），`haiku`/`sonnet` 槽 = 徒弟（子代理/产出者）。spawn 徒弟 = `Agent({ model:"haiku" })`，零额外配置。具体哪个模型占哪个槽由用户 env 决定，本协议只认这个抽象映射。

## When to Use

**启用**：徒弟产出的重复类任务（<你的重复任务领域>）有质量问题；用户说"带徒弟""监督返工""优化 skill"；徒弟代码出现运行崩溃 / 功能失效 / 规范违背。

**不启用**：探索调研、读码问答、紧急修复 → 师傅直接做。

## 核心循环

① 检查（师傅三层审徒弟产出，定位根因）→ ② 监督返工（师傅喂问题+判定标准+根因给徒弟，绝不亲手改）→ ③ 错误沉淀（这错值得沉淀成 eval case 吗？崩溃级/反复犯/CHK 未覆盖 → 入 cases/）→ 循环。

**灵魂动作**：徒弟每次犯错，师傅强制自问——"这错，值得沉淀成 eval case 吗？"

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

## 毕业标准

徒弟在纯徒弟会话连续通过 **N=5** 个同类**新 case**，每个均在 **K=1**（首轮裸做即过）通过三层：
- 静态层：`auto-pass`/`auto-fail` 全 pass
- 逻辑层：LLM rubric 全 pass
- 运行层：用户运行回填全 pass（无 pending）

任一 case 任一层失败 → 回退协作期，补 eval case 或强化硬红线。
