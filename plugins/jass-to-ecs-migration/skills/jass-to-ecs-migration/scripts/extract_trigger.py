#!/usr/bin/env python3
"""
extract_trigger.py - 提取并分析单个 JASS 触发器

用法:
    python3 extract_trigger.py <war3map.j路径> <触发器名称> [--output <输出路径>]

示例:
    python3 extract_trigger.py map/war3map.j Trig____________________079Actions
    python3 extract_trigger.py map/war3map.j DummyDieActions -o /tmp/analysis.md
"""

import re
import sys
import os
import argparse
from collections import defaultdict

# 已知 API 分类
API_CATEGORIES = {
    # 单位事件
    'GetTriggerUnit': 'unit_event',
    'GetDyingUnit': 'unit_event',
    'GetAttacker': 'unit_event',
    'GetKillingUnit': 'unit_event',
    'GetEnumUnit': 'unit_event',
    'GetManipulatingUnit': 'unit_event',
    'GetManipulatedItem': 'item_event',
    'GetSoldItem': 'item_event',
    'GetBuyingUnit': 'unit_event',
    'GetSoldUnit': 'unit_event',
    'GetEventDamageSource': 'unit_event',
    'GetSpellAbilityUnit': 'unit_event',
    'GetEnteringUnit': 'unit_event',
    'GetSellingUnit': 'unit_event',
    'GetFilterUnit': 'unit_event',
    'GetExpiredTimer': 'timer_event',
    'GetDyingDestructable': 'unit_event',
    'GetEnumDestructable': 'unit_enum',
    # 单位信息
    'GetUnitX': 'unit_info',
    'GetUnitY': 'unit_info',
    'GetUnitTypeId': 'unit_info',
    'GetWidgetLife': 'unit_info',
    'GetUnitState': 'unit_info',
    'GetUnitAbilityLevel': 'unit_info',
    'GetUnitLoc': 'location',
    'GetOwningPlayer': 'unit_info',
    'GetUnitFacing': 'unit_info',
    'GetUnitUserData': 'unit_info',
    'GetUnitLifePercent': 'unit_info',
    'GetUnitStateSwap': 'unit_info',
    'GetHeroLevel': 'unit_info',
    'GetHeroStr': 'unit_info',
    'GetHeroAgi': 'unit_info',
    'GetHeroInt': 'unit_info',
    'GetHeroStatBJ': 'unit_info',
    'IsUnitType': 'unit_info',
    'IsUnitAliveBJ': 'unit_info',
    'IsUnitAlly': 'unit_info',
    'IsUnitEnemy': 'unit_info',
    'GetUnitFlyHeight': 'unit_info',
    'YDWEAngleBetweenUnits': 'unit_info',
    # 物品信息
    'GetItemTypeId': 'item_info',
    'GetItemCharges': 'item_info',
    'UnitItemInSlotBJ': 'item_info',
    'YDWEGetItemOfTypeFromUnitBJNull': 'item_info',
    'YDWEUnitHasItemOfTypeBJNull': 'item_info',
    # 事件信息
    'GetEventDamage': 'damage',
    'GetSpellAbilityId': 'spell',
    'GetSpellTargetUnit': 'spell',
    'GetSpellTargetX': 'spell',
    'GetSpellTargetY': 'spell',
    # 操作
    'UnitDamageTarget': 'damage',
    'UnitDamageTargetBJ': 'damage',
    'UnitAddAbility': 'ability',
    'UnitRemoveAbility': 'ability',
    'CreateUnit': 'unit_create',
    'CreateUnitAtLoc': 'unit_create',
    'CreateNUnitsAtLocFacingLocBJ': 'unit_create',
    'CreateNUnitsAtLoc': 'unit_create',
    'RemoveUnit': 'unit_remove',
    'KillUnit': 'unit_kill',
    'KillDestructable': 'unit_kill',
    'RemoveDestructable': 'unit_kill',
    'ReviveHeroLoc': 'unit_revive',
    'CreateItem': 'item',
    'CreateItemLoc': 'item',
    'RemoveItem': 'item',
    'UnitRemoveItemFromSlotSwapped': 'item',
    'UnitAddItemByIdSwapped': 'item',
    'UnitRemoveItemSwapped': 'item',
    'UnitResetCooldown': 'unit_modify',
    'UnitApplyTimedLife': 'unit_buff',
    'UnitStripHeroLevel': 'unit_modify',
    'AddHeroXP': 'unit_modify',
    'SetHeroLevelBJ': 'unit_modify',
    'ModifyHeroStat': 'unit_modify',
    'SetHeroStr': 'unit_modify',
    'SetHeroAgi': 'unit_modify',
    'SetHeroInt': 'unit_modify',
    'SetUnitFlyHeight': 'unit_modify',
    'SetUnitUserData': 'unit_modify',
    'SoAddUnitState': 'unit_modify',
    'SoInvincible': 'unit_modify',
    'SoHeroStateAmend': 'unit_modify',
    'SoAddUnitLife': 'unit_modify',
    'SoAddItemCharges': 'item',
    'ChooseRandomItemBJ': 'item',
    'YDWENewItemsFormula': 'item_info',
    'AddSpecialEffect': 'effect',
    'AddSpecialEffectTargetUnitBJ': 'effect',
    'AddSpecialEffectLocBJ': 'effect',
    'DestroyEffect': 'effect',
    'CreateTextTagUnitBJ': 'texttag',
    'CreateTextTagLocBJ': 'texttag',
    'DisplayTextToPlayer': 'texttag',
    'GetLastCreatedTextTag': 'texttag',
    'YDWETimerDestroyTextTag': 'texttag',
    'SoTextTagForUnit': 'texttag',
    'SoNewTextTagUnit': 'texttag',
    'SoNewTextTag': 'texttag',
    'SoTurnTextTagToUnit': 'texttag',
    'CreateTimer': 'timer',
    'TimerStart': 'timer',
    'PauseTimer': 'timer',
    'DestroyTimer': 'timer',
    'GetLastCreatedTimerBJ': 'timer',
    'CreateTimerDialogBJ': 'timer',
    'GetLastCreatedTimerDialogBJ': 'timer',
    'DestroyTimerDialog': 'timer',
    'CreateGroup': 'group',
    'DestroyGroup': 'group',
    'GroupAddUnit': 'group',
    'GroupRemoveUnit': 'group',
    'ForGroup': 'group',
    'ForGroupBJ': 'group',
    'GroupEnumUnitsInRange': 'group',
    'GroupEnumUnitsOfPlayer': 'group',
    'YDWEGetUnitsOfPlayerMatchingNull': 'group',
    'YDWEGetUnitsInRectMatchingNull': 'group',
    'YDWEGetUnitsInRectOfPlayerNull': 'group',
    'IsUnitInGroup': 'group',
    'IsUnitGroupEmptyBJ': 'group',
    'Location': 'location',
    'RemoveLocation': 'location',
    'GetRectCenter': 'location',
    'GetRectCenterEx': 'location',
    'GetRectCenterX': 'location',
    'GetRectCenterY': 'location',
    'GetRandomLocInRect': 'location',
    'GetDestructableLoc': 'location',
    'GetPlayableMapRect': 'location',
    'PolarProjectionBJ': 'location',
    'SaveUnitHandle': 'hashtable',
    'SaveInteger': 'hashtable',
    'SaveReal': 'hashtable',
    'SaveString': 'hashtable',
    'SaveGroupHandle': 'hashtable',
    'SavePlayerHandle': 'hashtable',
    'SaveEffectHandle': 'hashtable',
    'SaveTimerDialogHandle': 'hashtable',
    'LoadUnitHandle': 'hashtable',
    'LoadInteger': 'hashtable',
    'LoadReal': 'hashtable',
    'LoadString': 'hashtable',
    'LoadGroupHandle': 'hashtable',
    'LoadEffectHandle': 'hashtable',
    'LoadPlayerHandle': 'hashtable',
    'LoadTimerDialogHandle': 'hashtable',
    'GetHandleId': 'hashtable',
    'FlushChildHashtable': 'hashtable',
    'DisableTrigger': 'trigger',
    'EnableTrigger': 'trigger',
    'DestroyTrigger': 'trigger',
    'GetTriggeringTrigger': 'trigger',
    'Condition': 'trigger',
    'TriggerExecute': 'trigger',
    'GetTriggerExecCount': 'trigger_info',
    'YDWEPolledWaitNull': 'polled_wait',
    'IssueImmediateOrder': 'order',
    'IssueTargetOrder': 'order',
    'IssuePointOrder': 'order',
    'IssuePointOrderLoc': 'order',
    'CreateTrigger': 'trigger_init',
    'TriggerRegisterAnyUnitEventBJ': 'trigger_init',
    'TriggerAddAction': 'trigger_init',
    'TriggerAddCondition': 'trigger_init',
    'SetUnitState': 'unit_state',
    'SetUnitPosition': 'unit_move',
    'SetUnitPositionLoc': 'unit_move',
    'SetUnitPositionLocEx': 'unit_move',
    'PanCameraToTimed': 'camera',
    'PanCameraToTimedLocForPlayer': 'camera',
    'PanCameraToTimedLocForPlayerEx': 'camera',
    'CameraSetEQNoiseForPlayer': 'camera',
    'CameraClearNoiseForPlayer': 'camera',
    'SetUnitVertexColor': 'unit_visual',
    'SetUnitVertexColorBJ': 'unit_visual',
    'GetRandomInt': 'random',
    'GetRandomReal': 'random',
    'GetRandomDirectionDeg': 'random',
    'I2S': 'conversion',
    'R2S': 'conversion',
    'S2I': 'conversion',
    'ConvertUnitState': 'conversion',
    # 玩家
    'GetPlayersAll': 'player',
    'GetPlayerState': 'player_info',
    'SetPlayerStateBJ': 'player_modify',
    'SetPlayerHandicapXP': 'player_modify',
    'GetPlayerSlotState': 'player_info',
    'GetPlayerController': 'player_info',
    'GetPlayerName': 'player_info',
    'AdjustPlayerStateBJ': 'player_modify',
    'SetPlayerAllianceStateBJ': 'player_modify',
    # 商店
    'AddItemToStockBJ': 'item_stock',
    'RemoveItemFromStockBJ': 'item_stock',
    # 对话框
    'DialogAddButtonBJ': 'dialog',
    'GetLastCreatedButtonBJ': 'dialog',
    'GetClickedButtonBJ': 'dialog',
    'DialogSetMessage': 'dialog',
    'DialogDisplayBJ': 'dialog',
    # 任务/胜利
    'CreateQuestBJ': 'quest',
    'CustomVictoryBJ': 'game',
    # YDWE 自定义
    'YDWERPGGetKey': 'custom',
    'YDWERPGAddKey': 'custom',
    'YDWERPGBillingHasStatus': 'custom',
    'YDWEGeneralBounsSystemUnitSetBonus': 'custom',
    'YDWETimerPatternRushSlide': 'custom',
    # DYC 自定义
    'DYCImpaleSector': 'custom',
    'DYCImpaleLinear': 'custom',
    'DYCdmgdodge': 'custom',
    'DYCpushback': 'custom',
    # Xcall 扩展
    'Xcalld': 'custom',
    'Xcallf': 'custom',
    'Xcalle': 'custom',
    # 其他
    'DoNothing': 'misc',
    'FogMaskEnable': 'camera',
    'FogEnable': 'camera',
    'CreateDestructableLoc': 'unit_create',
    'GetLastCreatedDestructable': 'unit_info',
    'EnumDestructablesInRectAll': 'unit_enum',
    'GetOrderTargetUnit': 'unit_event',
    'GetOrderPointX': 'location',
    'GetOrderPointY': 'location',
    'GetIssuedOrderId': 'order',
    'GetTriggerPlayer': 'player',
    'GetSpellTargetItem': 'item_event',
    'GetEventPlayerChatString': 'player',
}

