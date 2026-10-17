#!/usr/bin/env python3
"""
analyzer.py - JASS → ECS 迁移全局分析工具

解析 war3map.j，生成：
1. 触发器清单（按事件类型分组、行数、复杂度评分）
2. 依赖图（变量引用、hashtable 共享关系）
3. 问题标记（泄漏、null 安全、PolledWait、死代码）
4. 迁移 PRD 文档

用法:
    python3 analyzer.py <war3map.j路径> [--output <输出路径>] [--strategy <策略>]
    python3 analyzer.py --help

策略选项:
    event-type    - 按事件类型分批
    complexity    - 从简到繁
    severity      - 按问题严重度
"""

import re
import sys
import os
import argparse
from datetime import date

# Windows GBK 控制台无法编码输出中的 emoji，统一切到 UTF-8
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, 'reconfigure'):
        try:
            _stream.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass
from collections import defaultdict, Counter

# 导入 API 分类（与 extract_trigger.py 共享）
sys.path.insert(0, os.path.dirname(__file__))
try:
    from extract_trigger import API_CATEGORIES
except ImportError:
    API_CATEGORIES = {}

# ============================================================
# JASS 解析器
# ============================================================

def parse_functions(content):
    """提取所有函数名和起止行"""
    functions = []
    lines = content.split('\n')
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('function ') and 'takes' in stripped:
            name = stripped.split('function ')[1].split('takes')[0].strip()
            start = i
            # 找到 endfunction
            for j in range(i + 1, len(lines)):
                if lines[j].strip() == 'endfunction':
                    functions.append({
                        'name': name,
                        'start_line': i + 1,  # 1-based
                        'end_line': j + 1,
                        'code': '\n'.join(lines[i:j+1]),
                        'line_count': j - i + 1,
                    })
                    break
    return functions


