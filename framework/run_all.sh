#!/usr/bin/env bash
# run_all.sh —— 批量跑所有 case（含可选 baseline）+ 汇总 + CI 门禁
# 用法: run_all.sh [target-filter]
#   target-filter  只跑 case 目录名含该子串的用例（如 jass-migrate）
# 环境变量: PASS_THRESHOLD（默认 0.8）门禁通过率阈值
# 退出码: 0=门禁通过，1=通过率低于阈值 / 有截断 / runner 或 judge 失败
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
# shellcheck source=lib/cli.sh
source lib/cli.sh

FILTER="${1:-}"
CASES=()
for d in "$EVALS_DIR"/cases/*/; do
  [[ -d "$d" ]] || continue
  cid="$(basename "$d")"
  [[ "$cid" == template* ]] && continue
  if [[ -n "$FILTER" && "$cid" != *"$FILTER"* ]]; then continue; fi
  CASES+=("cases/$cid")
done

[[ ${#CASES[@]} -gt 0 ]] || die "没有匹配的 case（filter=$FILTER）"
log "待跑 case: ${CASES[*]}"

FAIL=0
for c in "${CASES[@]}"; do
  cid="$(basename "$c")"
  log "========== $cid =========="
  DO_BASELINE="$(cfg_get "$EVALS_DIR/$c/config.json" baseline "false")"

  set +e
  NORMAL_DIR="$(./runner.sh "$c")"
  rc=$?
  set -e
  if [[ $rc -ne 0 ]]; then warn "runner(normal) 失败: $cid"; FAIL=1; continue; fi
  set +e; ./judge.sh "$c" "$NORMAL_DIR"; rc=$?; set -e
  [[ $rc -ne 0 ]] && { warn "judge(normal) 失败: $cid"; FAIL=1; }

  if [[ "$DO_BASELINE" == "true" ]]; then
    set +e
    BASE_DIR="$(./runner.sh "$c" --baseline)"
    rc=$?
    set -e
    if [[ $rc -ne 0 ]]; then warn "runner(baseline) 失败: $cid"; FAIL=1; continue; fi
    set +e; ./judge.sh "$c" "$BASE_DIR"; rc=$?; set -e
    [[ $rc -ne 0 ]] && { warn "judge(baseline) 失败: $cid"; FAIL=1; }
  fi
done

set +e; ./summarize.py; rc=$?; set -e
[[ $rc -ne 0 ]] && { warn "summarize 失败"; FAIL=1; }

# ---- CI 门禁 ----
python3 - "$EVALS_DIR/report/summary.json" "$PASS_THRESHOLD" "$FAIL" <<'PY'
import json, sys, pathlib
sp, thr, fail = sys.argv[1], float(sys.argv[2]), int(sys.argv[3])
try:
    summary = json.loads(pathlib.Path(sp).read_text(encoding="utf-8"))
except Exception as e:
    print(f"门禁: FAIL（读 summary.json 失败: {e}）"); sys.exit(1)
overall = summary.get("overall", {})
pass_rate = overall.get("pass_rate", 0.0)
truncated = overall.get("truncated", 0)
print(f"门禁: pass_rate={pass_rate:.1%}（阈值 {thr:.0%}）, truncated={truncated}, upstream_fail={fail}")
if fail or truncated > 0 or pass_rate < thr:
    reasons = []
    if fail: reasons.append("runner/judge/summarize 有失败")
    if truncated: reasons.append(f"{truncated} 次运行被截断")
    if pass_rate < thr: reasons.append(f"通过率 {pass_rate:.1%} < {thr:.0%}")
    print("门禁: FAIL → " + "; ".join(reasons))
    sys.exit(1)
print("门禁: PASS")
PY
