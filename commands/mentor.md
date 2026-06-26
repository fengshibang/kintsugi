---
description: 带徒弟做任务,走师徒试错循环(师傅监督不亲自改)
argument-hint: <任务描述>
allowed-tools: ["Bash(${CLAUDE_PLUGIN_ROOT}/framework/*:*)", "Bash(git worktree:*)", "Bash(git merge:*)", "Bash(git checkout:*)", "Bash(git branch:*)", "Agent", "Skill", "Read", "Grep"]
---

用户要带徒弟（主会话模型=师傅，Agent model:haiku=徒弟）做任务：**$ARGUMENTS**

按 `mentor-protocol` skill 走**师徒试错循环**。核心铁律：师傅**绝不亲自改代码**，只监督徒弟改。

执行步骤：

0. **拆分判断**（默认不拆）：
   - 判断任务是否需要拆分（跨独立模块/可并行/规模大）
   - 不拆 → 走步骤 1-6（现有 mentor-protocol 一对一流程）
   - 拆 → 走步骤 1'-8'（多徒弟编排流程，见下方）

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

### 多徒弟编排流程（拆分时）

1'. **师傅输出 decomposition 计划**：JSON 格式（part 列表、依赖关系、并行组）

2'. **师傅创建 worktree + 并行 spawn 多个徒弟**：师傅先手动 `git worktree add <path> -b <branch>` 创建 N 个 worktree（每个 worktree 一个命名分支），然后并行 spawn 徒弟：`Agent({ model:"haiku", subagent_type:"general-purpose", prompt:<徒弟模板> })`（prompt 里传 worktree 路径 + 分支名）。每个徒弟只负责一个 part，在各自 worktree 的命名分支上 commit。

3'. **师傅逐个三层审查**：每个徒弟完成后，师傅独立三层审查（静态/逻辑/运行）

4'. **fail → 监督返工**：每个徒弟独立走 rework 三阶段（R1/R2/R3），互不影响

5'. **审完所有 part → spawn 集成徒弟**：`Agent({ model:"haiku", subagent_type:"general-purpose", prompt:<集成徒弟模板> })`。集成徒弟负责逐个 `git merge <branch-N>` 到默认分支合并所有 part + 解决冲突 + 跑通整体。

6'. **师傅对集成徒弟产出做最终三层审查**：三层审查（静态：合并无冲突 / 逻辑：接口对齐 / 运行：整体跑通）

7'. **错误沉淀**：
   - 每个徒弟 part 失败 → 沉淀 part 级 case
   - 集成徒弟失败 → 沉淀集成级 case（`integrate-<seq>`）
   - 师傅拆分判断错误 → 沉淀拆分判断 case（`decompose-<seq>`）

8'. **集成徒弟失败 → 师傅接手**：师傅必须沉淀"为何集成失败"（依赖判断错/文件边界错/接口不对齐）

9'. **清理**：师傅清理所有 part worktree（`git worktree remove <path>`）+ 删除已合并的 part 分支（`git branch -d <part-N>`）

汇报格式：徒弟改了什么 / 三层审查结果（静态过没、逻辑对照结论、运行层待验证项）/ 是否沉淀新 case / rework 轮次。

**多徒弟场景汇报格式**：
- decomposition 计划（JSON）
- 每个徒弟的改动清单 + 三层审查结果
- 集成徒弟的合并日志 + 冲突解决记录 + 整体验证结果
- 是否沉淀新 case（part 级/集成级/拆分判断级）
- rework 轮次（每个徒弟各自统计）