# ECS 映射建议
ECS_SUGGESTIONS = {
    'unit_event': '事件回调中 → event 对象属性',
    'damage': 'DamageObj.create():apply()',
    'timer': 'ac.timer(callback, timeout, {loop=...})',
    'timer_event': 'event.timer (在 timer 回调中)',
    'group': 'Engine:query({Component})',
    'location': '{x, y} table 替代 Location',
    'hashtable': 'ECS Component 属性',
    'trigger': 'EventManager.subscribe/unsubscribe',
    'trigger_init': 'EventManager 注册 (仅需一次)',
    'trigger_info': 'trigger 对象属性',
    'polled_wait': 'ac.timer 状态机替代',
    'effect': 'AssetsManager.createEffect()',
    'texttag': 'ac.texttag',
    'ability': 'addBuff() 或 SkillSystem',
    'item': 'ItemSystem.createItem()',
    'item_info': 'item.typeId 或 item 对象属性',
    'item_event': '事件回调中 → event 对象属性',
    'item_stock': '商店 Entity 的库存管理',
    'unit_info': 'Component 属性或保留 JASS API',
    'unit_enum': 'for _, entity in engine:query({Comp}) do',
    'unit_create': 'AssetsManager.createUnit() 或 engine:addEntity()',
    'unit_remove': 'entity:destroy()',
    'unit_kill': 'unit:kill() 或 unit:destroy()',
    'unit_revive': 'HeroSystem.reviveHero()',
    'unit_modify': 'unit.attribute:modify() 或对应 Component',
    'unit_buff': 'unit:addBuff()',
    'unit_move': 'unit:setPoint() 或 SetUnitX/Y',
    'unit_state': 'japi.SetUnitState() 或 Component 属性',
    'unit_visual': 'SetUnitVertexColor()',
    'player': 'PlayerObj 实体',
    'player_info': 'player 对象属性',
    'player_modify': 'player 方法调用',
    'camera': 'Camera API 保留或使用 ac.camera',
    'dialog': 'UI 系统处理',
    'quest': 'QuestSystem',
    'game': 'GameState 转换',
    'random': 'math.random()',
    'conversion': '类型转换函数',
    'custom': '自定义扩展，需查看具体实现',
    'misc': '无操作或保留 JASS API',
}


