#!/usr/bin/env python3
"""judge_merge.py —— 合并 auto/llm 评判结果 + red 一票否决 + run pending。

stdin 输入 JSON：{rubric:[...], auto:{id:bool}, llm:{id:bool}}
stdout 输出：{score, passed, checks:[{id,pass,note,layer,red_line,judged_by}], reason}
"""
import json, sys


def merge(data):
    rubric = data['rubric']
    auto = data.get('auto', {})
    llm = data.get('llm', {})
    checks, pending, red_fail = [], [], False

    for c in rubric:
        cid, layer = c['id'], c['layer']
        is_red = c['kind'] == 'red'
        if c['auto'] is not None:  # static 机器判
            verdict = bool(auto.get(cid))
            checks.append({'id': cid, 'pass': verdict, 'layer': layer,
                           'red_line': is_red, 'judged_by': 'auto',
                           'note': f"auto-{c['auto']['kind']} {'pass' if verdict else 'fail'}"})
            if is_red and not verdict:
                red_fail = True
        elif layer == 'run':  # 待用户双跑
            checks.append({'id': cid, 'pass': False, 'layer': layer,
                           'red_line': is_red, 'judged_by': 'user',
                           'note': 'pending-user：待双跑地图回填'})
            pending.append(cid)
        else:  # logic LLM 判
            verdict = bool(llm.get(cid))
            checks.append({'id': cid, 'pass': verdict, 'layer': layer,
                           'red_line': is_red, 'judged_by': 'llm',
                           'note': 'llm 评判'})
            if is_red and not verdict:
                red_fail = True

    non_pending = [c for c in checks if c['judged_by'] != 'user']
    score = (sum(1 for c in non_pending if c['pass']) / len(non_pending)) if non_pending else 0.0
    fail_ids = [c['id'] for c in checks if not c['pass']]
    reasons = []
    if red_fail:
        reasons.append(f"红线失败：{[c['id'] for c in checks if c['red_line'] and not c['pass']]}")
    if pending:
        reasons.append(f"待用户回填(pending-user)：{pending}")
    if fail_ids and not red_fail:
        reasons.append(f"未通过项：{fail_ids}")
    if not reasons:
        reasons.append('全部通过')
    passed = (not red_fail) and (not pending) and all(c['pass'] for c in non_pending)
    return {'score': round(score, 4), 'passed': passed, 'checks': checks, 'reason': '; '.join(reasons)}


if __name__ == '__main__':
    data = json.load(sys.stdin)
    print(json.dumps(merge(data), ensure_ascii=False, indent=2))
