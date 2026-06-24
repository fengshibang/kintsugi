#!/usr/bin/env bash
# mentor-rework.sh —— 三阶段渐进 rework 循环（R1摸索/R2给标准/R3全给），最多 K 轮
# 用法: mentor-rework.sh <case-dir> [--max-rounds N] [--baseline]
# 产物: <run-dir>/rework/round-{1..K}/{...} + rework-summary.json
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
# shellcheck source=lib/cli.sh
source lib/cli.sh

[[ $# -ge 1 ]] || die "用法: mentor-rework.sh <case-dir> [--max-rounds N] [--baseline]"
resolve_case_dir "$1"; shift || true

MAX_ROUNDS=3; BASELINE=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --max-rounds) MAX_ROUNDS="$2"; shift 2 ;;
    --baseline) BASELINE=1; shift ;;
    *) die "未知参数: $1" ;;
  esac
done

CID="$(basename "$CASE_DIR")"
[[ -f "$CASE_DIR/prompt.md" ]] || die "缺少 prompt.md"
[[ -f "$CASE_DIR/rubric.md" ]] || die "缺少 rubric.md"
EXPECTED_FILE="$CASE_DIR/expected.md"
RUBRIC_PARSED="$(python3 "$EVALS_DIR/lib/rubric.py" "$CASE_DIR/rubric.md")"

REWORK_DIR="$RUNS_DIR/rework-$(date +%Y%m%d-%H%M%S)-$CID"
mkdir -p "$REWORK_DIR"
log "rework 开始：case=$CID max_rounds=$MAX_ROUNDS → $REWORK_DIR"

declare -a ROUND_PASSED=()
PASSED_AT="null"; FINAL_SCORE="null"; PENDING_CHECKS="[]"

for ((R=1; R<=MAX_ROUNDS; R++)); do
  ROUND_DIR="$REWORK_DIR/round-$R"
  mkdir -p "$ROUND_DIR"

  # ---- 组装该轮反馈 prompt（用 python 读文件构造 JSON，避免 shell 转义问题）----
  PREV_SCORE_FILE=""
  if [[ $R -ge 2 ]]; then
    PREV="$REWORK_DIR/round-$((R-1))/score.json"
    [[ -f "$PREV" ]] && PREV_SCORE_FILE="$PREV"
  fi

  # 用 python 构造 JSON 输入（heredoc 绑第一个 python3 读脚本），命令替换捕获 stdout，再 pipe 给 rework_stages.py
  STAGE_IN="$(python3 - "$R" "$CASE_DIR/prompt.md" "$EXPECTED_FILE" "$RUBRIC_PARSED" "$PREV_SCORE_FILE" <<'PY'
import json, sys, pathlib
rnd = int(sys.argv[1])
prompt_path = sys.argv[2]
expected_path = sys.argv[3]
rubric = json.loads(sys.argv[4])
prev_score_file = sys.argv[5]
base = pathlib.Path(prompt_path).read_text(encoding="utf-8")
try:
    expected = pathlib.Path(expected_path).read_text(encoding="utf-8")
except Exception:
    expected = ""
last = None
if prev_score_file:
    try:
        last = json.loads(pathlib.Path(prev_score_file).read_text(encoding="utf-8"))
    except Exception:
        last = None
print(json.dumps({"round": rnd, "base_prompt": base, "rubric": rubric,
                  "last_score": last, "expected": expected}))
PY
)"
  printf '%s' "$STAGE_IN" | python3 "$EVALS_DIR/lib/rework_stages.py" > "$ROUND_DIR/prompt.md"

  # ---- 跑 runner（PROMPT_FILE 覆盖 prompt）----
  BL_ARG=""
  [[ $BASELINE -eq 1 ]] && BL_ARG="--baseline"
  RUN_DIR_R=""
  export PROMPT_FILE="$ROUND_DIR/prompt.md"
  if ! RUN_DIR_R="$(./runner.sh "$CASE_DIR" $BL_ARG)"; then
    warn "round $R runner 失败"
    ROUND_PASSED+=("error")
    unset PROMPT_FILE
    continue
  fi

  # 复制 runner 产物到 round 目录
  if [[ -n "$RUN_DIR_R" && -d "$RUN_DIR_R" ]]; then
    cp -r "$RUN_DIR_R/." "$ROUND_DIR/" 2>/dev/null || true
  fi

  # ---- judge 评判 ----
  if [[ -n "$RUN_DIR_R" && -d "$RUN_DIR_R" ]]; then
    ./judge.sh "$CASE_DIR" "$RUN_DIR_R" >/dev/null 2>&1 || warn "round $R judge 失败"
    if [[ -f "$RUN_DIR_R/score.json" ]]; then
      cp "$RUN_DIR_R/score.json" "$ROUND_DIR/score.json"
    fi
  fi

  unset PROMPT_FILE

  # ---- 解析 score.json ----
  SCORE_FILE="$ROUND_DIR/score.json"
  if [[ -f "$SCORE_FILE" ]]; then
    read -r PASSED_R SCORE_R PENDING_R < <(python3 - "$SCORE_FILE" <<'PY'
import json, sys, pathlib
try:
    s = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
    pend = [c["id"] for c in s.get("checks", []) if c.get("judged_by") == "user"]
    print(s.get("passed", False), s.get("score", 0), json.dumps(pend, ensure_ascii=False))
except Exception:
    print(False, 0, "[]")
PY
)
  else
    PASSED_R="False"; SCORE_R=0; PENDING_R="[]"
  fi

  ROUND_PASSED+=("$PASSED_R")
  if [[ "$PASSED_R" == "True" ]]; then
    PASSED_AT="$R"; FINAL_SCORE="$SCORE_R"
    log "round $R：全部通过！score=$SCORE_R"
    break
  fi
  FINAL_SCORE="$SCORE_R"; PENDING_CHECKS="$PENDING_R"
  log "round $R：passed=$PASSED_R score=$SCORE_R"
done

# ---- 写 rework-summary.json ----
python3 - "$REWORK_DIR/rework-summary.json" "$CID" "$MAX_ROUNDS" "$PASSED_AT" \
  "$FINAL_SCORE" "$PENDING_CHECKS" "${ROUND_PASSED[@]}" <<'PY'
import json, sys, pathlib
out, cid, mx, passed_at, final, pending = sys.argv[1:7]
rounds = sys.argv[7:]
data = {
    "case": cid, "max_rounds": int(mx),
    "passed_at_round": (int(passed_at) if passed_at != "null" else None),
    "final_score": (float(final) if final != "null" else None),
    "rounds_passed": [r == "True" for r in rounds],
    "pending_user_checks": json.loads(pending) if pending else [],
}
pathlib.Path(out).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"rework 完成：passed_at_round={data['passed_at_round']} final_score={data['final_score']}", file=sys.stderr)
PY

log "rework 汇总：$REWORK_DIR/rework-summary.json"
echo "$REWORK_DIR"
