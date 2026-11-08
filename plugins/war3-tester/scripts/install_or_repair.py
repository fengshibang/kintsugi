#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
install_or_repair.py - War3 Auto Test & Named Pipe Agent 一键安装 / 体检 / 修复命令行工具

用法示例：
  # 1. 只读体检（检查地图项目的 DLL、Lua Agent 模块、-test on 钩子及插件缓存）
  python install_or_repair.py --check --source-dir D:\\maps\\wzns --war3-dir D:\\war3

  # 2. 一键安装/修复全部测试与 Agent 功能（默认模式）
  python install_or_repair.py --repair --source-dir D:\\maps\\wzns --war3-dir D:\\war3

  # 3. 修复后顺便重编译地图 (.w3x)
  python install_or_repair.py --repair --source-dir D:\\maps\\wzns --war3-dir D:\\war3 --compile
"""

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PLUGIN_ROOT = SCRIPT_DIR.parent
SERVER_DIR = PLUGIN_ROOT / "server"
sys.path.insert(0, str(SERVER_DIR))

from config import Config
from environment_provisioner import EnvironmentProvisioner
from env_bridge import create_executor


def main():
    parser = argparse.ArgumentParser(
        description="War3 Tester & Named Pipe Agent 一键安装 / 体检 / 修复工具"
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--repair", action="store_true", help="安装缺失并修复损坏组件（默认）")
    mode_group.add_argument("--install", action="store_true", help="仅增量安装缺失组件（不覆盖已有 Lua 脚本）")
    mode_group.add_argument("--check", action="store_true", help="只读体检模式（Doctor），不修改任何文件")

    parser.add_argument("--source-dir", type=str, default=None, help="目标地图项目根目录（如 D:\\maps\\wzns）")
    parser.add_argument("--war3-dir", type=str, default=None, help="War3 1.27 安装目录（如 D:\\war3）")
    parser.add_argument(
        "--components",
        nargs="+",
        default=["socket", "http", "nopause", "agent_bridge", "agent_lua", "entry_hook", "plugin_sync"],
        help="指定要处理的组件列表",
    )
    parser.add_argument("--compile", action="store_true", help="安装/修复完成后自动调用 w2l.exe slk 重编译地图")
    args = parser.parse_args()

    mode = "check" if args.check else ("install" if args.install else "repair")
    proj_root = Path(args.source_dir).resolve() if args.source_dir else Path.cwd().resolve()

    cfg = Config(project_root=proj_root if (proj_root / "w3x2lni").exists() else None)
    provisioner = EnvironmentProvisioner(cfg, PLUGIN_ROOT)

    result = provisioner.setup({
        "source_dir": str(proj_root),
        "war3_dir": args.war3_dir,
        "mode": mode,
        "components": args.components,
    })

    text = result["content"][0]["text"]
    print(text)

    if args.compile and mode != "check" and not result.get("isError"):
        print("\n=== 正在重编译地图 (w2l.exe slk) ===")
        executor = create_executor(cfg)
        comp = executor.compile(str(proj_root))
        if comp.get("success"):
            print(f"[OK] 地图编译成功：{comp.get('message', '')}")
        else:
            print(f"[FAIL] 地图编译失败：{comp.get('error', '未知错误')}")
            sys.exit(1)

    sys.exit(1 if result.get("isError") else 0)


if __name__ == "__main__":
    main()
