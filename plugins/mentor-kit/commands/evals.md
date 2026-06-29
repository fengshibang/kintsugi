---
description: 跑eval回归看通过率/baseline delta/skill增益
argument-hint: [领域filter 如 buff/system/migrate; 留空跑全部]
allowed-tools: ["Bash(${CLAUDE_PLUGIN_ROOT}/framework/*:*)", "Read"]
---

跑 eval 回归，量化 skill 是否变好。参数：`$ARGUMENTS`（领域 filter；留空跑全部 case）。

执行：

1. 用 Bash 跑（worktree 隔离由 runner 内部处理，主仓库零污染）：
   - 留空：`EVALS_DIR="$PWD/.claude/evals" bash "${CLAUDE_PLUGIN_ROOT}/framework/run_all.sh"`
   - 有 filter：`EVALS_DIR="$PWD/.claude/evals" bash "${CLAUDE_PLUGIN_ROOT}/framework/run_all.sh" $ARGUMENTS`

2. 跑完 Read `$PWD/.claude/evals/report/report.md` 和 `report/summary.json`，汇报：
   - **整体通过率**（CI 门禁阈值 `PASS_THRESHOLD=0.8`）
   - 每 case 的 **baseline delta**（normal − baseline：>0 = skill 正向增益；<0 = 回归）
   - 截断 / runner·judge 失败的 case
   - CI 门禁 PASS / FAIL

3. 若通过率低于阈值或有回归 case：分析是 skill 退化还是 case 内容问题，给改进建议。

注意：每个开 `baseline:true` 的 case 会跑两次（normal + 禁用 Skill 基线），成本约翻倍；`run_all.sh` 退出码 0=门禁通过，1=未过。
