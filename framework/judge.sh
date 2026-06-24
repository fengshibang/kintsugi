#!/usr/bin/env bash
# judge.sh —— 分层评判：static(auto) + logic(llm) + run(pending-user) + red 一票否决
# 用法:
#   judge.sh <case-dir> <run-dir>                 评判
#   judge.sh <case-dir> <run-dir> --merge-user    合并 user-verdict.json 回填 run 层
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
source lib/cli.sh

MERGE=0
case "${3:-}" in
  --merge-user) MERGE=1 ;;
  "") ;;
  *) die "未知参数: $3（仅支持 --merge-user）" ;;
esac

[[ $# -ge 2 ]] || die "用法: judge.sh <case-dir> <run-dir> [--merge-user]"
resolve_case_dir "$1"
RUN_DIR="$(cd "$2" && pwd)"
PARSED="$RUN_DIR/parsed.json"
RUBRIC="$CASE_DIR/rubric.md"
EXPECTED="$CASE_DIR/expected.md"
PRODUCT="$RUN_DIR/product"
CHANGED_JSON="$RUN_DIR/changed_files.json"
SCHEMA="$EVALS_DIR/rubrics/judge-schema.json"

[[ -f "$PARSED" ]] || die "找不到 parsed.json: $PARSED（先跑 runner.sh）"
[[ -f "$RUBRIC" ]] || die "缺少 rubric.md: $RUBRIC"

MODE="$(cfg_get "$RUN_DIR/meta.json" mode "unknown")"
JUDGE_MODEL_CFG="$(cfg_get "$CASE_DIR/config.json" judge_model "")"
[[ -z "$JUDGE_MODEL_CFG" ]] && JUDGE_MODEL_CFG="$JUDGE_MODEL"
CID="$(basename "$CASE_DIR")"

# 1) 解析 rubric
CHECKS_JSON="$(python3 "$EVALS_DIR/lib/rubric.py" "$RUBRIC")"
echo "$CHECKS_JSON" > "$RUN_DIR/rubric_parsed.json"

# 2) --merge-user 模式：直接读 user-verdict.json + 已有 score.json，重算
if [[ $MERGE -eq 1 ]]; then
  UV="$RUN_DIR/user-verdict.json"
  [[ -f "$UV" ]] || die "缺少 user-verdict.json: $UV"
  [[ -f "$RUN_DIR/score.json" ]] || die "缺少 score.json（先正常 judge 一次）"
  python3 - "$RUN_DIR/score.json" "$UV" "$RUN_DIR/score.json" "$CID" "$MODE" <<'PY'
import json, sys, pathlib, datetime
score_p, uv_p, out_p, cid, mode = sys.argv[1:6]
score = json.loads(pathlib.Path(score_p).read_text(encoding="utf-8"))
uv = json.loads(pathlib.Path(uv_p).read_text(encoding="utf-8"))
for c in score.get("checks", []):
    if c.get("judged_by") == "user" and c["id"] in uv:
        v = uv[c["id"]]
        c["pass"] = bool(v.get("pass"))
        c["note"] = f"user 回填：{v.get('note','')}"
red_fail = any(c.get("red_line") and not c["pass"] for c in score["checks"])
score["passed"] = (not red_fail) and all(c["pass"] for c in score["checks"])
non_p = [c for c in score["checks"]]
score["score"] = round(sum(1 for c in non_p if c["pass"])/len(non_p), 4) if non_p else 0.0
score["reason"] = (score.get("reason","") + " | user-verdict 已合并").strip(" |")
score["case_id"] = cid; score["mode"] = mode
score["timestamp"] = datetime.datetime.now().isoformat(timespec="seconds")
pathlib.Path(out_p).write_text(json.dumps(score, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"merged: passed={score['passed']} score={score['score']}")
PY
  log "user-verdict 已合并：$RUN_DIR/score.json"
  exit 0
fi

# 3) 静态层 auto 评判（在 product/ 下跑，注入 CHANGED_FILES）
mkdir -p "$PRODUCT"
CHANGED_FILES="$(python3 - "$CHANGED_JSON" <<'PY'
import json, sys, pathlib
p = sys.argv[1]
try: files = json.loads(pathlib.Path(p).read_text(encoding="utf-8"))
except Exception: files = []
print(" ".join(files))
PY
)"
AUTO_RESULTS="$RUN_DIR/auto_results.json"
python3 - "$CHECKS_JSON" "$PRODUCT" "$CHANGED_FILES" "$AUTO_RESULTS" <<'PY'
import json, sys, pathlib, subprocess, os
checks, prod, changed, out = sys.argv[1:5]
checks = json.loads(checks)
results = {}
for c in checks:
    if c['auto'] is None:
        continue
    cmd = c['auto']['cmd']
    kind = c['auto']['kind']
    env = {**os.environ, 'CHANGED_FILES': changed}
    try:
        r = subprocess.run(['bash', '-c', cmd], cwd=prod, env=env,
                           capture_output=True, text=True, timeout=60)
        exit0 = (r.returncode == 0)
    except Exception:
        exit0 = False
    verdict = exit0 if kind == 'pass' else (not exit0)
    results[c['id']] = verdict
pathlib.Path(out).write_text(json.dumps(results, ensure_ascii=False, indent=2))
PY
log "static(auto) 评判完成：$AUTO_RESULTS"

# 4) 逻辑层 LLM 评判（只传非 auto、非 run 的 logic checks 的 rubric 片段）
LOGIC_RUBRIC="$RUN_DIR/logic_rubric.md"
python3 - "$CHECKS_JSON" "$RUBRIC" "$LOGIC_RUBRIC" <<'PY'
import json, sys, pathlib
checks = json.loads(sys.argv[1])
logic_ids = {c['id'] for c in checks if c['auto'] is None and c['layer'] != 'run'}
full = pathlib.Path(sys.argv[2]).read_text(encoding="utf-8")
out = []
keep = False
for line in full.splitlines():
    if line.startswith("## CHECK ") or line.startswith("## RED "):
        cid = line.split()[2]
        keep = cid in logic_ids
    if keep:
        out.append(line)
pathlib.Path(sys.argv[3]).write_text("\n".join(out) + "\n", encoding="utf-8")
PY

LLM_RESULTS="$RUN_DIR/llm_results.json"
if [[ -s "$LOGIC_RUBRIC" ]]; then
  log "logic(llm) 评判 case=$CID"
  python3 - "$PARSED" "$LOGIC_RUBRIC" "$EXPECTED" <<'PY' | timeout "$TIMEOUT_SECS" "$CLAUDE_BIN" -p \
    --output-format json \
    --json-schema "$(cat "$SCHEMA")" \
    --disallowedTools "Bash" "Write" "Edit" "NotebookEdit" "Skill" \
    --append-system-prompt "你是严格的回归评分员。只根据 rubric 给 logic 层 checks 打分，禁止调用任何工具，只输出符合给定 JSON schema 的对象。" \
    ${JUDGE_MODEL_CFG:+--model "$JUDGE_MODEL_CFG"} \
    > "$RUN_DIR/judge_raw.json" 2> "$RUN_DIR/judge_stderr.log"
import json, sys, pathlib
parsed = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace"))
result = parsed.get("result", "")
tools = parsed.get("tool_uses", [])
rubric = pathlib.Path(sys.argv[2]).read_text(encoding="utf-8")
expected = pathlib.Path(sys.argv[3]).read_text(encoding="utf-8") if pathlib.Path(sys.argv[3]).exists() else ""
prompt = f"""# 任务
你是回归评分员。按 Rubric 逐条给 logic 层 checks 打分。

# Rubric
{rubric}

# 参考答案（上下文，非精确匹配）
{expected.strip() or '（无）'}

# 被测会话工具调用
{', '.join(tools) if tools else '（无）'}

# 被测会话最终输出
{result.strip() or '（空）'}

# 要求
- 对 Rubric 每个 CHECK/RED id 给 {{id, pass, note}}。
- 只输出符合 schema 的 JSON。
"""
sys.stdout.write(prompt)
PY
  python3 - "$RUN_DIR/judge_raw.json" "$LLM_RESULTS" <<'PY'
import json, sys, pathlib
raw = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace"))
obj = raw.get("structured_output") or {}
if not isinstance(obj, dict):
    import re
    s = (raw.get("result") or "").strip()
    s = re.sub(r"^```.*?$|```$", "", s, flags=re.M).strip()
    obj = json.loads(s)
res = {c["id"]: bool(c.get("pass")) for c in obj.get("checks", [])}
pathlib.Path(sys.argv[2]).write_text(json.dumps(res, ensure_ascii=False, indent=2))
PY
else
  echo '{}' > "$LLM_RESULTS"
  log "无 logic checks，跳过 LLM 评判"
fi

# 5) 合并：auto + llm + run(pending) + red 一票否决
MERGE_IN="$(python3 - "$RUN_DIR/rubric_parsed.json" "$AUTO_RESULTS" "$LLM_RESULTS" <<'PY'
import json, sys, pathlib
rubric = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
auto = json.loads(pathlib.Path(sys.argv[2]).read_text(encoding="utf-8"))
llm = json.loads(pathlib.Path(sys.argv[3]).read_text(encoding="utf-8"))
print(json.dumps({"rubric": rubric, "auto": auto, "llm": llm}, ensure_ascii=False))
PY
)"
printf '%s' "$MERGE_IN" | python3 "$EVALS_DIR/lib/judge_merge.py" > "$RUN_DIR/merge.json"

python3 - "$RUN_DIR/merge.json" "$RUN_DIR/score.json" "$CID" "$MODE" <<'PY'
import json, sys, pathlib, datetime
m = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
m["case_id"] = sys.argv[3]; m["mode"] = sys.argv[4]
m["timestamp"] = datetime.datetime.now().isoformat(timespec="seconds")
pathlib.Path(sys.argv[2]).write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"score={m['score']} passed={m['passed']} checks={len(m['checks'])}")
PY
log "评分完成：$RUN_DIR/score.json"
