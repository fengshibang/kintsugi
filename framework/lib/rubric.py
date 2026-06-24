#!/usr/bin/env python3
"""rubric.py —— 解析 rubric.md 为结构化 checks（见 spec §5）。

语法：
  ## CHECK <id>   [layer=static|logic|run]   普通检查（layer 缺省=logic）
  ## RED <id>     [layer=...]                 崩溃级硬线（一票否决）
  auto-pass: <cmd>                            static 机器判定（exit0=pass）
  auto-fail: <cmd>                            static 机器判定（exit0=fail）

auto-* 必须紧跟所属 check 标题之后的正文段内。输出 JSON 数组：
  [{id, kind:"check"|"red", layer, auto:{kind,cmd}|null, desc}]
仅依赖标准库。
"""
import json, re, sys, pathlib

_HEAD = re.compile(r'^##\s+(CHECK|RED)\s+(\S+)(.*)$')
_AUTO = re.compile(r'^\s*auto-(pass|fail):\s*(.*)$')
_LAYER = re.compile(r'layer=(static|logic|run)')


def parse_rubric(text):
    checks, cur, body = [], None, []

    def flush():
        nonlocal cur, body
        if cur is not None:
            cur['desc'] = '\n'.join(body).strip()
            checks.append(cur)
        cur, body = None, []

    for line in text.splitlines():
        m = _HEAD.match(line)
        if m:
            flush()
            kind_tok, cid, rest = m.groups()
            lm = _LAYER.search(rest)
            cur = {
                'id': cid,
                'kind': 'red' if kind_tok == 'RED' else 'check',
                'layer': lm.group(1) if lm else 'logic',
                'auto': None,
            }
            body = []
            continue
        am = _AUTO.match(line)
        if am and cur is not None:
            ak, acmd = am.groups()
            cur['auto'] = {'kind': ak, 'cmd': acmd.strip()}
            continue
        if cur is not None:
            body.append(line)
    flush()
    return checks


def main():
    if len(sys.argv) < 2:
        print('用法: rubric.py <rubric.md>', file=sys.stderr)
        sys.exit(2)
    text = pathlib.Path(sys.argv[1]).read_text(encoding='utf-8')
    print(json.dumps(parse_rubric(text), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
