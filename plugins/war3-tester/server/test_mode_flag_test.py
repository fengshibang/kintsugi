#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TestModeFlag 单测

覆盖：enable / disable / is_disabled / write_after_test / legacy 清理
全部使用临时目录，不依赖外部服务
"""

import sys
import os
import tempfile
import shutil
import logging
from pathlib import Path

# 确保能 import 同目录下的 test_mode_flag
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_mode_flag import TestModeFlag


def _make_logger():
    """创建测试用 logger（静默）"""
    logger = logging.getLogger('test_mode_flag_test')
    logger.setLevel(logging.DEBUG)
    if not logger.handlers:
        logger.addHandler(logging.NullHandler())
    return logger


def _make_test_dir(tmpdir):
    """创建测试目录（模拟 test_dir）"""
    test_dir = Path(tmpdir) / 'auto-test'
    test_dir.mkdir()
    return test_dir


def test_enable_deletes_off_file():
    """enable: 删除 _war3_tester/_test_off.lua"""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = _make_test_dir(tmpdir)
        flag = TestModeFlag(logger=_make_logger())

        # 先 disable 创建标志
        flag.disable(test_dir)
        assert flag.is_disabled(test_dir), "disable 后标志应存在"

        # enable 删除标志
        result = flag.enable(test_dir)
        assert result is True, "enable 应返回 True"
        assert not flag.is_disabled(test_dir), "enable 后标志应不存在"

    print("  PASS test_enable_deletes_off_file")


def test_enable_idempotent_when_no_file():
    """enable: 标志不存在时也返回 True"""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = _make_test_dir(tmpdir)
        flag = TestModeFlag(logger=_make_logger())

        result = flag.enable(test_dir)
        assert result is True, "标志不存在时 enable 也应返回 True"

    print("  PASS test_enable_idempotent_when_no_file")


def test_disable_writes_off_file():
    """disable: 写入 _war3_tester/_test_off.lua"""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = _make_test_dir(tmpdir)
        flag = TestModeFlag(logger=_make_logger())

        result = flag.disable(test_dir)
        assert result is True, "disable 应返回 True"
        assert flag.is_disabled(test_dir), "disable 后标志应存在"

        # 检查内容
        off_path = test_dir / '_war3_tester' / '_test_off.lua'
        content = off_path.read_text(encoding='utf-8')
        assert 'return true' in content, "内容应包含 return true"
        assert 'toggle_test' in content, "内容应包含 toggle_test 来源注释"

    print("  PASS test_disable_writes_off_file")


def test_disable_clears_target_and_run_auto():
    """disable: 同时清理 _target_test.lua 和 run_auto_test.lua"""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = _make_test_dir(tmpdir)
        flag = TestModeFlag(logger=_make_logger())

        # 创建残留文件
        wt_dir = test_dir / '_war3_tester'
        wt_dir.mkdir(parents=True)
        (wt_dir / '_target_test.lua').write_text('old target')
        (test_dir / 'run_auto_test.lua').write_text('old run_auto')

        flag.disable(test_dir)

        assert not (wt_dir / '_target_test.lua').exists(), "_target_test.lua 应被清理"
        assert not (test_dir / 'run_auto_test.lua').exists(), "run_auto_test.lua 应被清理"

    print("  PASS test_disable_clears_target_and_run_auto")


def test_legacy_cleanup_on_enable():
    """enable: 清理 test_dir 根的 legacy _test_off.lua"""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = _make_test_dir(tmpdir)
        flag = TestModeFlag(logger=_make_logger())

        # 创建 legacy 残留
        legacy_off = test_dir / '_test_off.lua'
        legacy_off.write_text('legacy')
        assert legacy_off.exists()

        flag.enable(test_dir)

        assert not legacy_off.exists(), "legacy _test_off.lua 应被清理"

    print("  PASS test_legacy_cleanup_on_enable")


def test_legacy_cleanup_on_disable():
    """disable: 清理 test_dir 根的 legacy _test_off.lua 和 _target_test.lua"""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = _make_test_dir(tmpdir)
        flag = TestModeFlag(logger=_make_logger())

        # 创建 legacy 残留
        (test_dir / '_test_off.lua').write_text('legacy off')
        (test_dir / '_target_test.lua').write_text('legacy target')

        flag.disable(test_dir)

        assert not (test_dir / '_test_off.lua').exists(), "legacy _test_off.lua 应被清理"
        assert not (test_dir / '_target_test.lua').exists(), "legacy _target_test.lua 应被清理"

    print("  PASS test_legacy_cleanup_on_disable")


def test_write_after_test():
    """write_after_test: 写 _war3_tester/_test_off.lua（内容不同于 disable）"""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = _make_test_dir(tmpdir)
        flag = TestModeFlag(logger=_make_logger())

        result = flag.write_after_test(test_dir)
        assert result is True, "write_after_test 应返回 True"
        assert flag.is_disabled(test_dir), "write_after_test 后标志应存在"

        # 检查内容（与 disable 不同，来源注释不同）
        off_path = test_dir / '_war3_tester' / '_test_off.lua'
        content = off_path.read_text(encoding='utf-8')
        assert 'return true' in content, "内容应包含 return true"
        assert '_run_single_test' in content, "内容应包含 _run_single_test 来源注释"

    print("  PASS test_write_after_test")


def test_is_disabled_returns_false_when_no_file():
    """is_disabled: 标志不存在时返回 False"""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = _make_test_dir(tmpdir)
        flag = TestModeFlag(logger=_make_logger())

        assert not flag.is_disabled(test_dir), "无标志文件时应返回 False"

    print("  PASS test_is_disabled_returns_false_when_no_file")


def test_war3_tester_dir_created_automatically():
    """_war3_tester/ 目录在操作时自动创建"""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = _make_test_dir(tmpdir)
        flag = TestModeFlag(logger=_make_logger())

        wt_dir = test_dir / '_war3_tester'
        assert not wt_dir.exists(), "初始时 _war3_tester 不应存在"

        flag.enable(test_dir)
        assert wt_dir.exists(), "enable 后 _war3_tester 应被创建"

    print("  PASS test_war3_tester_dir_created_automatically")


if __name__ == "__main__":
    print("=== TestModeFlag 单测 ===")
    tests = [
        test_enable_deletes_off_file,
        test_enable_idempotent_when_no_file,
        test_disable_writes_off_file,
        test_disable_clears_target_and_run_auto,
        test_legacy_cleanup_on_enable,
        test_legacy_cleanup_on_disable,
        test_write_after_test,
        test_is_disabled_returns_false_when_no_file,
        test_war3_tester_dir_created_automatically,
    ]

    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"  FAIL {t.__name__}: {e}")

    print(f"\n结果：{passed} 通过，{failed} 失败，共 {len(tests)} 条")
    sys.exit(1 if failed else 0)
