---
description: 带徒弟做任务,走师徒试错循环(师傅监督不亲自改)
argument-hint: <任务描述>
allowed-tools: ["Bash(${CLAUDE_PLUGIN_ROOT}/framework/*:*)", "Agent", "Skill", "Read", "Grep"]
---

用户要带徒弟（主会话模型=师傅，Agent model:haiku=徒弟）做任务：**$ARGUMENTS**

按 `mentor-protocol` skill 走**师徒试错循环**。核心铁律：师傅**绝不亲自改代码**，只监督徒弟改。

执行步骤：

1. **加载师傅协议**：用 Skill 工具加载 `mentor-protocol`，理解试错循环 + 三层检查 + 徒弟模板。

2. **spawn 徒弟裸做**：`Agent({ model:"haiku", subagent_type:"general-purpose", prompt:<徒弟模板> })`。徒弟 prompt 按 skill 的「徒弟 prompt 模板（试错版·不给答案）」组装——只给【任务】+【崩溃级硬红线】（≤10 条），**不给答案、不强制预读 CHK**，让徒弟裸做碰壁。要求徒弟返回：①改动清单 ②自检报告 ③不确定处。

3. **师傅三层审查徒弟产出**：
   - **静态层**：跑 <你的自动检查命令>（徒弟已自检，师傅独立 grep 复核，不信注释"已验证"）
   - **逻辑层**：师傅对照 <领域 skill 规范> + 项目同类实现
   - **运行层**：标 pending-user，列出现象请用户运行验证（师傅跑不了的部分）

4. **fail → 监督返工**：
   - 若该任务已有 eval case：
     `EVALS_DIR="$PWD/.claude/evals" bash "${CLAUDE_PLUGIN_ROOT}/framework/mentor-rework.sh" cases/<case-id>` 三阶段（R1摸索/R2给标准/R3给正解）
   - 否则：师傅喂【问题+判定标准】（不给正解）让徒弟改，最多 **K=3 轮**

5. **错误沉淀**：徒弟犯的值得记录的错（崩溃级 / 同类反复犯 / CHK 未覆盖的新坑），按 `docs/SOP-沉淀新case.md` 沉淀成 eval case。

6. 超 K 轮未通过 → 师傅接手完成，但**必须**把"为何反复失败"沉淀进 eval case。

汇报格式：徒弟改了什么 / 三层审查结果（静态过没、逻辑对照结论、运行层待验证项）/ 是否沉淀新 case / rework 轮次。
