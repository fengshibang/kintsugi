#!/usr/bin/env python3
"""
sync_from_rouge_lua.py — 从 rouge_lua 同步框架到插件 assets/

功能:
  把 rouge_lua (MoeHero 地图) 的 map/ 目录同步到插件 assets/,
  复现各 ticket 的清洗规则(剥硬编码/剥测试钩子/提炼通用脚手架),
  幂等(重复跑结果一致),保护 optional-modules.json 不被覆盖。

用法:
  python sync_from_rouge_lua.py [--dry-run] [--source DIR] [--target DIR]

参数:
  --dry-run       只打印会执行的操作,不实际修改文件
  --source DIR    rouge_lua 根目录(默认: D:/maps/rouge_lua)
  --target DIR    插件根目录(默认: D:/maps/war3-lua-framework-plugin)

自动同步(可正确复现):
  - lib/: 原样拷(ticket 01)
  - path.lua: 剥 D:\\war3项目\\wjsg\\map\\ 硬编码分支(ticket 01)
  - script/init.lua: 剥 test_runner/test_reporter 钩子(ticket 01)
  - plugin_main.lua: 剥 japi.SetOwner 行(ticket 01)
  - (key) / callback: 原样拷(ticket 01)
  - bin/: socket.dll + libwinpthread-1.dll 原样拷(ticket 06)
  - fonts/: fonts.ttf 原样拷(ticket 06)
  - tools/: 排除 MoeHero py + 临时 + __pycache__,顶层脚本已参数化直接拷(ticket 09)

人工提炼(只报告差异,不自动覆盖):
  - src/ 脚手架(ticket 04): core/model/types + PlayerObj/UnitObj 桩
  - src/util/(ticket 07): 9 个通用工具(排 SelfCheck)
  - src/{entities,components,systems}/(ticket 08): 42 个通用 RPG 实体层
  这些文件是人工从 rouge_lua 提炼+剥 MoeHero 专属,sync 只检测差异并提示"需人工 re-提炼"

保护:
  - optional-modules.json: sync 不覆盖(插件配置,非 rouge_lua 同步源)
  - NOTICE: sync 后追加时间戳 + 来源标注

作者: ticket 10 产物
日期: 2026-07-25
"""

import os
import re
import sys
import shutil
import argparse
from pathlib import Path
from datetime import datetime


# ============================================================================
# 配置
# ============================================================================

# rouge_lua 源路径(默认)
DEFAULT_SOURCE = "D:/maps/rouge_lua"
# 插件目标路径(默认)
DEFAULT_TARGET = "D:/maps/war3-lua-framework-plugin"

# 脚手架核心白名单(ticket 04) — 从 rouge_lua src/ 提炼的通用核心
SCAFFOLD_WHITELIST = [
    "types/init.lua",
    "types/Attribute.lua",
    "types/point.lua",
    "core/init.lua",
    "core/Game.lua",
    "core/GameEvent.lua",
    "core/Selector.lua",
    "core/state.lua",
    "core/AssetsManager.lua",
    "model/init.lua",
    "model/enum.lua",
    "model/UnitModelComp.lua",
    "model/UnitNumeric.lua",
    "model/UnitNumericMap.lua",
    "entities/init.lua",
    "entities/PlayerObj.lua",
    "entities/UnitObj.lua",
]

# util 白名单(ticket 07) — 排除 SelfCheck(MoeHero 专属)
UTIL_WHITELIST = [
    "EventPool.lua",
    "fourcc.lua",
    "textTag.lua",
    "destroyTextTagDelayed.lua",
    "rushSlide.lua",
    "unitAlive.lua",
    "unitGetItemOfType.lua",
    "unitHasItem.lua",
    "unitSpawn.lua",
]

# entities 白名单(ticket 08)
ENTITIES_WHITELIST = [
    "init.lua",
    "AuraObj.lua",
    "BuffObj.lua",
    "EffectObj.lua",
    "SkillObj.lua",
]

# components 白名单(ticket 08)
COMPONENTS_WHITELIST = [
    "init.lua",
    "BulletComp.lua",
    "EffectDamageComp.lua",
    "EquipComp.lua",
    "HeroComp.lua",
    "OnDamageComp.lua",
    "TweenComp.lua",
    "Restriction/init.lua",
    "Restriction/AbunComp.lua",
    "Restriction/AvoidDeathComp.lua",
    "Restriction/ControlFreeComp.lua",
    "Restriction/HideComp.lua",
    "Restriction/InvulnerableComp.lua",
    "Restriction/OneDamageComp.lua",
    "Restriction/StealthComp.lua",
    "Restriction/StopMoveComp.lua",
    "Restriction/StunComp.lua",
]