def find_function(content, trigger_name):
    """查找指定函数的代码"""
    pattern = rf'function {re.escape(trigger_name)}\s+takes\s+.*?endfunction'
    match = re.search(pattern, content, re.DOTALL)
    if match:
        return match.group(0)
    return None


def find_function_lines(content, trigger_name):
    """查找函数起止行号"""
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if line.strip().startswith(f'function {trigger_name} ') or line.strip() == f'function {trigger_name} takes':
            start = i + 1
            for j in range(i + 1, len(lines)):
                if lines[j].strip() == 'endfunction':
                    return start, j + 1
    return None, None


def find_event_from_inittrig(content, trigger_name):
    """从对应的 InitTrig 函数中查找事件类型"""
    # Trig_XXXActions -> InitTrig_XXX
    init_name = trigger_name.replace('Actions', '').replace('Conditions', '')
    init_name = 'InitTrig_' + init_name.replace('Trig_', '', 1)

    init_code = find_function(content, init_name)
    if not init_code:
        return None

    trigger_events = {
        'EVENT_PLAYER_UNIT_DEATH': 'UNIT_DEATH',
        'EVENT_PLAYER_UNIT_ATTACKED': 'UNIT_ATTACKED',
        'EVENT_PLAYER_UNIT_SPELL_EFFECT': 'UNIT_SPELL_EFFECT',
        'EVENT_PLAYER_UNIT_PICKUP_ITEM': 'UNIT_PICKUP_ITEM',
        'EVENT_PLAYER_UNIT_USE_ITEM': 'UNIT_USE_ITEM',
        'EVENT_PLAYER_UNIT_SELL_ITEM': 'UNIT_SELL_ITEM',
        'EVENT_PLAYER_UNIT_SELL': 'UNIT_SELL',
        'EVENT_PLAYER_UNIT_DROP_ITEM': 'UNIT_DROP_ITEM',
        'EVENT_PLAYER_UNIT_ISSUED_TARGET_ORDER': 'UNIT_ISSUED_TARGET_ORDER',
    }
    for jass_event, short_name in trigger_events.items():
        if jass_event in init_code:
            return short_name
    return None


