#!/usr/bin/env bash
# runner.sh —— 跑一个 eval case 的被测会话
# 用法: runner.sh <case-dir> [--baseline]
#   <case-dir>  相对 .claude/evals 的路径（如 cases/jass-migrate-001）或绝对路径
#   --baseline  禁用 Skill 工具，作为「无 skill」基线对照
#
# 默认在临时 git worktree 里隔离运行（config.json 的 isolate:false 可关），主仓库零污染。
# worktree 基于 HEAD（不含工作区 WIP），且会删掉 worktree 内的 .claude/evals，
# 防止被测 agent 偷看 expected.md 答案。
# 用 stream-json 输出，使预算超限被中断时仍能从已落盘的事件流里提取 tool_use。
# 产物落回主仓库 runs/<ts>-<case>{-baseline}/：
#   output.jsonl  原始事件流（stream-json，每行一个事件）
#   parsed.json   解析后的 {result, tool_uses, is_error, num_turns, cost_usd, stop_reason}
#   meta.json     运行元数据（含 truncated/is_error/tool_uses）
#   stderr.log    claude 的 stderr
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
# shellcheck source=lib/cli.sh
source lib/cli.sh

# ---- product 快照：把 worktree 里被测会话的改动文件复制到 run-dir/product/ ----
# 供 judge 的 auto 命令对真实产出判定（worktree 销毁后产物留存）。
export_snapshot() {
  local wt="$1" prod_dir="$2" changed_json="$3"
  mkdir -p "$prod_dir"
  git -C "$wt" add -A >/dev/null 2>&1 || true
  local changed=()
  while IFS= read -r -d '' f; do
    [[ -z "$f" ]] && continue
    changed+=("$f")
  done < <(git -C "$wt" diff --cached --name-only -z 2>/dev/null)
  local f
  for f in "${changed[@]+"${changed[@]}"}"; do
    # 排除 runner 机制性删除的 .claude/（防偷看 rm -rf .claude/evals），且只 cp 实际存在的文件（跳过删除项）
    [[ "$f" == .claude/* ]] && continue
    [[ -f "$wt/$f" ]] || continue
    mkdir -p "$prod_dir/$(dirname "$f")"
    cp "$wt/$f" "$prod_dir/$f" 2>/dev/null || true
  done
  "$PYTHON_BIN" - "$changed_json" "${changed[@]+"${changed[@]}"}" <<'PY'
import json, sys, pathlib
dst = sys.argv[1]
files = [x for x in sys.argv[2:] if x and not x.startswith('.claude/')]
pathlib.Path(dst).write_text(json.dumps(files, ensure_ascii=False, indent=2), encoding='utf-8')
PY
  git -C "$wt" reset -q >/dev/null 2>&1 || true
}

# 测试钩子：EXPORT_SNAPSHOT_ONLY=1 时用环境变量 WT/RUN_DIR/PRODUCT_DIR/CHANGED_JSON 跑快照后退出
if [[ "${EXPORT_SNAPSHOT_ONLY:-0}" == "1" ]]; then
  mkdir -p "$(dirname "$CHANGED_JSON")"
  export_snapshot "$WT" "$PRODUCT_DIR" "$CHANGED_JSON"
  log "快照(only)完成：$PRODUCT_DIR"
  exit 0
fi

[[ $# -ge 1 ]] || die "用法: runner.sh <case-dir> [--baseline]"
resolve_case_dir "$1"
shift || true

BASELINE=0
for a in "$@"; do [[ "$a" == "--baseline" ]] && BASELINE=1; done

CID="$(basename "$CASE_DIR")"
MODE="normal"; [[ $BASELINE -eq 1 ]] && MODE="baseline"

# config.json 覆盖（可选）
TIMEOUT_SECS="$(cfg_get "$CASE_DIR/config.json" timeout_secs "$TIMEOUT_SECS")"
BUDGET_USD="$(cfg_get "$CASE_DIR/config.json" budget_usd "$BUDGET_USD")"
CFG_MODEL="$(cfg_get "$CASE_DIR/config.json" model "")"
[[ -z "$CFG_MODEL" ]] && CFG_MODEL="$RUN_MODEL"
ISOLATE="$(cfg_get "$CASE_DIR/config.json" isolate "true")"

PROMPT_FILE="${PROMPT_FILE:-$CASE_DIR/prompt.md}"
[[ -f "$PROMPT_FILE" ]] || die "缺少 prompt: $PROMPT_FILE"

TS="$(date +%Y%m%d-%H%M%S)"
SUFFIX=""; [[ $BASELINE -eq 1 ]] && SUFFIX="-baseline"
RUN_DIR="$RUNS_DIR/${TS}-${CID}${SUFFIX}"
mkdir -p "$RUN_DIR"
OUT="$RUN_DIR/output.jsonl"

# ---- 隔离：临时 worktree（基于 HEAD，干净环境）----
WT=""
if [[ "$ISOLATE" == "true" ]]; then
  WT="/tmp/evals-wt-${CID}-$$"
  log "隔离运行：创建 worktree $WT（基于 HEAD）"
  git worktree add --detach "$WT" HEAD >/dev/null
  cleanup() {
    local rc=$?
    # 销毁 worktree 前，快照被测会话的改动文件到 product/（judge auto 命令需要）
    if [[ -n "$WT" && -d "$WT" ]]; then
      export_snapshot "$WT" "$RUN_DIR/product" "$RUN_DIR/changed_files.json"
    fi
    cd "$SCRIPT_DIR" 2>/dev/null || true
    git worktree remove --force "$WT" >/dev/null 2>&1 || true
    exit "$rc"
  }
  trap cleanup EXIT
  cd "$WT"
  # 删掉被测环境里的 evals（含 expected.md 答案），防止 agent 偷看；skill/workflows 保留
  rm -rf .claude/evals 2>/dev/null || true
fi

# ---- 组装命令（prompt 走 stdin，避免引号/长度问题）----
DISALLOWED=()
[[ $BASELINE -eq 1 ]] && DISALLOWED+=(--disallowedTools "Skill")

# config.json 的可选透传：MCP 配置 / 临时 settings / 额外目录（MCP、hook case 用）
MCP_CONFIG="$(cfg_get "$CASE_DIR/config.json" mcp_config "")"
SETTINGS="$(cfg_get "$CASE_DIR/config.json" settings "")"
mapfile -t ADD_DIRS < <("$PYTHON_BIN" - "$CASE_DIR/config.json" <<'PY'
import json, pathlib, sys
try:
    d = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
except Exception:
    d = {}
for x in d.get("add_dirs", []):
    print(x)
PY
)
EXTRA=()
[[ -n "$MCP_CONFIG" ]] && EXTRA+=(--mcp-config "$MCP_CONFIG")
[[ -n "$SETTINGS" ]]   && EXTRA+=(--settings "$SETTINGS")
for ad in "${ADD_DIRS[@]+"${ADD_DIRS[@]}"}"; do EXTRA+=(--add-dir "$ad"); done

log "运行 case=$CID mode=$MODE budget=\$${BUDGET_USD} timeout=${TIMEOUT_SECS}s isolate=$ISOLATE${EXTRA:+ (extra: ${EXTRA[*]})}"

START=$SECONDS
set +e
cat "$PROMPT_FILE" | timeout "$TIMEOUT_SECS" "$CLAUDE_BIN" -p \
  --output-format stream-json \
  --verbose \
  --permission-mode bypassPermissions \
  --max-budget-usd "$BUDGET_USD" \
  ${CFG_MODEL:+--model "$CFG_MODEL"} \
  --no-session-persistence \
  ${DISALLOWED[@]+"${DISALLOWED[@]}"} \
  ${EXTRA[@]+"${EXTRA[@]}"} \
  > "$OUT" 2> "$RUN_DIR/stderr.log"
EXIT_CODE=$?
set -e
WALL=$((SECONDS - START))

# ---- 解析 stream-json（多行事件流）→ parsed.json；判断是否被截断 ----
TRUNCATED=$("$PYTHON_BIN" - "$OUT" "$EXIT_CODE" "$RUN_DIR/parsed.json" <<'PY'
import json, sys, pathlib
src, ec, dst = sys.argv[1], int(sys.argv[2]), sys.argv[3]
result_text, tool_uses, is_error, num_turns, cost, stop_reason = "", [], False, 0, 0.0, ""
lines = pathlib.Path(src).read_text(encoding="utf-8", errors="replace").splitlines()
for line in lines:
    line = line.strip()
    if not line:
        continue
    try:
        ev = json.loads(line)
    except Exception:
        continue
    etype = ev.get("type")
    if etype == "assistant":
        for block in (ev.get("message") or {}).get("content", []):
            if isinstance(block, dict) and block.get("type") == "tool_use":
                tool_uses.append(block.get("name", ""))
    elif etype == "result":
        result_text = ev.get("result") or ""
        is_error = bool(ev.get("is_error"))
        num_turns = ev.get("num_turns", 0)
        cost = ev.get("total_cost_usd", 0.0)
        stop_reason = ev.get("stop_reason", "")
parsed = {
    "result": result_text, "tool_uses": tool_uses,
    "is_error": is_error, "num_turns": num_turns,
    "cost_usd": cost, "stop_reason": stop_reason,
    "raw_lines": len(lines),
}
pathlib.Path(dst).write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")
# 截断：外层 timeout(124) / 会话报错(is_error) / 既无文本产出也无任何工具调用
truncated = (ec == 124) or is_error or (not result_text and not tool_uses)
print("true" if truncated else "false")
PY
)

# ---- meta.json ----
"$PYTHON_BIN" - "$RUN_DIR/meta.json" "$CID" "$MODE" "$TIMEOUT_SECS" "$BUDGET_USD" "$EXIT_CODE" "$WALL" "$TRUNCATED" "$ISOLATE" "$RUN_DIR/parsed.json" <<'PY'
import json, sys, pathlib
(path, cid, mode, to, bud, ec, wall, trunc, iso, parsed_p) = sys.argv[1:11]
try:
    parsed = json.loads(pathlib.Path(parsed_p).read_text(encoding="utf-8"))
except Exception:
    parsed = {}
data = {
    "case": cid, "mode": mode,
    "baseline": mode == "baseline", "isolate": iso == "true",
    "timeout_secs": int(to), "budget_usd": float(bud),
    "exit_code": int(ec), "wall_secs": int(wall),
    "truncated": trunc == "true",
    "is_error": parsed.get("is_error", False),
    "num_turns": parsed.get("num_turns", 0),
    "cost_usd": parsed.get("cost_usd", 0.0),
    "tool_uses": parsed.get("tool_uses", []),
    "run_dir": str(pathlib.Path(path).parent),
}
pathlib.Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
PY

log "完成：$RUN_DIR (exit=$EXIT_CODE ${WALL}s turns=${TURNS:-?} truncated=$TRUNCATED)"
echo "$RUN_DIR"