# systems 白名单(ticket 08)
SYSTEMS_WHITELIST = [
    "init.lua",
    "BuffSystem.lua",
    "BulletSystem.lua",
    "DamageSystem.lua",
    "EffectSystem.lua",
    "EquipSystem.lua",
    "SkillSystem.lua",
    "TweenSystem.lua",
    "Restriction/init.lua",
    "Restriction/定身.lua",
    "Restriction/缴械.lua",
    "Restriction/免死.lua",
    "Restriction/隐身.lua",
    "Restriction/隐藏.lua",
    "Restriction/免控.lua",
    "Restriction/晕眩.lua",
    "Restriction/无敌.lua",
]

# tools 排除模式(ticket 09)
TOOLS_EXCLUDE_PATTERNS = [
    r".*\.py$",  # MoeHero 专属 Python 脚本
    r".*__pycache__.*",  # Python 缓存
    r".*\.bak$",  # 备份文件
    r".*/backups/.*",  # jasshelper/backups
    r".*/logs/.*",  # jasshelper/logs
    r".*/log/.*",  # w3x2lni/log
    r"test_selector_pool\.lua",  # 临时测试
]


# ============================================================================
# 清洗函数
# ============================================================================

def clean_path_lua(content: str) -> str:
    """
    清洗 path.lua — 剥 D:\war3项目\wjsg\map\ 硬编码分支(ticket 01)

    保留相对路径模式(else 分支),删除本地路径模式(if is_local 分支)。
    """
    # 匹配 if is_local then ... else ... end 结构
    # 保留 else 后的相对路径,删除 if 后的硬编码路径
    pattern = r"if is_local then\s+package\.path = package\.path \.\s*\";\".*?package\.local_map_path = \"D:\\\\war3项目\\\\wjsg\\\\map\\\\\"\s+else"

    # 替换为只保留 else
    replacement = r"if is_local then" + "\n    -- [sync] 本地路径分支已剥(硬编码 D:\\\\war3项目\\\\wjsg\\\\map\\\\)\n    -- 保留相对路径模式\nelse"

    cleaned = re.sub(pattern, replacement, content, flags=re.DOTALL)
    return cleaned


def clean_script_init_lua(content: str) -> str:
    """
    清洗 script/init.lua — 剥 test_runner/test_reporter 钩子(ticket 01)

    保留 require('script.lib') + require('script.src'),删除 war3-tester 钩子。
    """
    lines = content.split('\n')
    cleaned_lines = []
    skip_block = False

    for line in lines:
        # 检测 war3-tester 钩子块开始
        if re.search(r"--\s*war3-tester", line):
            skip_block = True
            continue

        # 检测块结束(end)
        if skip_block and line.strip() == "end)":
            skip_block = False
            continue

        # 跳过块内内容
        if skip_block:
            continue

        # 保留其他行
        cleaned_lines.append(line)

    return '\n'.join(cleaned_lines)


def clean_plugin_main_lua(content: str) -> str:
    """
    清洗 plugin_main.lua — 剥 japi.SetOwner 行(ticket 01)

    删除 `local japi = require 'jass.japi'` 和 `japi.SetOwner(...)` 行。
    """
    lines = content.split('\n')
    cleaned_lines = []

    for line in lines:
        # 跳过 japi 相关行
        if re.search(r"require\s+['\"]jass\.japi['\"]", line):
            continue
        if re.search(r"japi\.SetOwner", line):
            continue
        cleaned_lines.append(line)

    return '\n'.join(cleaned_lines)


# ============================================================================
# 同步操作
# ============================================================================

def should_exclude_tools(path: Path) -> bool:
    """检查 tools/ 下的文件是否应排除"""
    path_str = str(path).replace('\\', '/')
    for pattern in TOOLS_EXCLUDE_PATTERNS:
        if re.match(pattern, path_str):
            return True
    return False


def copy_file(src: Path, dst: Path, dry_run: bool = False, clean_fn=None):
    """拷贝单个文件,可选清洗函数"""
    if dry_run:
        action = "会拷贝"
        if clean_fn:
            action = "会拷贝+清洗"
        print(f"  {action}: {src} -> {dst}")
        return

    dst.parent.mkdir(parents=True, exist_ok=True)

    if clean_fn:
        # 读内容 → 清洗 → 写
        content = src.read_text(encoding='utf-8')
        cleaned = clean_fn(content)
        dst.write_text(cleaned, encoding='utf-8')
    else:
        # 直接拷(二进制或文本)
        shutil.copy2(src, dst)


