---
description: 师傅审查弱模型产出,走审查→沉淀→硬红线传承循环(师傅不当场亲手改)
argument-hint: <任务描述>
allowed-tools: ["Bash(${CLAUDE_PLUGIN_ROOT}/framework/*:*)", "Agent", "Skill", "Read", "Grep"]
---

用户要审查弱模型（主会话模型=师傅，Agent model:haiku=弱模型）产出做任务：**$ARGUMENTS**

按 `mentor-protocol` skill 走**审查 → 沉淀 → 硬红线传承**循环。核心铁律：师傅**不当场亲手改弱模型产出**——改了丢沉淀素材，且等于假设能当场教会一个无状态模型。错了就沉淀，靠硬红线传承到下次。

执行步骤：

1. **加载审查协议**：用 Skill 工具加载 `mentor-protocol`，理解审查循环 + 三层检查 + 理论基石（弱模型无状态不可训，硬红线内联进 prompt 是唯一传承通道）。

2. **spawn 弱模型试做**：`Agent({ model:"haiku", subagent_type:"general-purpose", prompt:<被审查产出模板> })`。prompt 按 skill 的「被审查产出的 prompt 模板（不给答案）」组装——只给【任务】+【崩溃级硬红线】（≤10 条），**不给答案、不强制预读 CHK**。要求返回：①改动清单 ②自检报告 ③不确定处。

3. **师傅三层审查产出**：
   - **静态层**：跑 <你的自动检查命令>（弱模型已自检，师傅独立 grep 复核，不信注释"已验证"）。**首选机器判**——绕过弱模型不可靠。
   - **逻辑层**：师傅对照 <领域 skill 规范> + 项目同类实现
   - **运行层**：标 pending-user，列出现象请用户运行验证（师傅跑不了的部分）

4. **fail → 沉淀**：任一层 fail，把这次错按 `docs/SOP-沉淀新case.md` 沉淀成 eval case（rubric=判定标准，expected=正解）。**不当场亲手改**——纠错发生在规范库的迭代里，不在当轮。

5. **晋升硬红线**：同类错反复 fail 的崩溃级 `## RED` → 晋升硬红线（≤10 条），下次 spawn 时内联进 prompt 头部（唯一传承通道）。

汇报格式：弱模型改了什么 / 三层审查结果（静态过没、逻辑对照结论、运行层待验证项）/ 是否沉淀新 case / 是否晋升硬红线。
