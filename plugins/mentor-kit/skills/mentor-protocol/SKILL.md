---
name: mentor-protocol
description: Use when reviewing weak-model-produced code (weak model is the doer spawned via Agent model:haiku; main-session strong model is the reviewer) — review its output for runtime crashes / features not working / convention violations, sediment errors into eval cases, and promote recurring crash-level failures into hard red-lines inlined into the spawn prompt. Does NOT train the doer (it's stateless, weights frozen). 领域中立，任何项目装上即用。
---

# 审查协议 — 师傅审查弱模型产出 + 硬红线传承

## Overview

师傅（主会话强模型）**审查**弱模型（子代理 `Agent({model:"haiku"})`）的产出，把错误根因沉淀进 eval case 库，反复 fail 的崩溃级模式**晋升为硬红线**，内联进 spawn prompt——这是唯一能影响下一次弱模型产出的通道。

**为什么不叫"训练徒弟"**：弱模型无状态、权重不可调，每次 spawn 都从零开始，eval 库沉淀的教训不会自动进入它下一次的上下文——**它不可训练**。本机制迭代的是**师傅手里的规范库**（审查 rubric + 硬红线），不是弱模型本身。

**理论基石**：in-context 注入对弱模型只有一条可靠通道——把 ≤10 条硬红线内联进 spawn prompt 头部。长 skill 正文、指望弱模型自觉加载 skill——基本失效（它不会主动想起来加载，加载了也遵循不全）。所以：
- 审查纪律补在**师傅**身上（每次审查走三层 + 灵魂动作）——有效；
- 硬红线补在**弱模型**身上（内联进 prompt）——唯一可靠的传承窄路。

**模型路由**（用户 `~/.claude/settings.json` env 配置）：`opus` 槽 = 师傅（主会话/审查者），`haiku`/`sonnet` 槽 = 弱模型（子代理/产出者）。spawn = `Agent({ model:"haiku" })`。具体哪个模型占哪个槽由用户 env 决定，本协议只认这个抽象映射。

## When to Use

**启用**：弱模型产出的重复类任务有质量问题；弱模型产出出现运行崩溃 / 功能失效 / 规范违背；要把某类反复错误固化成回归 case。

**不启用**：探索调研、读码问答、紧急修复 → 师傅直接做。

## 核心循环

① **审查**（师傅三层审弱模型产出，定位根因）→ ② **沉淀**（这错值得沉淀成 eval case 吗？崩溃级/反复犯/CHK 未覆盖 → 入 cases/）→ ③ **晋升**（反复 fail 的 `## RED` → 硬红线，≤10 条）→ ④ **传承**（硬红线内联进下次 spawn prompt）→ 循环。eval 回归（`run_all.sh`）验证硬红线库覆盖率是否 ↑。

**灵魂动作**：弱模型每次犯错，师傅强制自问——"这错，值得沉淀成 eval case 吗？"

> 单轮产出错了，师傅**不当场亲手改**（那样既丢沉淀素材、又假设能当场教会一个无状态模型）。而是沉淀成 case，靠硬红线传承到下一轮。纠错发生在规范库的迭代里，不在当轮。

## 三层检查（不同问题用不同手段）

| 层 | 问题类型 | 手段 | 执行者 |
|---|---|---|---|
| 静态 | 规范/API 违背 | judge.sh `auto-pass`/`auto-fail`（**首选**，绕过弱模型不可靠）+ 弱模型自检 | 机器判 |
| 逻辑 | 功能不对 | 师傅对照 <领域 skill 规范> + 项目同类实现深审 | 师傅 |
| 运行 | 崩溃/报错 | <你的运行验证手段，如跑测试/跑应用> | **用户**（师傅跑不了的部分） |

任一层失败 → 沉淀成 case（见核心循环 ②）。**静态 auto 是首选**：它直接验产物，不依赖弱模型"听话"，是唯一绕过弱模型指令遵循短板的层——case 的 rubric 应优先用 `auto-pass/auto-fail`，把 `logic`（LLM judge）留给无法机器判的项。

## 被审查产出的 prompt 模板（不给答案）

子代理不一定可靠加载 skill，必须兜底。**不给预设答案、不强制预读 CHK 清单**——只给任务 + 硬红线，让弱模型试做：

```
【任务】<具体目标 + <基线参照（如 基线文件:行号 / 验收标准）>>
【崩溃级硬红线】<仅极少数会导致静默失效/全局崩的硬约束，从 §硬红线清单 取，≤10 条；其余一律不给。这是唯一能约束本次产出的通道>
【自检】产出后跑 <你的自动检查命令>，报告一并返回
【输出】①改动清单 ②自检报告 ③不确定处明确标出
```

> 硬红线内联进 prompt 头部 = 本机制唯一传给无状态弱模型的窄路。skill 长文、CHK 清单它读不到 / 遵循不全，别指望。

## 硬红线清单（崩溃级，≤10 条，从 eval 案例晋升）

> 不预先堆砌。从 eval 库"反复 fail 且代价=静默失效/全局崩"的 `## RED` check 晋升。
> 超 10 条 = skill 表述缺陷，重构而非新增。

（初始为空，随 eval 案例积累由师傅提炼填充）

## Quick Reference

| 操作 | 命令/位置 |
|---|---|
| 批量回归（验证硬红线覆盖率） | `EVALS_DIR=<数据目录> bash "${CLAUDE_PLUGIN_ROOT}/framework/run_all.sh" [filter]` |
| 运行层回填 | run-dir 放 `user-verdict.json` → `bash "${CLAUDE_PLUGIN_ROOT}/framework/judge.sh" <case> <run-dir> --merge-user` |
| 沉淀新 case | 流程见 `docs/SOP-沉淀新case.md` |
| 评判标准语法 | `## CHECK/RED <id> [layer=static|logic|run]` + `auto-pass/auto-fail:`（见 `framework/lib/rubric.py`） |

## Common Mistakes

| 错误 | 纠正 |
|---|---|
| 指望弱模型"学会" | 它无状态不可训——迭代的是师傅规范库（rubric + 硬红线），不是弱模型 |
| 把硬红线写在 skill 长文里指望弱模型读 | 必须内联进 spawn prompt 头部——长文它读不到 / 遵循不全 |
| 师傅当场亲手改弱模型产出 | 丢掉沉淀素材；应沉淀成 case，靠硬红线传承到下次 |
| 只做静态检查就放行 | 必过逻辑层(对照领域规范) + 运行层(用户实跑) |
| rubric 全用 logic 层（LLM judge） | 能 `auto-pass/auto-fail` 机器判的优先机器判——绕过弱模型短板，降 judge 成本与方差 |
| 修了错不沉淀 | 每个错必走灵魂动作 → 沉淀成 eval case（入 cases/） |
| 盲信弱模型注释"已验证" | 独立 grep 复核 |
| 把运行层丢给弱模型自检 | 运行层只能用户/环境实跑，师傅主动索要报错/现象 |