def sync_lib(source: Path, target: Path, dry_run: bool):
    """同步 lib/ — 原样拷(ticket 01)"""
    print("\n[sync] lib/ — 原样拷 (ticket 01)")
    src_lib = source / "map" / "script" / "lib"
    dst_lib = target / "assets" / "lib"

    if not src_lib.exists():
        print(f"  警告: 源不存在 {src_lib}")
        return

    if dry_run:
        print(f"  会拷贝: {src_lib} -> {dst_lib}")
        return

    # 删除旧目录,重新拷
    if dst_lib.exists():
        shutil.rmtree(dst_lib)
    shutil.copytree(src_lib, dst_lib)


def sync_framework_bootstrap(source: Path, target: Path, dry_run: bool):
    """同步 framework/ 引导链 — 带清洗(ticket 01)"""
    print("\n[sync] framework/ 引导链 — 带清洗 (ticket 01)")

    # plugin_main.lua — 剥 japi.SetOwner
    src = source / "map" / "plugin_main.lua"
    dst = target / "assets" / "framework" / "plugin_main.lua"
    if src.exists():
        copy_file(src, dst, dry_run, clean_plugin_main_lua)

    # path.lua — 剥硬编码
    src = source / "map" / "path.lua"
    dst = target / "assets" / "framework" / "path.lua"
    if src.exists():
        copy_file(src, dst, dry_run, clean_path_lua)

    # script/init.lua — 剥测试钩子
    src = source / "map" / "script" / "init.lua"
    dst = target / "assets" / "framework" / "script" / "init.lua"
    if src.exists():
        copy_file(src, dst, dry_run, clean_script_init_lua)

    # (key) / callback — 原样拷
    for name in ["(key)", "callback"]:
        src = source / "map" / name
        dst = target / "assets" / "framework" / name
        if src.exists():
            copy_file(src, dst, dry_run)


def sync_framework_scaffold(source: Path, target: Path, dry_run: bool):
    """报告 framework/script/src/ 脚手架差异 — 不自动覆盖(ticket 04 人工提炼)"""
    print("\n[report] framework/script/src/ 脚手架 — 人工提炼,只报告差异 (ticket 04)")

    src_root = source / "map" / "script" / "src"
    dst_root = target / "assets" / "framework" / "script" / "src"

    diff_count = 0
    for rel_path in SCAFFOLD_WHITELIST:
        src = src_root / rel_path
        dst = dst_root / rel_path
        if src.exists() and dst.exists():
            # 比较文件差异
            src_content = src.read_text(encoding='utf-8')
            dst_content = dst.read_text(encoding='utf-8')
            if src_content != dst_content:
                print(f"  ⚠️  差异: {rel_path} (rouge_lua 有更新,需人工 re-提炼)")
                diff_count += 1
        elif src.exists() and not dst.exists():
            print(f"  ⚠️  新增: {rel_path} (rouge_lua 有,插件无,需人工判断是否提炼)")
            diff_count += 1
        elif not src.exists():
            print(f"  警告: 源不存在 {src}")

    if diff_count == 0:
        print("  ✓ 无差异")
    else:
        print(f"  共 {diff_count} 个文件需人工 re-提炼")


def sync_framework_util(source: Path, target: Path, dry_run: bool):
    """报告 framework/script/src/util/ 差异 — 不自动覆盖(ticket 07 人工提炼)"""
    print("\n[report] framework/script/src/util/ — 人工提炼,只报告差异 (ticket 07)")

    src_root = source / "map" / "script" / "src" / "util"
    dst_root = target / "assets" / "framework" / "script" / "src" / "util"

    diff_count = 0
    for name in UTIL_WHITELIST:
        src = src_root / name
        dst = dst_root / name
        if src.exists() and dst.exists():
            src_content = src.read_text(encoding='utf-8')
            dst_content = dst.read_text(encoding='utf-8')
            if src_content != dst_content:
                print(f"  ⚠️  差异: util/{name} (rouge_lua 有更新,需人工 re-提炼)")
                diff_count += 1
        elif src.exists() and not dst.exists():
            print(f"  ⚠️  新增: util/{name} (rouge_lua 有,插件无,需人工判断是否提炼)")
            diff_count += 1
        elif not src.exists():
            print(f"  警告: 源不存在 {src}")

    if diff_count == 0:
        print("  ✓ 无差异")
    else:
        print(f"  共 {diff_count} 个文件需人工 re-提炼")


