#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DiagnosticsCollector 单测

覆盖：get_debug_output（store + 日志文件 mock）
（v0.20: analyze_screenshot/VLM 测试已随功能移除——判读交由环境内视觉 MCP）
全部使用临时目录 + mock，不启动游戏、不依赖网络
"""

import sys
import os
import tempfile
import json
import logging
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# 确保能 import 同目录下的 diagnostics_collector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from diagnostics_collector import DiagnosticsCollector


def _make_logger():
    """创建测试用 logger（静默）"""
    logger = logging.getLogger('diagnostics_collector_test')
    logger.setLevel(logging.DEBUG)
    if not logger.handlers:
        logger.addHandler(logging.NullHandler())
    return logger


def _make_mock_store():
    """创建 mock store"""
    store = Mock()
    store.recent = Mock(return_value=[])
    return store


def _make_mock_config(tmpdir):
    """创建 mock config"""
    config = Mock()
    config.war3_log_dir = Path(tmpdir) / 'logs'
    config.war3_log_dir.mkdir(exist_ok=True)

    def get_war3_log_file_path(player_id=1, date=None):
        log_file = config.war3_log_dir / f'war3_player{player_id}.log'
        return log_file

    config.get_war3_log_file_path = get_war3_log_file_path
    return config



def test_get_debug_output_includes_war3_log():
    """get_debug_output: 包含 War3 日志内容"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        store = _make_mock_store()
        config = _make_mock_config(tmpdir)

        # 创建日志文件
        log_file = config.war3_log_dir / 'war3_player1.log'
        log_file.write_text(
            'Normal line\n'
            'Error: something failed\n'
            'Warning: deprecated API\n'
            'Another normal line\n',
            encoding='utf-8'
        )

        collector = DiagnosticsCollector(store, config, logger=_make_logger())
        result = collector.get_debug_output(limit=10, level='all')

        assert 'War3 游戏日志' in result, "应包含日志标题"
        assert 'war3_player1.log' in result, "应包含日志文件路径"
        assert 'Error: something failed' in result, "应包含错误行"
        assert 'Warning: deprecated API' in result, "应包含警告行"

    print("  PASS test_get_debug_output_includes_war3_log")


def test_get_debug_output_filters_by_level():
    """get_debug_output: 按 level 过滤"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        store = _make_mock_store()
        config = _make_mock_config(tmpdir)

        log_file = config.war3_log_dir / 'war3_player1.log'
        log_file.write_text(
            'Normal line\n'
            'Error: something failed\n'
            'Warning: deprecated API\n',
            encoding='utf-8'
        )

        collector = DiagnosticsCollector(store, config, logger=_make_logger())

        # 只过滤 error
        result = collector.get_debug_output(limit=10, level='error')
        assert 'Error: something failed' in result, "应包含错误行"
        assert 'Warning: deprecated API' not in result, "不应包含警告行"

        # 只过滤 warning
        result = collector.get_debug_output(limit=10, level='warning')
        assert 'Warning: deprecated API' in result, "应包含警告行"
        assert 'Error: something failed' not in result, "不应包含错误行"

    print("  PASS test_get_debug_output_filters_by_level")


def test_get_debug_output_includes_store_recent():
    """get_debug_output: 包含 store.recent 的运行时错误"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        store = _make_mock_store()
        store.recent.return_value = [
            {
                '_source': 'game_error',
                'test_name': 'test_skill',
                'message': 'Assertion failed',
                'traceback': 'stack trace here',
                'timestamp': '2026-07-23 10:00:00'
            },
            {
                '_source': 'log',
                'test_name': 'test_skill',
                'level': 'info',
                'category': 'system',
                'message': 'Test started',
                'timestamp': '2026-07-23 10:00:01'
            }
        ]

        config = _make_mock_config(tmpdir)
        collector = DiagnosticsCollector(store, config, logger=_make_logger())

        result = collector.get_debug_output(limit=10, level='all')

        assert 'HTTP 缓存的运行时错误与分级日志' in result, "应包含 HTTP 缓存标题"
        assert 'Assertion failed' in result, "应包含运行时错误"
        assert 'Test started' in result, "应包含分级日志"
        assert 'test_skill' in result, "应包含 test_name"

    print("  PASS test_get_debug_output_includes_store_recent")


def test_get_debug_output_handles_missing_log():
    """get_debug_output: 日志文件不存在时 graceful"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        store = _make_mock_store()
        config = _make_mock_config(tmpdir)

        # 不创建日志文件
        collector = DiagnosticsCollector(store, config, logger=_make_logger())
        result = collector.get_debug_output(limit=10, level='all')

        assert '游戏日志文件不存在' in result, "应提示日志文件不存在"

    print("  PASS test_get_debug_output_handles_missing_log")


def test_get_debug_output_handles_empty_store():
    """get_debug_output: store 无数据时 graceful"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        store = _make_mock_store()
        store.recent.return_value = []

        config = _make_mock_config(tmpdir)
        collector = DiagnosticsCollector(store, config, logger=_make_logger())

        result = collector.get_debug_output(limit=10, level='all')

        assert '无缓存错误/日志' in result, "应提示无缓存数据"

    print("  PASS test_get_debug_output_handles_empty_store")


def test_get_debug_output_respects_limit():
    """get_debug_output: 遵守 limit 参数"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        store = _make_mock_store()
        store.recent.return_value = [
            {
                '_source': 'game_error',
                'test_name': f'test_{i}',
                'message': f'Error {i}',
                'timestamp': f'2026-07-23 10:00:{i:02d}'
            }
            for i in range(20)
        ]

        config = _make_mock_config(tmpdir)
        collector = DiagnosticsCollector(store, config, logger=_make_logger())

        result = collector.get_debug_output(limit=5, level='all')

        # 应只包含最近 5 条
        assert 'test_19' in result, "应包含最新条目"
        assert 'test_15' in result, "应包含第 15 条"
        # test_0 到 test_14 不应出现（被 limit 截断）

    print("  PASS test_get_debug_output_respects_limit")


if __name__ == "__main__":
    print("=== DiagnosticsCollector 单测 ===")
    tests = [
        test_get_debug_output_includes_war3_log,
        test_get_debug_output_filters_by_level,
        test_get_debug_output_includes_store_recent,
        test_get_debug_output_handles_missing_log,
        test_get_debug_output_handles_empty_store,
        test_get_debug_output_respects_limit,
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