def parse_triggers(functions, content):
    """识别触发器函数及其事件类型

    支持所有事件注册方式:
    - TriggerRegisterAnyUnitEventBJ
    - TriggerRegisterPlayerUnitEvent
    - TriggerRegisterTimerEventPeriodic / Single
    - TriggerRegisterEnterRectSimpleNull
    - TriggerRegisterDialogEvent
    - TriggerRegisterDestDeathInRegionEvent
    - TriggerRegisterUnitInRangeSimple
    - TriggerRegisterPlayerChatEvent
    - TriggerRegisterPlayerSelectionEventBJ
    - TriggerRegisterUnitEvent
    """
    lines = content.split('\n')
    triggers = []

    # 事件映射表
    trigger_events = {
        'EVENT_PLAYER_UNIT_DEATH': 'UNIT_DEATH',
        'EVENT_PLAYER_UNIT_ATTACKED': 'UNIT_ATTACKED',
        'EVENT_PLAYER_UNIT_SPELL_EFFECT': 'UNIT_SPELL_EFFECT',
        'EVENT_PLAYER_UNIT_PICKUP_ITEM': 'UNIT_PICKUP_ITEM',
        'EVENT_PLAYER_UNIT_USE_ITEM': 'UNIT_USE_ITEM',
        'EVENT_PLAYER_UNIT_SELL_ITEM': 'UNIT_SELL_ITEM',
        'EVENT_PLAYER_UNIT_SELL': 'UNIT_SELL',
        'EVENT_PLAYER_UNIT_DROP_ITEM': 'UNIT_DROP_ITEM',
        'EVENT_PLAYER_UNIT_SPELL_CAST': 'UNIT_SPELL_CAST',
        'EVENT_PLAYER_UNIT_SPELL_FINISH': 'UNIT_SPELL_FINISH',
        'EVENT_PLAYER_UNIT_SPELL_CHANNEL': 'UNIT_SPELL_CHANNEL',
        'EVENT_PLAYER_UNIT_SPELL_ENDCAST': 'UNIT_SPELL_ENDCAST',
    }

    timer_events = {
        'TimerStart': 'TIMER_PERIODIC',
        'TimerStartPeriodic': 'TIMER_PERIODIC',
    }

    other_event_types = {
        'TriggerRegisterEnterRectSimpleNull': 'ENTER_RECT',
        'TriggerRegisterEnterRectSimple': 'ENTER_RECT',
        'TriggerRegisterEnterRegion': 'ENTER_REGION',
        'TriggerRegisterDialogEvent': 'DIALOG_EVENT',
        'TriggerRegisterDestDeathInRegionEvent': 'DESTRUCTABLE_DEATH',
        'TriggerRegisterUnitInRangeSimple': 'UNIT_IN_RANGE',
        'TriggerRegisterPlayerChatEvent': 'PLAYER_CHAT',
        'TriggerRegisterPlayerSelectionEventBJ': 'PLAYER_SELECTION',
    }

    # Step 1: 从 InitTrig 函数中提取事件注册信息
    init_event_map = {}  # trigger_var_name -> event_type
    init_action_map = {}  # trigger_var_name -> action_function_name
    init_func_map = {}    # init_func_name -> trigger_var_name (for non-standard events)

    for func in functions:
        if not func['name'].startswith('InitTrig_'):
            continue
        code = func['code']

        # 提取 trigger 变量名 (gg_trg_XXX)
        trg_var_match = re.search(r'set\s+(gg_trg_\w+)\s*=\s*CreateTrigger', code)
        trg_var = trg_var_match.group(1) if trg_var_match else None

        # 1a. TriggerRegisterAnyUnitEventBJ / TriggerRegisterPlayerUnitEvent
        for jass_event, short_name in trigger_events.items():
            pattern = r'TriggerRegister(?:AnyUnit)?EventBJ\((\w+),\s*' + re.escape(jass_event) + r'\)'
            var_match = re.search(pattern, code)
            if var_match:
                var_name = var_match.group(1)
                init_event_map[var_name] = short_name

        # 1b. Timer events
        if 'TriggerRegisterTimerEvent' in code:
            timer_match = re.search(r'TriggerRegisterTimerEvent[^\(]*\((\w+)', code)
            if timer_match:
                var_name = timer_match.group(1)
                if 'Periodic' in code:
                    init_event_map[var_name] = 'TIMER_PERIODIC'
                else:
                    init_event_map[var_name] = 'TIMER_SINGLE'

        # 1c. Other event types
        for reg_func, event_type in other_event_types.items():
            if reg_func in code:
                reg_match = re.search(reg_func + r'\((\w+)', code)
                if reg_match:
                    var_name = reg_match.group(1)
                    init_event_map[var_name] = event_type

        # 1d. TriggerAddAction
        action_match = re.search(r'TriggerAddAction\((\w+),\s*function\s+(\w+)\)', code)
        if action_match:
            var_name = action_match.group(1)
            action_name = action_match.group(2)
            init_action_map[var_name] = action_name

        # Track InitTrig -> trg_var for non-standard events
        if trg_var:
            init_func_map[func['name']] = trg_var

    # Step 2: 构建 action_function_name -> event_type 映射
    action_event_map = {}
    for var_name, event_type in init_event_map.items():
        if var_name in init_action_map:
            action_name = init_action_map[var_name]
            action_event_map[action_name] = event_type

    # Step 3: 将事件类型关联到 Trig_ 函数
    for func in functions:
        if not func['name'].startswith('Trig_'):
            continue

        event_type = action_event_map.get(func['name'])

        # 跳过没有事件类型的 Trig_ 函数（可能是 Conditions 或其他辅助函数）
        if not event_type:
            continue

        # 分析 helper function 调用
        helper_funcs = extract_helper_calls(func['code'], functions)

        triggers.append({
            **func,
            'event_type': event_type,
            'has_conditions': False,
            'helper_functions': helper_funcs,
        })

    return triggers


