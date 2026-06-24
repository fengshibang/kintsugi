# shellcheck shell=bash
# evals 共享库 —— 被 runner.sh / judge.sh / run_all.sh source
# 依赖：claude CLI、bash、python3、GNU timeout（刻意不依赖 jq/lua）
#
# FRAMEWORK_DIR 按文件位置推算（插件内只读框架目录），不调用 git，这样即使
# runner cd 进临时 worktree 后本文件被重新 source，也不会误判框架目录。
# EVALS_DIR 由调用方显式注入（项目数据目录），脚本不猜 $PWD，保证插件只读可复用。

CLAUDE_BIN="${CLAUDE_BIN:-claude}"
TIMEOUT_SECS="${TIMEOUT_SECS:-300}"
BUDGET_USD="${BUDGET_USD:-0.25}"
RUN_MODEL="${RUN_MODEL:-}"
JUDGE_MODEL="${JUDGE_MODEL:-}"
PASS_THRESHOLD="${PASS_THRESHOLD:-0.8}"

FRAMEWORK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
: "${EVALS_DIR:?未设置 EVALS_DIR：请指向项目数据目录，如 <repo>/.claude/evals（例：EVALS_DIR=.claude/evals bash framework/run_all.sh）}"
REPO_ROOT="$(cd "$EVALS_DIR/../.." && pwd)"
RUNS_DIR="$EVALS_DIR/runs"
REPORT_DIR="$EVALS_DIR/report"

log()  { printf '\033[36m[evals]\033[0m %s\n' "$*" >&2; }
warn() { printf '\033[33m[evals]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[31m[evals error]\033[0m %s\n' "$*" >&2; exit 1; }

# 解析 case 目录参数为绝对路径：接受相对 .claude/evals 的路径或绝对路径
# 用法： resolve_case_dir "$1" => 将绝对路径赋给 CASE_DIR
resolve_case_dir() {
  local arg="$1"
  if [[ "$arg" = /* ]]; then
    CASE_DIR="$arg"
  else
    CASE_DIR="$EVALS_DIR/$arg"
  fi
  CASE_DIR="$(cd "$CASE_DIR" 2>/dev/null && pwd)" || die "case 目录不存在: $arg"
}

# 从 config.json（可选）读取字段，缺失返回默认值。用 python3 解析，避免依赖 jq。
# 用法： cfg_get "<case-dir>/config.json" "<key>" "<default>"
cfg_get() {
  local file="$1" key="$2" default="$3"
  [[ -f "$file" ]] || { printf '%s' "$default"; return; }
  python3 - "$file" "$key" "$default" <<'PY'
import json, sys, pathlib
f, key, default = sys.argv[1], sys.argv[2], sys.argv[3]
try:
    data = json.loads(pathlib.Path(f).read_text(encoding="utf-8"))
except Exception:
    print(default); sys.exit(0)
val = data.get(key, default)
if val is None:
    val = default
# JSON 布尔输出为小写 true/false（bash 用 [[ == "true" ]] 判断，区分大小写）
if isinstance(val, bool):
    print("true" if val else "false")
else:
    print(val)
PY
}