def extract_apis(code):
    """提取代码中调用的 API"""
    apis = defaultdict(list)
    lines = code.split('\n')
    for line_offset, line in enumerate(lines):
        for api_name, category in API_CATEGORIES.items():
            if api_name + '(' in line:
                apis[api_name].append({'line_offset': line_offset + 1, 'category': category})
    return apis


def extract_variables(code):
    """提取读取/写入的全局变量"""
    read_vars = defaultdict(list)
    write_vars = defaultdict(list)

    lines = code.split('\n')
    for line_offset, line in enumerate(lines):
        stripped = line.strip()
        # 写入: set var = ...
        set_match = re.match(r'set\s+(\w+)\s*=', stripped)
        if set_match:
            var = set_match.group(1)
            if not var.startswith('local ') and not var.startswith('end'):
                write_vars[var].append(line_offset + 1)

        # 读取: 变量出现在表达式中
        # 排除 local 声明和 set 左侧
        if 'local ' in stripped or stripped.startswith('set '):
            continue
        # 简单提取：找已知 UDG 前缀或常见变量
        udg_vars = re.findall(r'udg_(\w+)', stripped)
        for v in udg_vars:
            read_vars[f'udg_{v}'].append(line_offset + 1)

    return read_vars, write_vars


def extract_hashtable_ops(code):
    """提取 hashtable 操作"""
    ops = []
    lines = code.split('\n')
    for line_offset, line in enumerate(lines):
        stripped = line.strip()
        ht_match = re.match(r'call\s+(Save|Load)(\w+)Handle?\((\w+),\s*(.+?),\s*(.+?)[,\)]', stripped)
        if ht_match:
            action = ht_match.group(1)  # Save/Load
            type_name = ht_match.group(2)  # Unit/Integer/Real/String/Group
            ht_name = ht_match.group(3)
            key = ht_match.group(4).strip()
            subkey = ht_match.group(5).strip().rstrip(')')
            ops.append({
                'action': action,
                'type': type_name,
                'hashtable': ht_name,
                'key': key,
                'subkey': subkey,
                'line_offset': line_offset + 1,
            })
    return ops