def extract_helper_calls(code, all_functions):
    """提取 Trig 函数中调用的辅助函数"""
    # 找 call XXX( 模式，排除 JASS API
    jass_api_prefixes = ('Get', 'Set', 'Create', 'Destroy', 'Add', 'Remove', 'Load', 'Save',
        'Issue', 'Pan', 'Unit', 'Trigger', 'For', 'Count', 'Convert', 'Is', 'Display',
        'Kill', 'Flush', 'Choose', 'Modify', 'Adjust', 'Custom', 'Dialog', 'Revive',
        'Enum', 'Camera', 'Fog', 'Do', 'Start', 'Stop', 'Pause', 'Reset',
        'Enable', 'Disable', 'Call', 'End', 'Exit', 'Loop', 'Return',
        'YDWE', 'YDW', 'DYC', 'So', 'Xc', 'Xw', 'BJ', 'Null')

    helper_calls = set()
    for m in re.finditer(r'call\s+(\w+)\s*\(', code):
        func_name = m.group(1)
        # 排除 JASS API 和关键字
        if not any(func_name.startswith(p) for p in jass_api_prefixes):
            helper_calls.add(func_name)

    # 查找这些 helper 函数的定义
    helper_defs = {}
    for func_name in helper_calls:
        for f in all_functions:
            if f['name'] == func_name:
                helper_defs[func_name] = {
                    'line_count': f['line_count'],
                    'start_line': f['start_line'],
                }
                break

    return helper_defs


def analyze_issues(triggers, content):
    """分析已知问题"""
    lines = content.split('\n')
    issues = {
        'disabled_triggers': [],
        'group_leaks': [],
        'polled_waits': [],
        'null_safety': [],
        'ht_heavy': [],  # 重度使用 hashtable 的 trigger
    }

    for trig in triggers:
        code = trig['code']
        start = trig['start_line']

        # 1. DisableTrigger without EnableTrigger
        disable_count = code.count('DisableTrigger')
        enable_count = code.count('EnableTrigger')
        if disable_count > enable_count:
            issues['disabled_triggers'].append({
                'name': trig['name'],
                'line': start,
                'disable_count': disable_count,
                'enable_count': enable_count,
            })

        # 2. Group leaks
        if 'local group' in code and 'DestroyGroup' not in code:
            groups = re.findall(r'local group (\w+)', code)
            for g in groups:
                issues['group_leaks'].append({
                    'name': trig['name'],
                    'line': start,
                    'group': g,
                })

        # 3. PolledWait (multiple variants)
        waits = re.findall(r'YDWEPolledWaitNull\(([\d.]+)\)', code)
        if not waits:
            waits = re.findall(r'PolledWait\(([\d.]+)\)', code)
        if waits:
            total = sum(float(w) for w in waits)
            issues['polled_waits'].append({
                'name': trig['name'],
                'line': start,
                'count': len(waits),
                'total_seconds': total,
            })

        # 4. Heavy hashtable usage (>5 Save/Load ops)
        ht_ops = code.count('Save') + code.count('Load')
        if ht_ops > 5:
            issues['ht_heavy'].append({
                'name': trig['name'],
                'line': start,
                'op_count': ht_ops,
            })

    return issues