def sync_framework_entities_components_systems(source: Path, target: Path, dry_run: bool):
    """报告 framework/script/src/{entities,components,systems}/ 差异 — 不自动覆盖(ticket 08 人工提炼)"""
    print("\n[report] framework/script/src/{entities,components,systems}/ — 人工提炼,只报告差异 (ticket 08)")

    src_root = source / "map" / "script" / "src"
    dst_root = target / "assets" / "framework" / "script" / "src"

    diff_count = 0

    # entities
    for rel_path in ENTITIES_WHITELIST:
        src = src_root / "entities" / rel_path
        dst = dst_root / "entities" / rel_path
        if src.exists() and dst.exists():
            src_content = src.read_text(encoding='utf-8')
            dst_content = dst.read_text(encoding='utf-8')
            if src_content != dst_content:
                print(f"  ⚠️  差异: entities/{rel_path} (rouge_lua 有更新,需人工 re-提炼)")
                diff_count += 1
        elif src.exists() and not dst.exists():
            print(f"  ⚠️  新增: entities/{rel_path} (rouge_lua 有,插件无,需人工判断是否提炼)")
            diff_count += 1
        elif not src.exists():
            print(f"  警告: 源不存在 {src}")

    # components
    for rel_path in COMPONENTS_WHITELIST:
        src = src_root / "components" / rel_path
        dst = dst_root / "components" / rel_path
        if src.exists() and dst.exists():
            src_content = src.read_text(encoding='utf-8')
            dst_content = dst.read_text(encoding='utf-8')
            if src_content != dst_content:
                print(f"  ⚠️  差异: components/{rel_path} (rouge_lua 有更新,需人工 re-提炼)")
                diff_count += 1
        elif src.exists() and not dst.exists():
            print(f"  ⚠️  新增: components/{rel_path} (rouge_lua 有,插件无,需人工判断是否提炼)")
            diff_count += 1
        elif not src.exists():
            print(f"  警告: 源不存在 {src}")

    # systems
    for rel_path in SYSTEMS_WHITELIST:
        src = src_root / "systems" / rel_path
        dst = dst_root / "systems" / rel_path
        if src.exists() and dst.exists():
            src_content = src.read_text(encoding='utf-8')
            dst_content = dst.read_text(encoding='utf-8')
            if src_content != dst_content:
                print(f"  ⚠️  差异: systems/{rel_path} (rouge_lua 有更新,需人工 re-提炼)")
                diff_count += 1
        elif src.exists() and not dst.exists():
            print(f"  ⚠️  新增: systems/{rel_path} (rouge_lua 有,插件无,需人工判断是否提炼)")
            diff_count += 1
        elif not src.exists():
            print(f"  警告: 源不存在 {src}")

    # IdHelp.lua — 特殊:这是 lib/util/ 的文件,可以自动同步
    src = source / "map" / "script" / "lib" / "util" / "IdHelp.lua"
    dst = target / "assets" / "framework" / "script" / "src" / "util" / "IdHelp.lua"
    if src.exists():
        if dst.exists():
            src_content = src.read_text(encoding='utf-8')
            dst_content = dst.read_text(encoding='utf-8')
            if src_content != dst_content:
                print(f"  ⚠️  差异: util/IdHelp.lua (rouge_lua 有更新,需人工 re-提炼)")
                diff_count += 1
        else:
            print(f"  ⚠️  新增: util/IdHelp.lua (rouge_lua 有,插件无,需人工判断是否提炼)")
            diff_count += 1
    else:
        print(f"  警告: 源不存在 {src}")

    if diff_count == 0:
        print("  ✓ 无差异")
    else:
        print(f"  共 {diff_count} 个文件需人工 re-提炼")


def sync_bin(source: Path, target: Path, dry_run: bool):
    """同步 bin/ — 二进制(ticket 06)"""
    print("\n[sync] bin/ — 二进制 (ticket 06)")

    src_bin = source / "map"
    dst_bin = target / "assets" / "bin"

    for name in ["socket.dll", "libwinpthread-1.dll"]:
        src = src_bin / name
        dst = dst_bin / name
        if src.exists():
            copy_file(src, dst, dry_run)
        else:
            print(f"  警告: 源不存在 {src}")


