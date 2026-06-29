#!/usr/bin/env python3
"""summarize.py —— 汇总 evals 运行结果 → report/report.md + report/summary.json

只依赖标准库（json/pathlib/statistics/collections/argparse/re）。
扫描 runs/*/<score|meta>.json，每个 (case, mode) 取最新一次运行，
计算每 case 分数/通过、baseline delta、按 target 分组、整体通过率，
并列出回归（带 skill 反而比基线差）。
"""
import json, re, sys, argparse, pathlib, statistics
from collections import defaultdict


def main():
    ap = argparse.ArgumentParser(description="汇总 evals 运行结果")
    ap.add_argument("--runs-dir", default=None, help="运行目录（默认 <script>/runs）")
    ap.add_argument("--out-dir", default=None, help="输出目录（默认 <script>/report）")
    args = ap.parse_args()

    here = pathlib.Path(__file__).resolve().parent
    runs_dir = pathlib.Path(args.runs_dir) if args.runs_dir else here / "runs"
    out_dir = pathlib.Path(args.out_dir) if args.out_dir else here / "report"
    out_dir.mkdir(parents=True, exist_ok=True)

    if not runs_dir.exists():
        print(f"运行目录不存在: {runs_dir}", file=sys.stderr)
        sys.exit(1)

    # 收集：{(cid, mode): [(dirname, dir, meta, score_p), ...]}
    runs = defaultdict(list)
    for d in sorted(runs_dir.glob("*")):
        if not d.is_dir():
            continue
        meta_p = d / "meta.json"
        if not meta_p.exists():
            continue
        try:
            meta = json.loads(meta_p.read_text(encoding="utf-8"))
        except Exception:
            continue
        cid = meta.get("case", d.name)
        mode = meta.get("mode", "normal")
        runs[(cid, mode)].append((d.name, d, meta, d / "score.json"))

    # 每个 (cid, mode) 取最新一次（目录名含时间戳，字典序即时间序）
    latest = {}
    for key, lst in runs.items():
        lst.sort(key=lambda x: x[0])
        dname, d, meta, score_p = lst[-1]
        latest[key] = {"dir": d, "meta": meta, "score_p": score_p}

    def load_score(rec):
        if not rec or not rec["score_p"].exists():
            return None
        try:
            return json.loads(rec["score_p"].read_text(encoding="utf-8"))
        except Exception:
            return None

    def has_pending(score):
        if not score:
            return False
        return any(c.get("judged_by") == "user" and not c.get("pass") and "pending" in (c.get("note") or "").lower()
                   for c in score.get("checks", []))

    target_of = lambda cid: re.sub(r"-\d+$", "", cid)

    all_cases = sorted({k[0] for k in latest})
    by_case_rows = []
    by_target = defaultdict(list)
    regressions = []

    for cid in all_cases:
        nrec = latest.get((cid, "normal"))
        brec = latest.get((cid, "baseline"))
        ns = load_score(nrec)
        bs = load_score(brec)
        n_score = ns.get("score") if ns else None
        b_score = bs.get("score") if bs else None
        delta = (n_score - b_score) if (n_score is not None and b_score is not None) else None
        passed = ns.get("passed") if ns else None
        incomplete_flag = has_pending(ns)
        if incomplete_flag:
            passed = None  # pending 视为未完成，不计入通过率
        truncated = nrec["meta"].get("truncated") if nrec else None
        row = {
            "case": cid, "target": target_of(cid), "mode": "normal",
            "score": n_score, "passed": passed,
            "baseline_score": b_score, "baseline_delta": delta,
            "truncated": truncated,
            "incomplete": incomplete_flag,
            "checks": ns.get("checks", []) if ns else [],
        }
        by_case_rows.append(row)
        by_target[row["target"]].append(row)
        if delta is not None and delta < 0:
            regressions.append({"case": cid, "delta": round(delta, 3),
                                "normal": round(n_score, 3), "baseline": round(b_score, 3)})

    incomplete = [{"case": r["case"], "target": r["target"]}
                  for r in by_case_rows if r.get("incomplete")]
    scored = [r for r in by_case_rows if r["score"] is not None and not r.get("incomplete")]
    overall = {
        "cases": len(by_case_rows),
        "scored": len(scored),
        "pass_rate": round(sum(1 for r in scored if r["passed"]) / len(scored), 3) if scored else 0.0,
        "avg_score": round(statistics.mean(r["score"] for r in scored), 3) if scored else 0.0,
        "with_baseline": sum(1 for r in by_case_rows if r["baseline_score"] is not None),
        "truncated": sum(1 for r in by_case_rows if r.get("truncated")),
    }

    target_summary = {}
    for t, rows in by_target.items():
        s = [r for r in rows if r["score"] is not None and not r.get("incomplete")]
        target_summary[t] = {
            "cases": len(rows),
            "pass_rate": round(sum(1 for r in s if r["passed"]) / len(s), 3) if s else 0.0,
            "avg_score": round(statistics.mean(r["score"] for r in s), 3) if s else 0.0,
        }

    summary = {
        "overall": overall,
        "by_target": target_summary,
        "by_case": by_case_rows,
        "regressions": regressions,
        "incomplete": incomplete,
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---- report.md ----
    def fmt(x):
        if x is None:
            return "—"
        if isinstance(x, bool):
            return "✓" if x else "✗"
        if isinstance(x, float):
            return f"{x:.3f}"
        return str(x)

    lines = ["# Evals 报告", "", "## 概览", ""]
    lines.append(f"- 用例数: {overall['cases']}（已评分 {overall['scored']}）")
    lines.append(f"- 通过率: {overall['pass_rate']:.1%}")
    lines.append(f"- 平均分: {overall['avg_score']:.3f}")
    lines.append(f"- 含基线对比: {overall['with_baseline']}")
    if overall["truncated"]:
        lines.append(f"- ⚠️ 被截断的运行: {overall['truncated']}（timeout/预算溢出，结果不可信）")
    lines += ["", "## 各用例", "",
              "| case | target | score | passed | baseline | Δ | truncated |",
              "|---|---|---|---|---|---|---|"]
    for r in by_case_rows:
        delta = f"{r['baseline_delta']:+.3f}" if r["baseline_delta"] is not None else "—"
        lines.append(f"| {r['case']} | {r['target']} | {fmt(r['score'])} | "
                     f"{fmt(r['passed'])} | {fmt(r['baseline_score'])} | {delta} | {r.get('truncated')} |")

    lines += ["", "## 按 target 分组", "",
              "| target | cases | pass_rate | avg_score |", "|---|---|---|---|"]
    for t, s in sorted(target_summary.items()):
        lines.append(f"| {t} | {s['cases']} | {s['pass_rate']:.1%} | {s['avg_score']:.3f} |")

    if regressions:
        lines += ["", "## ⚠️ 回归（带 skill 反而比基线差）", "",
                  "| case | Δ | normal | baseline |", "|---|---|---|---|"]
        for r in regressions:
            lines.append(f"| {r['case']} | {r['delta']:+.3f} | {r['normal']:.3f} | {r['baseline']:.3f} |")

    if incomplete:
        lines += ["", "## ⏳ 未完成（含 pending-user，待双跑回填）", "",
                  "| case | target |", "|---|---|"]
        for c in incomplete:
            lines.append(f"| {c['case']} | {c['target']} |")

    (out_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"已生成: {out_dir / 'report.md'}")
    print(f"已生成: {out_dir / 'summary.json'}")
    print(f"通过率 {overall['pass_rate']:.1%}（{overall['scored']} 已评分）")


if __name__ == "__main__":
    main()
