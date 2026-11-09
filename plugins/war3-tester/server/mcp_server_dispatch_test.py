#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dispatch registrar 单测

覆盖：
① 单源一致性：_tool_registry.keys() == capabilities["tools"] 的 name 集合 == 精确 34 个工具名
② 未知 tool fallback：handle_tool_call('not_a_real_tool', {}) 返回 isError=True
③ ≥2 真实工具路由：stop_game / send_key / inspect_game / exec_game / game_observe 经 MagicMock 被正确分发调用
"""

import sys
import os
import asyncio
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

_mock_config = MagicMock()
_mock_config.project_root = None
_mock_config.compile_source_dir = '.'
_mock_config.http_host = '127.0.0.1'
_mock_config.http_port = 0
_mock_config.resolve_path = lambda p: p

_mock_executor = MagicMock()
_mock_store = MagicMock()
_mock_http_receiver = MagicMock()
_mock_pipe_client = MagicMock()

_patches = [
    patch('config.Config', return_value=_mock_config),
    patch('env_bridge.create_executor', return_value=_mock_executor),
    patch('test_state_store.TestStateStore', return_value=_mock_store),
    patch('http_receiver.HTTPReceiver', return_value=_mock_http_receiver),
    patch('pipe_client.PipeClient', return_value=_mock_pipe_client),
    patch('test_batch_runner.TestBatchRunner', return_value=MagicMock()),
    patch('desktop_runner.DesktopRunner', return_value=MagicMock()),
    patch('watcher.FileWatcher', return_value=MagicMock()),
    patch('test_mode_flag.TestModeFlag', return_value=MagicMock()),
    patch('test_entry_preparer.TestEntryPreparer', return_value=MagicMock()),
    patch('diagnostics_collector.DiagnosticsCollector', return_value=MagicMock()),
    patch('logger.setup_logger', return_value=MagicMock()),
]

for _p in _patches:
    _p.start()

import mcp_server
from mcp_server import War3TesterMCP


# ── 精确 34 个工具名（26 传统工具 + 8 Named Pipe LLM Agent 工具）──────────────
EXPECTED_34_TOOLS = {
    'compile_map', 'compile_only', 'test_commit', 'run_test_batch',
    'discover_tests', 'launch_only', 'run_game', 'stop_game',
    'stop_http_server', 'cleanup_all', 'take_screenshot',
    'send_key', 'send_mouse_click', 'toggle_test', 'get_project_info', 'inspect_game',
    'get_debug_output', 'run_unit_test', 'scaffold_test', 'tdd_red',
    'tdd_green', 'watch_unit_tests', 'stop_watch', 'get_watch_results',
    'setup_environment', 'exec_game', 'save_adapter_hook',
    # Named Pipe LLM Agent 工具
    'game_status', 'game_set_mode', 'game_observe', 'game_act',
    'game_events', 'game_inspect', 'game_setup', 'game_report_bug',
}


def _make_instance():
    """构造 War3TesterMCP 实例（依赖已 mock）"""
    return War3TesterMCP()


def test_single_source_consistency():
    """① _tool_registry.keys() == capabilities['tools'] name 集合 == 精确 34 个"""
    instance = _make_instance()

    registry_keys = set(instance._tool_registry.keys())
    capability_names = {t['name'] for t in instance.capabilities['tools']}

    assert registry_keys == EXPECTED_34_TOOLS, (
        f"_tool_registry.keys() 与期望 34 个工具不一致\n"
        f"  缺: {EXPECTED_34_TOOLS - registry_keys}\n"
        f"  多: {registry_keys - EXPECTED_34_TOOLS}"
    )
    assert capability_names == EXPECTED_34_TOOLS, (
        f"capabilities['tools'] name 集合与期望 34 个工具不一致\n"
        f"  缺: {EXPECTED_34_TOOLS - capability_names}\n"
        f"  多: {capability_names - EXPECTED_34_TOOLS}"
    )
    assert registry_keys == capability_names
    assert len(EXPECTED_34_TOOLS) == 35

    print("  PASS test_single_source_consistency")


def test_unknown_tool_fallback():
    """② handle_tool_call('not_a_real_tool', {}) 返回含 isError: True"""
    instance = _make_instance()

    result = asyncio.run(instance.handle_tool_call('not_a_real_tool', {}))

    assert isinstance(result, dict)
    assert result.get('isError') is True
    content = result.get('content', [])
    assert isinstance(content, list) and len(content) >= 1
    text = content[0].get('text', '')
    assert 'not_a_real_tool' in text

    print("  PASS test_unknown_tool_fallback")


def test_stop_game_routes_to_executor():
    """③ stop_game 路由：handle_tool_call('stop_game') 调用 executor.stop_game"""
    instance = _make_instance()
    instance.executor = MagicMock()
    instance.executor.stop_game.return_value = {'success': True, 'message': '已关闭'}
    instance.pipe_client = MagicMock()

    result = asyncio.run(instance.handle_tool_call('stop_game', {}))

    instance.executor.stop_game.assert_called_once()
    instance.pipe_client.close.assert_called_once()
    assert isinstance(result, dict)
    assert result.get('isError') is not True

    print("  PASS test_stop_game_routes_to_executor")


def test_send_key_routes_to_executor():
    """③ send_key 路由：handle_tool_call('send_key', {'key':'enter'}) 调用 executor.send_key('enter')"""
    instance = _make_instance()
    instance.executor = MagicMock()
    instance.executor.send_key.return_value = {'success': True, 'message': 'ok'}

    result = asyncio.run(instance.handle_tool_call('send_key', {'key': 'enter'}))

    instance.executor.send_key.assert_called_once_with('enter')
    assert isinstance(result, dict)
    assert result.get('isError') is not True

    print("  PASS test_send_key_routes_to_executor")


def test_send_mouse_click_routes_to_executor():
    """send_mouse_click 路由：handle_tool_call('send_mouse_click', ...) 调用 executor.send_mouse_click(...) """
    instance = _make_instance()
    instance.executor = MagicMock()
    instance.executor.send_mouse_click.return_value = {'success': True, 'message': 'ok'}

    result = asyncio.run(instance.handle_tool_call('send_mouse_click', {'x': 100, 'y': 200, 'button': 'left', 'double_click': True}))

    instance.executor.send_mouse_click.assert_called_once_with(100, 200, 'left', True)
    assert isinstance(result, dict)
    assert result.get('isError') is not True

    print("  PASS test_send_mouse_click_routes_to_executor")


def test_registry_handler_is_callable():
    """每个 ToolSpec 的 handler 都应是可调用对象"""
    instance = _make_instance()

    for name, spec in instance._tool_registry.items():
        assert callable(spec.handler), f"工具 {name!r} 的 handler 不可调用: {spec.handler!r}"
        assert 'name' in spec.schema, f"工具 {name!r} schema 缺 name"
        assert spec.schema['name'] == name

    print("  PASS test_registry_handler_is_callable")


def test_inspect_and_exec_game_route_to_pipe_client():
    """inspect_game / exec_game 路由：通过 pipe_client.request('inspect', ...) 执行"""
    instance = _make_instance()
    instance.pipe_client = MagicMock()
    instance.pipe_client.request.return_value = {'ok': True, 'payload': {'result': 999}}

    res1 = asyncio.run(instance.handle_tool_call('inspect_game', {'expr': '1+2'}))
    instance.pipe_client.request.assert_called_with('inspect', {'expr': '1+2'}, timeout_ms=5000, pid=None)
    assert '999' in res1['content'][0]['text']

    res2 = asyncio.run(instance.handle_tool_call('exec_game', {'code': 'return 999', 'pid': 3316}))
    instance.pipe_client.request.assert_called_with('inspect', {'expr': 'return 999'}, timeout_ms=5000, pid=3316)
    assert '999' in res2['content'][0]['text']

    print("  PASS test_inspect_and_exec_game_route_to_pipe_client")


def test_game_observe_routes_to_pipe_client():
    """game_observe 路由：通过 pipe_client.request('observe', ...) 执行"""
    instance = _make_instance()
    instance.pipe_client = MagicMock()
    instance.pipe_client.request.return_value = {'ok': True, 'payload': {'frame': 1234, 'mode': 'free'}}

    res = asyncio.run(instance.handle_tool_call('game_observe', {'detail': 'brief', 'radius': 800}))
    instance.pipe_client.request.assert_called_once_with(
        'observe', {'detail': 'brief', 'radius': 800}, timeout_ms=5000, pid=None
    )
    assert '1234' in res['content'][0]['text']

    print("  PASS test_game_observe_routes_to_pipe_client")


if __name__ == "__main__":
    print("=== dispatch registrar 单测 ===")
    tests = [
        test_single_source_consistency,
        test_unknown_tool_fallback,
        test_stop_game_routes_to_executor,
        test_send_key_routes_to_executor,
        test_send_mouse_click_routes_to_executor,
        test_registry_handler_is_callable,
        test_inspect_and_exec_game_route_to_pipe_client,
        test_game_observe_routes_to_pipe_client,
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

    for _p in _patches:
        try:
            _p.stop()
        except Exception:
            pass

    sys.exit(1 if failed else 0)