def sync_fonts(source: Path, target: Path, dry_run: bool):
    """同步 fonts/ — 二进制(ticket 06)"""
    print("\n[sync] fonts/ — 二进制 (ticket 06)")

    src = source / "map" / "fonts.ttf"
    dst = target / "assets" / "fonts" / "fonts.ttf"

    if src.exists():
        copy_file(src, dst, dry_run)
    else:
        print(f"  警告: 源不存在 {src}")


def sync_tools(source: Path, target: Path, dry_run: bool):
    """同步 tools/ — 排除 MoeHero py + 临时(ticket 09)"""
    print("\n[sync] tools/ — 排除 MoeHero py + 临时 (ticket 09)")

    src_tools = source / "tools"
    dst_tools = target / "assets" / "tools"

    if not src_tools.exists():
        print(f"  警告: 源不存在 {src_tools}")
        return

    if dry_run:
        print(f"  会拷贝: {src_tools} -> {dst_tools} (排除模式匹配)")
        return

    # 删除旧目录,重新拷
    if dst_tools.exists():
        shutil.rmtree(dst_tools)

    # 递归拷,排除匹配模式
    def ignore_fn(directory, contents):
        ignored = []
        for item in contents:
            item_path = Path(directory) / item
            if should_exclude_tools(item_path):
                ignored.append(item)
        return ignored

    shutil.copytree(src_tools, dst_tools, ignore=ignore_fn)


def update_notice(target: Path, dry_run: bool):
    """更新 NOTICE — 追加时间戳 + 来源标注"""
    print("\n[sync] NOTICE — 追加时间戳")

    notice_path = target / "NOTICE"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    update_line = f"\n\n## Sync 记录\n- 最后同步: {timestamp} (sync_from_rouge_lua.py)\n- 来源: rouge_lua (MoeHero 地图) map/ 目录\n"

    if dry_run:
        print(f"  会追加到 {notice_path}:\n{update_line}")
        return

    with open(notice_path, 'a', encoding='utf-8') as f:
        f.write(update_line)


# ============================================================================
# 主流程
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="从 rouge_lua 同步框架到插件 assets/")
    parser.add_argument("--dry-run", action="store_true", help="只打印操作,不实际修改")
    parser.add_argument("--source", default=DEFAULT_SOURCE, help="rouge_lua 根目录")
    parser.add_argument("--target", default=DEFAULT_TARGET, help="插件根目录")
    args = parser.parse_args()

    source = Path(args.source)
    target = Path(args.target)

    print("=" * 70)
    print("sync_from_rouge_lua.py — 从 rouge_lua 同步框架到插件 assets/")
    print("=" * 70)
    print(f"源: {source}")
    print(f"目标: {target}")
    print(f"模式: {'DRY-RUN (不修改)' if args.dry_run else '实跑 (会修改)'}")

    # 检查源存在
    if not source.exists():
        print(f"\n错误: 源目录不存在 {source}")
        sys.exit(1)

    # 检查目标存在
    if not target.exists():
        print(f"\n错误: 目标目录不存在 {target}")
        sys.exit(1)

    # 执行同步
    sync_lib(source, target, args.dry_run)
    sync_framework_bootstrap(source, target, args.dry_run)
    sync_framework_scaffold(source, target, args.dry_run)
    sync_framework_util(source, target, args.dry_run)
    sync_framework_entities_components_systems(source, target, args.dry_run)
    sync_bin(source, target, args.dry_run)
    sync_fonts(source, target, args.dry_run)
    sync_tools(source, target, args.dry_run)

    # 更新 NOTICE
    update_notice(target, args.dry_run)

    print("\n" + "=" * 70)
    if args.dry_run:
        print("DRY-RUN 完成(未修改任何文件)")
    else:
        print("同步完成!")
    print("=" * 70)

    # 提醒
    print("\n提醒:")
    print("  ✓ 自动同步: lib/ + 引导链(plugin_main/path/script-init) + bin/ + fonts/ + tools/")
    print("  ⚠️  人工提炼: src/ 脚手架/util/entities/components/systems (只报告差异,不自动覆盖)")
    print("  - optional-modules.json 未被覆盖(插件配置)")
    print("  - 如 rouge_lua src/ 有更新,需人工 re-提炼后手动更新插件 assets/framework/script/src/")
    print("  - 建议先跑 --dry-run 检查,再实跑")


if __name__ == "__main__":
    main()
