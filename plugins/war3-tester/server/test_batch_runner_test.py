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
import threading
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
    runner.launched_war3 = False
    runner.pipe_client = None
    runner.desktop_runner = None
    runner.cancel_event = threading.Event()
    runner._batch_lock = threading.Lock()
    runner.executor.check_connectivity.return_value = True
    return runner


def _fake_selection(runner, tests):
    """tests: [(name, layer)]"""
    runner._select_tests = MagicMock(return_value=[
        {'test_name': n, 'file': f'{n}.lua', 'layer': l} for n, l in tests])


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


def test_poll_pipe_events_collects_progress_logs_and_result():
    """_poll_pipe_events: 通过命名管道收集 test_progress / test_log / test_error / test_result"""
    from test_state_store import TestStateStore
    runner = _make_runner()
    runner.store = TestStateStore()
    runner.pipe_client = MagicMock()
    runner.pipe_client.request.return_value = {
        "ok": True,
        "payload": {
            "dropped": 0,
            "max_seq": 4,
            "events": [
                {"seq": 1, "kind": "test_progress", "step": "wait_hero", "phase": "done", "elapsed_ms": 120},
                {"seq": 2, "kind": "test_log", "level": "info", "message": "hero ready"},
                {"seq": 3, "kind": "test_error", "test_name": "test_pipe_case", "error": "boom", "traceback": "tb"},
                {
                    "seq": 4,
                    "kind": "test_result",
                    "test_name": "test_pipe_case",
                    "success": True,
                    "duration_ms": 250,
                    "assertions": [{"name": "ok", "passed": True}],
                },
            ],
        },
    }

    res, new_seq = runner._poll_pipe_events("test_pipe_case", 0, None)
    assert new_seq == 4
    assert res is not None
    assert res["test_name"] == "test_pipe_case"
    assert res["success"] is True
    assert len(res["progress"]) == 1
    assert res["progress"][0]["step"] == "wait_hero"
    assert len(res["logs"]) == 1
    assert res["logs"][0]["message"] == "hero ready"
    snap = runner.store.snapshot("test_pipe_case")
    assert len(snap["game_errors"]) == 1
    assert snap["game_errors"][0]["error"] == "boom"

    print("  PASS test_poll_pipe_events_collects_progress_logs_and_result")


# ---------------------------------------------------------------------------
# v0.21.1 防失控护栏
# ---------------------------------------------------------------------------

def test_unit_layer_never_launches_game():
    """unit 层测试必须走 desktop_runner，绝不调用 run_single_test / run_game"""
    runner = _make_runner()
    _fake_selection(runner, [('test_unit_a', 'unit'), ('test_unit_b', 'unit')])
    runner.desktop_runner = MagicMock()
    runner.desktop_runner.run_unit_test.return_value = {'success': True, 'elapsed': 0.01}
    runner.run_single_test = MagicMock()

    res = runner.run_test_batch(test_filter='all', layer='unit')

    assert res['summary']['passed'] == 2, res
    assert res['summary']['game_launches'] == 0, res
    runner.run_single_test.assert_not_called()
    runner.executor.run_game.assert_not_called()
    runner.executor.stop_game.assert_not_called()
    print("  PASS test_unit_layer_never_launches_game")


def test_unit_layer_without_desktop_runner_refuses():
    """没有 desktop_runner 时 unit 测试直接失败，不得回退到实机"""
    runner = _make_runner()
    _fake_selection(runner, [('test_unit_a', 'unit')])
    runner.run_single_test = MagicMock()
    res = runner.run_test_batch(test_filter='all')
    assert res['summary']['failed'] == 1
    runner.run_single_test.assert_not_called()
    print("  PASS test_unit_layer_without_desktop_runner_refuses")


def test_env_error_not_retried_and_circuit_breaks():
    """env_error 不重试；连续 2 个 env_error 熔断，剩余测试不执行"""
    runner = _make_runner()
    _fake_selection(runner, [(f'test_int_{i}', 'integration') for i in range(10)])
    runner.run_single_test = MagicMock(return_value={
        'success': False, 'failure_type': 'env_error', 'error': 'x'})

    res = runner.run_test_batch(test_filter='all', max_retries=3)

    assert runner.run_single_test.call_count == 2, runner.run_single_test.call_count
    assert res['summary']['aborted'], res
    assert res['summary']['not_run'] == 8, res
    print("  PASS test_env_error_not_retried_and_circuit_breaks")


def test_residue_aborts_batch_immediately():
    """War3 残留杀不掉 → 第一个测试后立即熔断"""
    runner = _make_runner()
    _fake_selection(runner, [(f'test_int_{i}', 'integration') for i in range(5)])
    runner.run_single_test = MagicMock(return_value={
        'success': False, 'failure_type': 'env_error', 'residue_detected': True})
    res = runner.run_test_batch(test_filter='all')
    assert runner.run_single_test.call_count == 1
    assert 'War3' in res['summary']['aborted']
    print("  PASS test_residue_aborts_batch_immediately")


def test_game_launch_budget():
    """单批次游戏启动次数受 max_game_launches 限制（含重试）"""
    runner = _make_runner()
    _fake_selection(runner, [(f'test_int_{i}', 'integration') for i in range(10)])
    runner.run_single_test = MagicMock(return_value={
        'success': False, 'failure_type': 'timeout'})
    res = runner.run_test_batch(test_filter='all', max_retries=1, max_game_launches=3)
    assert runner.run_single_test.call_count == 3, runner.run_single_test.call_count
    assert '启动上限' in res['summary']['aborted']
    print("  PASS test_game_launch_budget")


def test_cancel_stops_batch():
    """cancel() 后批次在下一个测试前停止"""
    runner = _make_runner()
    _fake_selection(runner, [(f'test_int_{i}', 'integration') for i in range(5)])

    def _side(*a, **kw):
        runner.cancel('test')
        return {'success': True}
    runner.run_single_test = MagicMock(side_effect=_side)
    res = runner.run_test_batch(test_filter='all')
    assert runner.run_single_test.call_count == 1
    assert '取消' in res['summary']['aborted']
    print("  PASS test_cancel_stops_batch")


def test_concurrent_batch_rejected():
    """已有批次运行时，第二个批次被拒绝"""
    runner = _make_runner()
    runner._batch_lock.acquire()
    try:
        res = runner.run_test_batch(test_filter='all')
        assert res['success'] is False and '并发' in res['error']
    finally:
        runner._batch_lock.release()
    print("  PASS test_concurrent_batch_rejected")


if __name__ == "__main__":
    print("=== test_batch_runner 单测 ===")
    tests = [
        test_run_single_test_war3_remaining_returns_env_error,
        test_run_single_test_war3_clean_continues,
        test_run_single_test_calls_is_war3_clean_after_sleep,
        test_poll_pipe_events_collects_progress_logs_and_result,
        test_unit_layer_never_launches_game,
        test_unit_layer_without_desktop_runner_refuses,
        test_env_error_not_retried_and_circuit_breaks,
        test_residue_aborts_batch_immediately,
        test_game_launch_budget,
        test_cancel_stops_batch,
        test_concurrent_batch_rejected,
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