def compute_complexity(trig):
    """计算触发器复杂度评分 (0-10)

    考虑因素:
    - 代码行数
    - 控制流复杂度 (if/loop/call)
    - PolledWait 阻塞
    - Hashtable 操作
    - Helper function 调用深度
    - API 类别多样性
    """
    code = trig['code']
    score = 0

    # 1. 代码行数 (0-2 分)
    score += min(trig['line_count'] // 10, 2)

    # 2. 控制流复杂度 (0-2 分)
    if_count = code.count('if (') + code.count('if(')
    loop_count = code.count('loop')
    score += min((if_count // 2) + (loop_count // 1), 2)

    # 3. API 调用数量 (0-1 分)
    call_count = code.count('call ')
    score += min(call_count // 5, 1)

    # 4. PolledWait 阻塞 (0-2 分) — 最严重影响复杂度
    wait_count = code.count('YDWEPolledWaitNull')
    score += min(wait_count * 2, 2)

    # 5. Hashtable 操作 (0-1 分)
    ht_ops = code.count('Save') + code.count('Load')
    if ht_ops > 0:
        score += min(ht_ops // 3, 1)

    # 6. Helper function 调用 (0-1 分)
    helpers = trig.get('helper_functions', {})
    if helpers:
        # 不仅看数量，还看 helper 的总行数
        helper_lines = sum(h.get('line_count', 0) for h in helpers.values())
        score += min(helper_lines // 20, 1)

    # 7. API 类别多样性 (0-1 分)
    api_categories = set()
    for api_name in API_CATEGORIES:
        if api_name + '(' in code:
            api_categories.add(API_CATEGORIES[api_name])
    score += min(len(api_categories) // 3, 1)

    return min(score, 10)


def generate_prd(functions, triggers, issues, content, strategy='event-type', ecs_status=None, source_path=None):
    """生成 PRD 文档

    ecs_status: dict mapping event_type -> {'has_event': bool, 'has_system': bool, 'systems': [...]}
    """
    lines = content.split('\n')
    total_lines = len(lines)
    total_functions = len(functions)
    total_triggers = len(triggers)

    # 事件分布
    event_counts = Counter(t['event_type'] for t in triggers)

    # 库统计
    libs = set()
    for line in lines:
        if 'LIBRARY_' in line and 'constant boolean' in line:
            lib = line.split('LIBRARY_')[1].split('=')[0].strip()
            libs.add(lib)

    # 有问题触发器集合（用于所有策略的标记）
    problem_names = set()
    for p in issues['disabled_triggers'] + issues['group_leaks'] + issues['polled_waits']:
        problem_names.add(p['name'])

    # 按策略分批
    if strategy == 'event-type':
        batches = defaultdict(list)
        for t in triggers:
            batches[t['event_type']].append(t)
        batch_list = [(f"事件类型: {k}", v) for k, v in sorted(batches.items(), key=lambda x: -len(x[1]))]
    elif strategy == 'complexity':
        sorted_trigs = sorted(triggers, key=lambda t: compute_complexity(t))
        third = len(sorted_trigs) // 3
        batch_list = [
            ("低复杂度", sorted_trigs[:third]),
            ("中复杂度", sorted_trigs[third:third*2]),
            ("高复杂度", sorted_trigs[third*2:]),
        ]
    elif strategy == 'severity':
        with_problems = [t for t in triggers if t['name'] in problem_names]
        without_problems = [t for t in triggers if t['name'] not in problem_names]
        batch_list = [
            ("有严重问题", with_problems[:50]),
            ("有严重问题 (续)", with_problems[50:]),
            ("无已知问题", without_problems[:50]),
        ]
    elif strategy == 'ecs-ready':
        # 优先迁移 ECS 已就绪的事件类型
        ready = [t for t in triggers if ecs_status and ecs_status.get(t['event_type'], {}).get('has_event', False)]
        partial = [t for t in triggers if ecs_status and t['event_type'] in ecs_status]
        not_ready = [t for t in triggers if not ecs_status or t['event_type'] not in ecs_status]
        batch_list = [
            ("ECS 已就绪", ready[:50]),
            ("ECS 已就绪 (续)", ready[50:]),
            ("ECS 部分就绪", partial[:50]),
            ("ECS 未就绪", not_ready[:50]),
        ]
    else:
        batch_list = [("全部触发器", triggers)]

    # 构建 PRD
    prd_lines = []
    prd_lines.append("# JASS → ECS 迁移 PRD\n")
    prd_lines.append(f"**生成日期**: {date.today().isoformat()}")
    prd_lines.append(f"**源文件**: {source_path or 'war3map.j'} ({total_lines} 行)")
    prd_lines.append(f"**迁移策略**: {strategy}\n")
    prd_lines.append("---\n")

    # 总览
    prd_lines.append("## 1. 总览\n")
    prd_lines.append(f"| 指标 | 数值 |")
    prd_lines.append(f"|------|------|")
    prd_lines.append(f"| 源文件行数 | {total_lines} |")
    prd_lines.append(f"| 总函数 | {total_functions} |")
    prd_lines.append(f"| 触发器函数 | {total_triggers} |")
    prd_lines.append(f"| 触发器事件类型 | {len(event_counts)} |")
    prd_lines.append(f"| 涉及库 | {len(libs)} |")
    prd_lines.append(f"| 触发器永久禁用 | {len(issues['disabled_triggers'])} |")
    prd_lines.append(f"| Group 内存泄漏 | {len(issues['group_leaks'])} |")
    prd_lines.append(f"| PolledWait 调用 | {sum(p['count'] for p in issues['polled_waits'])} |")
    prd_lines.append(f"| Hashtable 重度使用 | {len(issues.get('ht_heavy', []))} |")
    prd_lines.append("")

    prd_lines.append("### 事件分布\n")
    prd_lines.append("| 事件类型 | 数量 | 占比 | ECS 就绪 |")
    prd_lines.append("|---------|------|------|----------|")
    for ev, count in event_counts.most_common():
        pct = f"{count/total_triggers*100:.1f}%"
        ecs_mark = ""
        if ecs_status and ev in ecs_status:
            s = ecs_status[ev]
            if s.get('has_event') and s.get('has_system'):
                ecs_mark = "✅"
            elif s.get('has_event'):
                ecs_mark = "🟡"
            else:
                ecs_mark = "❌"
        prd_lines.append(f"| {ev} | {count} | {pct} | {ecs_mark} |")
    prd_lines.append("")

    # 已知问题
    prd_lines.append("## 2. 已知问题\n")
    if issues['disabled_triggers']:
        prd_lines.append("### 2.1 触发器永久禁用\n")
        prd_lines.append(f"共 {len(issues['disabled_triggers'])} 个触发器被禁用但未重新启用，**可直接删除**。\n")
        for p in issues['disabled_triggers'][:30]:
            prd_lines.append(f"- **{p['name']}** (L{p['line']}): 禁用 {p['disable_count']} 次，启用 {p['enable_count']} 次")
        if len(issues['disabled_triggers']) > 30:
            prd_lines.append(f"- ... 还有 {len(issues['disabled_triggers'])-30} 处")
        prd_lines.append("")

    if issues['group_leaks']:
        prd_lines.append("### 2.2 Group 内存泄漏\n")
        for p in issues['group_leaks'][:20]:
            prd_lines.append(f"- **{p['name']}** (L{p['line']}): `{p['group']}` 未 DestroyGroup")
        if len(issues['group_leaks']) > 20:
            prd_lines.append(f"- ... 还有 {len(issues['group_leaks'])-20} 处")
        prd_lines.append("")

    if issues['polled_waits']:
        total_wait = sum(p['total_seconds'] for p in issues['polled_waits'])
        prd_lines.append("### 2.3 PolledWait 阻塞\n")
        prd_lines.append(f"总计 {len(issues['polled_waits'])} 个触发器使用 PolledWait，累计 {total_wait:.0f} 秒\n")
        sorted_waits = sorted(issues['polled_waits'], key=lambda x: -x['total_seconds'])
        for p in sorted_waits[:10]:
            prd_lines.append(f"- **{p['name']}** (L{p['line']}): {p['count']} 次等待，共 {p['total_seconds']:.1f} 秒")
        prd_lines.append("")

    if issues.get('ht_heavy'):
        prd_lines.append("### 2.4 Hashtable 重度使用\n")
        prd_lines.append(f"共 {len(issues['ht_heavy'])} 个触发器有大量 hashtable 操作，迁移时需转为 Component。\n")
        for p in sorted(issues['ht_heavy'], key=lambda x: -x['op_count'])[:15]:
            prd_lines.append(f"- **{p['name']}** (L{p['line']}): {p['op_count']} 次 Save/Load 操作")
        prd_lines.append("")

    # 迁移批次
    prd_lines.append("## 3. 迁移计划\n")
    for i, (name, batch_trigs) in enumerate(batch_list, 1):
        if not batch_trigs:
            continue
        prd_lines.append(f"### 批次 {i}: {name}\n")
        prd_lines.append(f"触发器数量: {len(batch_trigs)}\n")
        prd_lines.append("| 触发器 | 事件 | 行数 | 复杂度 | Helper | 问题 |")
        prd_lines.append("|--------|------|------|--------|--------|------|")
        for t in batch_trigs[:30]:
            cx = compute_complexity(t)
            has_issue = '⚠️' if t['name'] in problem_names else ''
            helper_count = len(t.get('helper_functions', {}))
            helper_str = str(helper_count) if helper_count > 0 else ''
            prd_lines.append(f"| {t['name']} | {t['event_type']} | {t['line_count']} | {cx} | {helper_str} | {has_issue} |")
        if len(batch_trigs) > 30:
            prd_lines.append(f"\n... 还有 {len(batch_trigs)-30} 个触发器，运行 `extract_trigger.py <trigger_name>` 查看单个分析\n")
        prd_lines.append("")

    return '\n'.join(prd_lines)


# ============================================================
# Main
# ============================================================

def analyze_ecs_readiness(lua_dir):
    """扫描现有 Lua 代码，分析 ECS 就绪度

    返回 dict: event_type -> {
        'has_event': bool,      # GameEvent.lua 中是否有对应事件类
        'has_system': bool,     # systems/ 中是否有对应系统
        'has_component': bool,  # components/ 中是否有对应组件
        'systems': [str],       # 系统列表
        'components': [str],    # 组件列表
    }
    """
    status = {}

    # 事件类到事件类型的映射
    event_class_map = {
        'AnyUnitDeath': 'UNIT_DEATH',
        'AnyUnitAttack': 'UNIT_ATTACKED',
        'AnyUnitDamaged': 'UNIT_ATTACKED',
        'AnyUnitSpellCast': 'UNIT_SPELL_CAST',
        'AnyUnitSpellEffect': 'UNIT_SPELL_EFFECT',
        'AnyUnitSpellFinish': 'UNIT_SPELL_FINISH',
        'AnyUnitPickUpItem': 'UNIT_PICKUP_ITEM',
        'AnyUnitUseItem': 'UNIT_USE_ITEM',
        'AnyUnitSellItem': 'UNIT_SELL_ITEM',
        'AnyUnitSell': 'UNIT_SELL',
        'AnyUnitDropItem': 'UNIT_DROP_ITEM',
        'AnyUnitEnterRect': 'ENTER_RECT',
        'AnyUnitEnterRegion': 'ENTER_REGION',
        'AnyUnitAboutToDie': 'UNIT_DEATH',
        'AnyUnitLearnedSkill': 'UNIT_SPELL_EFFECT',
        'AnyUnitIssueImmediateOrder': 'UNIT_ISSUE_ORDER',
        'AnyUnitIssueTargetOrder': 'UNIT_ISSUE_TARGET_ORDER',
        'AnyUnitIssuePointOrder': 'UNIT_ISSUE_POINT_ORDER',
        'AnyPlayerChat': 'PLAYER_CHAT',
        'AnyPlayerEsc': 'PLAYER_ESC',
        'AnyPlayerLeave': 'PLAYER_LEAVE',
        'AnyPlayerSelectUnit': 'PLAYER_SELECTION',
        'AnyPlayerKeyDown': 'PLAYER_KEY_DOWN',
        'AnyUnitAttributeChanged': 'ATTRIBUTE_CHANGED',
        'AnyUnitCollideBullet': 'COLLIDE_BULLET',
        'AnyUnitSell': 'UNIT_SELL',
        'PathNodeNotify': 'PATH_NODE',
        'PathEndedNotify': 'PATH_ENDED',
        'AnyDungeonKilledOver': 'DUNGEON_CLEAR',
        'AnyHeroLevelUp': 'HERO_LEVEL_UP',
        'AnyUnitConstructFinish': 'UNIT_CONSTRUCT',
        'AnyUnitTrainFinish': 'UNIT_TRAIN',
        'AnyUnitUpgradeFinish': 'UNIT_UPGRADE',
        'AnyUnitPickUpItem': 'UNIT_PICKUP_ITEM',
    }

    # 扫描 GameEvent.lua
    game_event_path = os.path.join(lua_dir, 'src', 'core', 'GameEvent.lua')
    if os.path.exists(game_event_path):
        with open(game_event_path, 'r', encoding='utf-8') as f:
            content = f.read()
        for event_class, event_type in event_class_map.items():
            if event_class in content:
                if event_type not in status:
                    status[event_type] = {'has_event': False, 'has_system': False, 'has_component': False, 'systems': [], 'components': []}
                status[event_type]['has_event'] = True

    # 扫描 systems/ 目录
    systems_dir = os.path.join(lua_dir, 'src', 'systems')
    if os.path.exists(systems_dir):
        for f in os.listdir(systems_dir):
            if f.endswith('.lua') and f != 'init.lua':
                system_name = f.replace('.lua', '')
                status[system_name] = status.get(system_name, {'has_event': False, 'has_system': True, 'has_component': False, 'systems': [], 'components': []})
                status[system_name]['has_system'] = True
                status[system_name]['systems'].append(system_name)

    # 扫描 components/ 目录
    components_dir = os.path.join(lua_dir, 'src', 'components')
    if os.path.exists(components_dir):
        for f in os.listdir(components_dir):
            if f.endswith('.lua') and f != 'init.lua':
                comp_name = f.replace('.lua', '')
                # 尝试匹配到事件类型
                for event_type in status:
                    status[event_type]['has_component'] = True
                    status[event_type]['components'].append(comp_name)

    # 已知系统-事件类型关联
    system_event_map = {
        'UnitSystem': ['UNIT_DEATH', 'UNIT_ATTACKED'],
        'ItemSystem': ['UNIT_PICKUP_ITEM', 'UNIT_USE_ITEM', 'UNIT_SELL_ITEM', 'UNIT_DROP_ITEM'],
        'SkillSystem': ['UNIT_SPELL_CAST', 'UNIT_SPELL_EFFECT', 'UNIT_SPELL_FINISH'],
        'DamageSystem': ['UNIT_ATTACKED'],
        'BuffSystem': ['UNIT_ATTACKED'],
        'PlayerSystem': ['PLAYER_CHAT', 'PLAYER_ESC', 'PLAYER_LEAVE', 'PLAYER_SELECTION'],
        'HeroSystem': ['HERO_LEVEL_UP'],
        'QuestSystem': [],
        'BulletSystem': ['COLLIDE_BULLET'],
        'TweenSystem': [],
        'UIMoveSystem': [],
        'PointEffectSystem': [],
        'TargetEffectSystem': [],
        'EquipSystem': [],
        'ManaShieldSystem': [],
        'BonusSystem': [],
        'EffectDamageSystem': [],
    }

    for system_name, event_types in system_event_map.items():
        for event_type in event_types:
            if event_type not in status:
                status[event_type] = {'has_event': False, 'has_system': False, 'has_component': False, 'systems': [], 'components': []}
            if os.path.exists(os.path.join(systems_dir, system_name + '.lua')):
                status[event_type]['has_system'] = True
                if system_name not in status[event_type]['systems']:
                    status[event_type]['systems'].append(system_name)

    return status


# ============================================================
# Main
# ============================================================

def load_migration_status(status_file):
    """加载迁移进度状态"""
    if os.path.exists(status_file):
        with open(status_file, 'r', encoding='utf-8') as f:
            import json
            return json.load(f)
    return {}


def save_migration_status(status, status_file):
    """保存迁移进度状态"""
    import json
    with open(status_file, 'w', encoding='utf-8') as f:
        json.dump(status, f, ensure_ascii=False, indent=2)


def mark_migrated(status, trigger_name, prd_file, notes=''):
    """标记触发器为已迁移"""
    import time
    status[trigger_name] = {
        'state': 'done',
        'migrated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'prd_file': prd_file,
        'notes': notes,
    }


def generate_prd_with_status(functions, triggers, issues, content, strategy='event-type', ecs_status=None, migration_status=None, source_path=None):
    """生成带迁移进度的 PRD 文档"""
    prd = generate_prd(functions, triggers, issues, content, strategy, ecs_status, source_path)

    # 在末尾添加迁移进度
    if migration_status:
        done_count = sum(1 for v in migration_status.values() if v.get('state') == 'done')
        total_count = len(migration_status)
        progress = f"\n\n## 迁移进度\n\n| 状态 | 数量 |\n|------|------|\n"
        progress += f"| ✅ 已迁移 | {done_count} |\n"
        progress += f"| ⬜ 待迁移 | {total_count - done_count} |\n"
        if total_count > 0:
            pct = done_count / total_count * 100
            progress += f"| **总计** | **{pct:.1f}%** |\n"
        prd += progress

    return prd


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(description='JASS → ECS 迁移全局分析')
    parser.add_argument('jass_file', help='war3map.j 文件路径')
    parser.add_argument('--output', '-o', help='PRD 输出路径', default=None)
    parser.add_argument('--strategy', '-s', choices=['event-type', 'complexity', 'severity', 'ecs-ready'],
                        default='event-type', help='迁移策略')
    parser.add_argument('--lua-dir', help='Lua ECS 代码目录，用于分析 ECS 就绪度', default=None)
    parser.add_argument('--status-file', help='迁移进度状态文件路径', default=None)
    parser.add_argument('--mark', metavar='TRIGGER_NAME', help='标记指定触发器为已迁移')
    parser.add_argument('--mark-notes', default='', help='标记时的备注信息')
    parser.add_argument('--status-list', action='store_true', help='列出迁移状态摘要')
    args = parser.parse_args()

    # --mark 模式：标记触发器并退出
    if args.mark and args.status_file:
        status = load_migration_status(args.status_file)
        mark_migrated(status, args.mark, args.output or '', args.mark_notes)
        save_migration_status(status, args.status_file)
        print(f"✅ 已标记 {args.mark} 为已迁移")
        done = sum(1 for v in status.values() if v.get('state') == 'done')
        print(f"   进度: {done}/{len(status)}")
        return

    # --status-list 模式：显示状态摘要并退出
    if args.status_list and args.status_file:
        status = load_migration_status(args.status_file)
        done = sum(1 for v in status.values() if v.get('state') == 'done')
        pending = len(status) - done
        print(f"迁移状态摘要:")
        print(f"  ✅ 已迁移: {done}")
        print(f"  ⬜ 待迁移: {pending}")
        print(f"  📊 总计: {len(status)}")
        if len(status) > 0:
            print(f"  📈 进度: {done/len(status)*100:.1f}%")
        return

    jass_path = args.jass_file
    if not os.path.exists(jass_path):
        print(f"错误: 文件不存在: {jass_path}")
        sys.exit(1)

    with open(jass_path, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()

    print(f"解析 {jass_path}...")
    functions = parse_functions(content)
    print(f"  发现 {len(functions)} 个函数")

    triggers = parse_triggers(functions, content)
    print(f"  发现 {len(triggers)} 个触发器")

    issues = analyze_issues(triggers, content)
    print(f"  触发器永久禁用: {len(issues['disabled_triggers'])}")
    print(f"  Group 内存泄漏: {len(issues['group_leaks'])}")
    print(f"  PolledWait 触发器: {len(issues['polled_waits'])}")
    print(f"  Hashtable 重度使用: {len(issues.get('ht_heavy', []))}")

    # ECS 就绪度分析
    ecs_status = None
    if args.lua_dir:
        ecs_status = analyze_ecs_readiness(args.lua_dir)
        print(f"  ECS 就绪度分析: {len(ecs_status)} 个事件类型")

    # 迁移进度
    migration_status = None
    if args.status_file:
        migration_status = load_migration_status(args.status_file)
        done = sum(1 for v in migration_status.values() if v.get('state') == 'done')
        print(f"  迁移进度: {done}/{len(migration_status)} 已迁移")

    prd = generate_prd_with_status(functions, triggers, issues, content, args.strategy, ecs_status, migration_status, source_path=jass_path)

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(prd)
        print(f"\nPRD 已写入: {args.output}")
    else:
        print("\n" + prd)


if __name__ == '__main__':
    main()
