#!/usr/bin/env python3
"""rework_stages.py —— 组装三阶段渐进反馈 prompt（见 spec §7）。

stdin 输入 JSON：{round, base_prompt, rubric:[...], last_score:{checks:[...]}, expected}
stdout 输出：该轮反馈 prompt 文本。
- R1：仅 base_prompt（摸索）
- R2：base + fail 的 static/logic checks 的判定标准（不给根因/正解）
- R3：R2 + 每个 fail 的根因提示 + expected 正解
run 层 pending 不参与反馈。
"""
import json, sys


def build(data):
    rnd = data['round']
    base = data['base_prompt']
    rubric = data['rubric']
    last = data.get('last_score') or {}
    expected = data.get('expected') or ''
    rubric_by_id = {c['id']: c for c in rubric}

    if rnd == 1 or not last:
        return base

    fail_checks = [c for c in last.get('checks', [])
                   if not c.get('pass') and c.get('judged_by') != 'user']
    lines = [base, '',
             '---', '上一轮以下检查未通过，请修正后重做：']
    for c in fail_checks:
        rc = rubric_by_id.get(c['id'], {})
        lines.append(f"- [{c['id']}] {rc.get('desc','（无判定标准）').strip()}")
        if rnd >= 3:
            lines.append(f"    根因提示：请重点排查此项；参考正解见下方。")
    if rnd >= 3 and expected:
        lines += ['', '---', '参考正解：', expected.strip()]
    return '\n'.join(lines)


if __name__ == '__main__':
    print(build(json.load(sys.stdin)))
