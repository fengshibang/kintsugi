#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Config 单测 - 覆盖 resolve_source_dir 新方法

v0.19.3: B-2b 收敛 source_dir 解析链,新增 resolve_source_dir 方法。
覆盖三种输入:有值 / None / 空串。
"""

import sys
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

# 确保能 import 同目录下的 config
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config


def test_resolve_source_dir_with_value():
    """resolve_source_dir: 传入有效路径时,返回 resolve_path 解析后的绝对路径字符串"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        config = Config(project_root=tmpdir)

        # 传入相对路径
        result = config.resolve_source_dir('subdir')
        expected = str(config.resolve_path('subdir'))
        assert result == expected, f"应返回 resolve_path 解析结果,实际: {result}, 期望: {expected}"
        assert isinstance(result, str), f"应返回字符串,实际: {type(result)}"

        # 传入绝对路径
        abs_path = tmpdir / 'another_dir'
        result = config.resolve_source_dir(str(abs_path))
        expected = str(config.resolve_path(str(abs_path)))
        assert result == expected, f"绝对路径应返回 resolve_path 解析结果,实际: {result}, 期望: {expected}"

    print("  PASS test_resolve_source_dir_with_value")


def test_resolve_source_dir_with_none():
    """resolve_source_dir: 传入 None 时,返回 compile_source_dir 的字符串形式"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        config = Config(project_root=tmpdir)

        # 默认 compile_source_dir = project_root
        result = config.resolve_source_dir(None)
        expected = str(config.compile_source_dir)
        assert result == expected, f"None 应回退 compile_source_dir,实际: {result}, 期望: {expected}"
        assert isinstance(result, str), f"应返回字符串,实际: {type(result)}"

    print("  PASS test_resolve_source_dir_with_none")


def test_resolve_source_dir_with_empty_string():
    """resolve_source_dir: 传入空串时,返回 compile_source_dir 的字符串形式"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        config = Config(project_root=tmpdir)

        # 空串应视为 falsy,回退 compile_source_dir
        result = config.resolve_source_dir('')
        expected = str(config.compile_source_dir)
        assert result == expected, f"空串应回退 compile_source_dir,实际: {result}, 期望: {expected}"
        assert isinstance(result, str), f"应返回字符串,实际: {type(result)}"

    print("  PASS test_resolve_source_dir_with_empty_string")


def test_resolve_source_dir_custom_compile_source_dir():
    """resolve_source_dir: compile_source_dir 非默认值时,None 应回退到自定义值"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        config = Config(project_root=tmpdir)

        # 修改 compile_source_dir
        custom_dir = tmpdir / 'custom_source'
        custom_dir.mkdir()
        config.compile_source_dir = custom_dir

        result = config.resolve_source_dir(None)
        expected = str(custom_dir)
        assert result == expected, f"None 应回退自定义 compile_source_dir,实际: {result}, 期望: {expected}"

        result = config.resolve_source_dir('')
        assert result == expected, f"空串应回退自定义 compile_source_dir,实际: {result}, 期望: {expected}"

    print("  PASS test_resolve_source_dir_custom_compile_source_dir")


if __name__ == "__main__":
    print("=== Config.resolve_source_dir 单测 ===")
    tests = [
        test_resolve_source_dir_with_value,
        test_resolve_source_dir_with_none,
        test_resolve_source_dir_with_empty_string,
        test_resolve_source_dir_custom_compile_source_dir,
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

    print(f"\n结果:{passed} 通过,{failed} 失败,共 {len(tests)} 条")
    sys.exit(1 if failed else 0)
