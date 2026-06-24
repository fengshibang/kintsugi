---
description: 对fail的case跑三阶段渐进纠正(R1摸索/R2标准/R3正解)
argument-hint: <case-id 如 jass-migrate-001>
allowed-tools: ["Bash(${CLAUDE_PLUGIN_ROOT}/framework/*:*)", "Read"]
---

对 fail 的 eval case 跑三阶段渐进 rework，让徒弟在反馈中自学。case：`$ARGUMENTS`

执行：

1. 用 Bash 调：
   `EVALS_DIR="$PWD/.claude/evals" bash "${CLAUDE_PLUGIN_ROOT}/framework/mentor-rework.sh" cases/$ARGUMENTS`
   （可选 `--max-rounds N` 改轮数，默认 3）

2. `mentor-rework.sh` 会在 `$PWD/.claude/evals/runs/rework-<时间戳>-<case>/` 下产 `round-1/2/3/` + `rework-summary.json`。末行打印 rework 目录路径。

3. Read `rework-summary.json`，汇报：`passed_at_round`（第几轮通过，null=3轮未通过）/ `final_score` / `rounds_passed` / `pending_user_checks`。

4. 未通过 → 分析徒弟卡在哪类错，判断：是否沉淀新 case / 强化硬红线 / skill 表述缺陷。

run 层 pending 不参与 rework 反馈，独立走 `/mentor-kit:evals` 或 `judge.sh --merge-user`。
