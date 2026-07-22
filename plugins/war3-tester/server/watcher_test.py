#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FileWatcher 单测

覆盖：
1. 正常 start_watch → stop_watch 成功往返
2. mock desktop_runner.run_unit_test 抛异常后，get_results()['watching'] 真实为 False
   （验证修复了「线程死亡但 watching=True」的静默失效 bug）
3. 未启动时 stop_watch() 返回 success=False

全部使用临时目录 + NullHandler 静默 logger，不依赖外部服务
"""

import sys
import os
import tempfile
import time
import logging
from pathlib import Path
from unittest.mock import MagicMock

# 确保能 import 同目录下的 watcher
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from watcher import FileWatcher, WatcherState


def _make_logger():
    """创建测试用 logger（静默）"""
    logger = logging.getLogger('watcher_test')
    logger.setLevel(logging.DEBUG)
    if not logger.handlers:
        logger.addHandler(logging.NullHandler())
    return logger


def _make_watcher(tmpdir, desktop_runner=None):
    """创建 FileWatcher 实例，使用临时目录"""
    tmpdir = Path(tmpdir)

    # 模拟 config
    config = MagicMock()
    config.compile_source_dir = tmpdir
    config._resolve_path = lambda x: Path(x) if x else tmpdir
    config.get_test_dir_path = lambda x: tmpdir / 'auto-test'

    # 创建 auto-test 目录和测试文件
    test_dir = tmpdir / 'auto-test'
    test_dir.mkdir(exist_ok=True)
    test_file = test_dir / 'test_example.lua'
    test_file.write_text('-- test')

    # 模拟 desktop_runner
    if desktop_runner is None:
        desktop_runner = MagicMock()
        desktop_runner.run_unit_test = MagicMock(return_value={
            'success': True,
            'failure_type': None,
            'error': None,
            'details': 'ok'
        })

    watcher = FileWatcher(desktop_runner, config)
    watcher.logger = _make_logger()  # 静默 logger
    return watcher


def test_normal_start_stop_roundtrip():
    """正常 start_watch → stop_watch 成功往返"""
    with tempfile.TemporaryDirectory() as tmpdir:
        watcher = _make_watcher(tmpdir)

        # 启动
        start_result = watcher.start_watch('test_example', poll_interval=0.1, debounce_delay=0.05)
        assert start_result['success'] is True, f"start_watch 应成功: {start_result}"
        assert 'watch_id' in start_result, "start_result 应包含 watch_id"
        assert 'log_file' in start_result, "start_result 应包含 log_file"

        # 检查状态
        results = watcher.get_results()
        assert results['watching'] is True, "启动后 watching 应为 True"

        # 等待 initial_run 完成
        time.sleep(0.3)

        # 停止
        stop_result = watcher.stop_watch()
        assert stop_result['success'] is True, f"stop_watch 应成功: {stop_result}"
        assert 'total_runs' in stop_result, "stop_result 应包含 total_runs"
        assert 'log_file' in stop_result, "stop_result 应包含 log_file"

        # 检查状态
        results = watcher.get_results()
        assert results['watching'] is False, "停止后 watching 应为 False"

    print("  PASS test_normal_start_stop_roundtrip")


def test_watching_false_after_exception():
    """mock _run_test_and_record 抛 BaseException 后，get_results()['watching'] 真实为 False

    这是最关键的测试：验证修复了「线程死亡但 watching=True」的静默失效 bug。
    用 KeyboardInterrupt（BaseException）绕过 _run_test_and_record 的内部 except Exception，
    模拟原 bug 场景（initial_run 在 try 外抛异常直接杀死线程）。
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        watcher = _make_watcher(tmpdir)

        # 让 _run_test_and_record 抛 BaseException，模拟原 bug 的 initial_run 崩溃
        def raise_kbi(*args, **kwargs):
            raise KeyboardInterrupt("模拟 initial_run 崩溃")
        watcher._run_test_and_record = raise_kbi

        # 启动
        start_result = watcher.start_watch('test_example', poll_interval=0.1, debounce_delay=0.05)
        assert start_result['success'] is True, f"start_watch 应成功: {start_result}"

        # 等待线程因异常退出
        time.sleep(0.5)

        # 关键检查：线程已死，watching 必须为 False
        results = watcher.get_results()
        assert results['watching'] is False, \
            f"线程异常退出后 watching 必须为 False，实际为 {results['watching']}（静默失效 bug 未修复）"

        # 额外检查：状态机应已复位
        with watcher._state_lock:
            assert watcher._state == WatcherState.STOPPED, \
                f"状态应为 STOPPED，实际为 {watcher._state}"

        # stop_watch 应返回失败（因为已经不在 RUNNING 状态）
        stop_result = watcher.stop_watch()
        assert stop_result['success'] is False, \
            f"线程已死后调用 stop_watch 应返回 success=False，实际为 {stop_result}"

    print("  PASS test_watching_false_after_exception")


def test_stop_without_start():
    """未启动时 stop_watch() 返回 success=False"""
    with tempfile.TemporaryDirectory() as tmpdir:
        watcher = _make_watcher(tmpdir)

        # 未启动直接停止
        stop_result = watcher.stop_watch()
        assert stop_result['success'] is False, "未启动时 stop_watch 应返回 success=False"
        assert stop_result['total_runs'] == 0, "未启动时 total_runs 应为 0"
        assert '没有监控在运行' in stop_result['message'], "message 应包含提示信息"

    print("  PASS test_stop_without_start")


if __name__ == "__main__":
    print("=== FileWatcher 单测 ===")
    tests = [
        test_normal_start_stop_roundtrip,
        test_watching_false_after_exception,
        test_stop_without_start,
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
            import traceback
            traceback.print_exc()

    print(f"\n结果：{passed} 通过，{failed} 失败，共 {len(tests)} 条")
    sys.exit(1 if failed else 0)