def detect_issues(code, start_line):
    """检测已知问题"""
    issues = []
    if 'DisableTrigger' in code and 'EnableTrigger' not in code:
        issues.append('⚠️ DisableTrigger 无对应 EnableTrigger — 触发器可能永久禁用')
    if 'local group' in code and 'DestroyGroup' not in code:
        issues.append('⚠️ local group 未调用 DestroyGroup — 内存泄漏')
    waits = re.findall(r'YDWEPolledWaitNull\(([\d.]+)\)', code)
    if waits:
        total = sum(float(w) for w in waits)
        issues.append(f'⚠️ PolledWait {len(waits)} 次，累计阻塞 {total:.1f} 秒 — 应改为 ac.timer')
    if code.count('else') > code.count('endif'):
        issues.append('⚠️ else/endif 数量不匹配 — 可能的语法错误')
    return issues


def generate_analysis(trigger_name, code, start_line, end_line, content=None):
    """生成分析报告"""
    apis = extract_apis(code)
    read_vars, write_vars = extract_variables(code)
    ht_ops = extract_hashtable_ops(code)
    issues = detect_issues(code, start_line)

    # 构建 markdown
    md = []
    md.append(f"# 触发器分析: {trigger_name}\n")
    md.append(f"**源**: war3map.j 行 {start_line}-{end_line}\n")

    # 事件类型 — 先查代码，再查 InitTrig
    event_type = '未知'
    if 'EVENT_PLAYER_UNIT_DEATH' in code:
        event_type = 'UNIT_DEATH'
    elif 'EVENT_PLAYER_UNIT_ATTACKED' in code:
        event_type = 'UNIT_ATTACKED'
    elif 'EVENT_PLAYER_UNIT_SPELL_EFFECT' in code:
        event_type = 'UNIT_SPELL_EFFECT'
    elif 'EVENT_PLAYER_UNIT_PICKUP_ITEM' in code:
        event_type = 'UNIT_PICKUP_ITEM'
    elif 'EVENT_PLAYER_UNIT_USE_ITEM' in code:
        event_type = 'UNIT_USE_ITEM'
    elif 'EVENT_PLAYER_UNIT_SELL_ITEM' in code:
        event_type = 'UNIT_SELL_ITEM'
    elif content:
        init_event = find_event_from_inittrig(content, trigger_name)
        if init_event:
            event_type = init_event
    md.append(f"**事件**: {event_type}\n")

    # 功能描述
    md.append("## 功能描述\n")
    md.append(f"共 {len(code.split(chr(10)))} 行代码，处理 {event_type} 事件。\n")

    # 原始代码
    md.append("## 原始代码\n")
    md.append("```jass")
    md.append(code)
    md.append("```\n")

    # API 依赖
    md.append("## JASS API 依赖\n")
    md.append("| API | 行偏移 | 类别 | Lua 替代 |")
    md.append("|-----|--------|------|----------|")
    for api_name, usages in sorted(apis.items(), key=lambda x: -len(x[1])):
        categories = set(u['category'] for u in usages)
        lines_str = ', '.join(str(u['line_offset']) for u in usages[:3])
        lua_alt = ECS_SUGGESTIONS.get(list(categories)[0], '视具体情况')
        md.append(f"| {api_name} | {lines_str} | {', '.join(categories)} | {lua_alt} |")
    md.append("")

    # Hashtable 操作
    if ht_ops:
        md.append("## Hashtable 操作\n")
        md.append("| Hashtable | Key | SubKey | 操作 | 行偏移 |")
        md.append("|-----------|-----|--------|------|--------|")
        for op in ht_ops:
            md.append(f"| {op['hashtable']} | {op['key']} | {op['subkey']} | {op['action']}{op['type']} | {op['line_offset']} |")
        md.append("")

    # ECS 映射
    md.append("## ECS 映射建议\n")
    md.append(f"- **事件**: {event_type} → EventManager.subscribe('{event_type}')")

    # 根据 API 推荐组件
    components = set()
    systems = set()
    for api_name in apis:
        if api_name in ('GetEventDamage', 'UnitDamageTarget'):
            components.add('OnDamageComp')
            systems.add('DamageSystem')
        if api_name in ('GetManipulatedItem', 'GetSoldItem', 'CreateItem', 'CreateItemLoc'):
            components.add('InventoryComp')
            systems.add('ItemSystem')
        if api_name in ('GetSpellAbilityId',):
            components.add('SkillComp')
            systems.add('SkillSystem')
    if 'UNIT_DEATH' == event_type:
        systems.add('DeathSystem')
        components.add('DeathComp')

    md.append(f"- **组件**: {', '.join(sorted(components)) if components else '根据具体逻辑确定'}")
    md.append(f"- **系统**: {', '.join(sorted(systems)) if systems else '根据具体逻辑确定'}")
    md.append("")

    # 已知问题
    if issues:
        md.append("## 已知问题\n")
        for issue in issues:
            md.append(f"- {issue}")
        md.append("")

    md.append("---\n")
    md.append(f"> 将以上分析粘贴给 `/war3-dev-guide`，创建对应的 ECS Lua 实现。\n")

    return '\n'.join(md)


def main():
    parser = argparse.ArgumentParser(description='提取并分析单个 JASS 触发器')
    parser.add_argument('jass_file', help='war3map.j 文件路径')
    parser.add_argument('trigger_name', help='触发器函数名')
    parser.add_argument('--output', '-o', help='输出路径', default=None)
    args = parser.parse_args()

    if not os.path.exists(args.jass_file):
        print(f"错误: 文件不存在: {args.jass_file}")
        sys.exit(1)

    with open(args.jass_file, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()

    code = find_function(content, args.trigger_name)
    if not code:
        print(f"错误: 未找到触发器函数: {args.trigger_name}")
        # 尝试模糊匹配
        matches = re.findall(rf'function\s+(\w*{re.escape(args.trigger_name)}\w*)\s+takes', content)
        if matches:
            print(f"  可能的匹配: {matches[:10]}")
        sys.exit(1)

    start_line, end_line = find_function_lines(content, args.trigger_name)
    analysis = generate_analysis(args.trigger_name, code, start_line, end_line, content)

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(analysis)
        print(f"分析已写入: {args.output}")
    else:
        print(analysis)


if __name__ == '__main__':
    main()
