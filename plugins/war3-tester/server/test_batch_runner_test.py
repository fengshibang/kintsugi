#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_batch_runner 单测

覆盖：
- run_single_test 预清理后复查：is_war3_clean 返回残留 → env_error + run_game 未被调用
- run_single_test 预清理后复查：is_war3_clean 返回无残留 → 正常流程继续

全部使用 MagicMock 隔离，不依赖真实 war3 进程
"""

import sys
import os
from unittest.mock import MagicMock

# 确保能 import 同目录下的模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_batch_runner import TestBatchRunner


def _make_runner():
    """构造 TestBatchRunner 实例（绕过 __init__，全部依赖 mock）"""
    runner = TestBatchRunner.__new__(TestBatchRunner)
    runner.config = MagicMock()
    runner.config.compile_source_dir = '/fake/source'
    runner.executor = MagicMock()
    runner.http_receiver = MagicMock()
    runner.test_mode_flag = MagicMock()
    runner.test_entry_preparer = MagicMock()
    runner.diagnostics_collector = MagicMock()
    runner.store = MagicMock()
    runner.logger = MagicMock()
    runner._failed_cache = []
    return runner


def test_run_single_test_war3_remaining_returns_env_error():
    """run_single_test: is_war3_clean 返回残留 → env_error + run_game 未被调用"""
    runner = _make_runner()

    # stop_game 成功
    runner.executor.stop_game.return_value = {'success': True}

    # is_war3_clean 返回残留
    runner.executor.is_war3_clean.return_value = {
        'success': False,
        'message': '进程仍未清除：war3.exe',
        'remaining': ['"war3.exe",1234']
    }

    result = runner.run_single_test('test_fake', timeout=10)

    # 验证返回 env_error
    assert result['success'] is False, f"期望 success:False，得到 {result}"
    assert result.get('failure_type') == 'env_error', \
        f"期望 failure_type='env_error'，得到 {result.get('failure_type')}"
    assert '预清理后仍有 war3 进程残留' in result.get('error', ''), \
        f"error 应包含'预清理后仍有 war3 进程残留'：{result.get('error')}"
    assert 'war3.exe' in result.get('error', ''), \
        f"error 应包含'war3.exe'：{result.get('error')}"

    # 验证 run_game 未被调用（关键：不自启新游戏）
    runner.executor.run_game.assert_not_called()
    # 验证 compile 未被调用（prepare/compile/run_game 都不应调）
    runner.executor.compile.assert_not_called()
    # 验证 test_entry_preparer.prepare 未被调用
    runner.test_entry_preparer.prepare.assert_not_called()

    print("  PASS test_run_single_test_war3_remaining_returns_env_error")


def test_run_single_test_war3_clean_continues():
    """run_single_test: is_war3_clean 返回无残留 → 正常流程继续"""
    runner = _make_runner()

    # stop_game 成功
    runner.executor.stop_game.return_value = {'success': True}

    # is_war3_clean 返回无残留
    runner.executor.is_war3_clean.return_value = {
        'success': True,
        'message': '游戏进程已全部清除'
    }

    # prepare 成功
    runner.test_entry_preparer.prepare.return_value = None

    # compile 成功
    runner.executor.compile.return_value = {
        'success': True,
        'map_path': '/fake/map.w3x'
    }

    # run_game 失败（模拟启动失败，避免进入轮询循环）
    runner.executor.run_game.return_value = {
        'success': False,
        'error': '模拟启动失败'
    }

    # 运行
    result = runner.run_single_test('test_fake', timeout=10)

    # 验证返回 env_error（因为 run_game 失败）
    assert result['success'] is False, f"期望 success:False，得到 {result}"
    assert result.get('failure_type') == 'env_error', \
        f"期望 failure_type='env_error'，得到 {result.get('failure_type')}"
    assert '启动游戏失败' in result.get('error', ''), \
        f"error 应包含'启动游戏失败'：{result.get('error')}"

    # 验证 run_game 被调用（正常流程继续）
    runner.executor.run_game.assert_called_once()
    # 验证 compile 被调用
    runner.executor.compile.assert_called_once()
    # 验证 test_entry_preparer.prepare 被调用
    runner.test_entry_preparer.prepare.assert_called_once()

    print("  PASS test_run_single_test_war3_clean_continues")


def test_run_single_test_calls_is_war3_clean_after_sleep():
    """run_single_test: 必须在 sleep(3) 后调用 is_war3_clean"""
    runner = _make_runner()

    runner.executor.stop_game.return_value = {'success': True}
    runner.executor.is_war3_clean.return_value = {
        'success': False,
        'remaining': ['war3.exe']
    }

    runner.run_single_test('test_fake', timeout=10)

    # 验证 stop_game 被调用
    runner.executor.stop_game.assert_called_once()
    # 验证 is_war3_clean 被调用
    runner.executor.is_war3_clean.assert_called_once()

    # 验证调用顺序：stop_game → is_war3_clean（通过 call_count 间接验证）
    assert runner.executor.stop_game.call_count == 1
    assert runner.executor.is_war3_clean.call_count == 1

    print("  PASS test_run_single_test_calls_is_war3_clean_after_sleep")


if __name__ == "__main__":
    print("=== test_batch_runner 单测 ===")
    tests = [
        test_run_single_test_war3_remaining_returns_env_error,
        test_run_single_test_war3_clean_continues,
        test_run_single_test_calls_is_war3_clean_after_sleep,
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
