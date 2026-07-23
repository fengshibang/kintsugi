#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dispatch registrar 单测（候选④收尾）

覆盖：
① 单源一致性：_tool_registry.keys() == capabilities["tools"] 的 name 集合 == 精确 25 个工具名
② 未知 tool fallback：handle_tool_call('not_a_real_tool', {}) 返回 isError=True
③ ≥2 真实工具路由：stop_game / send_key 经 MagicMock executor 被正确分发调用

隔离策略：
mcp_server.py 模块级会实例化 config/executor/store/http_receiver，
测试用 unittest.mock.patch 在 import 前替换这些依赖，避免依赖真实 war3 环境。
"""

import sys
import os
import asyncio
from unittest.mock import MagicMock, patch

# 确保能 import 同目录下的 mcp_server
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── 模块级依赖 mock（必须在 import mcp_server 之前）────────────────────
# mcp_server.py 顶层会 from config/env_bridge/http_receiver/test_state_store/...
# 并实例化 config/executor/store/http_receiver。用 MagicMock 替换，避免真实环境。

_mock_config = MagicMock()
_mock_config.project_root = None
_mock_config.compile_source_dir = '.'
_mock_config.http_host = '127.0.0.1'
_mock_config.http_port = 0
_mock_config.resolve_path = lambda p: p

_mock_executor = MagicMock()
_mock_store = MagicMock()
_mock_http_receiver = MagicMock()

# 先 patch 这些模块/对象，再 import mcp_server
_patches = [
    patch('config.Config', return_value=_mock_config),
    patch('env_bridge.create_executor', return_value=_mock_executor),
    patch('test_state_store.TestStateStore', return_value=_mock_store),
    patch('http_receiver.HTTPReceiver', return_value=_mock_http_receiver),
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

# v0.19.0: mcp_server 模块级 config/executor/store/http_receiver 改为 None 占位（init_runtime 才构造）。
# 上面的 patch('config.Config') 只拦构造函数调用，对模块级全局赋值无效——
# 直接赋 mock 覆盖模块级全局，War3TesterMCP.__init__ 读到的就是 mock。
import mcp_server
mcp_server.config = _mock_config
mcp_server.executor = _mock_executor
mcp_server.store = _mock_store
mcp_server.http_receiver = _mock_http_receiver
from mcp_server import War3TesterMCP


# ── 精确 25 个工具名（禁止弱断言）────────────────────────────────────
EXPECTED_25_TOOLS = {
    'compile_map', 'compile_only', 'test_commit', 'run_test_batch',
    'discover_tests', 'launch_only', 'run_game', 'stop_game',
    'stop_http_server', 'cleanup_all', 'take_screenshot', 'analyze_screenshot',
    'send_key', 'toggle_test', 'get_project_info', 'inspect_game',
    'get_debug_output', 'run_unit_test', 'scaffold_test', 'tdd_red',
    'tdd_green', 'watch_unit_tests', 'stop_watch', 'get_watch_results',
    'setup_environment',
}


def _make_instance():
    """构造 War3TesterMCP 实例（依赖已 mock）"""
    return War3TesterMCP()


def test_single_source_consistency():
    """① _tool_registry.keys() == capabilities['tools'] name 集合 == 精确 25 个"""
    instance = _make_instance()

    registry_keys = set(instance._tool_registry.keys())
    capability_names = {t['name'] for t in instance.capabilities['tools']}

    assert registry_keys == EXPECTED_25_TOOLS, (
        f"_tool_registry.keys() 与期望 25 个工具不一致\n"
        f"  缺: {EXPECTED_25_TOOLS - registry_keys}\n"
        f"  多: {registry_keys - EXPECTED_25_TOOLS}"
    )
    assert capability_names == EXPECTED_25_TOOLS, (
        f"capabilities['tools'] name 集合与期望 25 个工具不一致\n"
        f"  缺: {EXPECTED_25_TOOLS - capability_names}\n"
        f"  多: {capability_names - EXPECTED_25_TOOLS}"
    )
    assert registry_keys == capability_names, (
        f"_tool_registry 与 capabilities['tools'] 不一致（双源漂移）\n"
        f"  registry 有但 capabilities 无: {registry_keys - capability_names}\n"
        f"  capabilities 有但 registry 无: {capability_names - registry_keys}"
    )
    assert len(EXPECTED_25_TOOLS) == 25, "期望集合本身应为 25 个（测试写错时捕获）"

    print("  PASS test_single_source_consistency")


def test_unknown_tool_fallback():
    """② handle_tool_call('not_a_real_tool', {}) 返回含 isError: True"""
    instance = _make_instance()

    result = asyncio.run(instance.handle_tool_call('not_a_real_tool', {}))

    assert isinstance(result, dict), f"返回值应为 dict，实际: {type(result)}"
    assert result.get('isError') is True, (
        f"未知工具应返回 isError=True，实际: {result}"
    )
    content = result.get('content', [])
    assert isinstance(content, list) and len(content) >= 1, (
        f"content 应为非空 list，实际: {content}"
    )
    text = content[0].get('text', '')
    assert 'not_a_real_tool' in text, (
        f"错误信息应包含工具名，实际: {text}"
    )

    print("  PASS test_unknown_tool_fallback")


def test_stop_game_routes_to_executor():
    """③ stop_game 路由：handle_tool_call('stop_game') 调用 executor.stop_game"""
    instance = _make_instance()
    instance.executor = MagicMock()
    instance.executor.stop_game.return_value = {'success': True, 'message': '已关闭'}

    result = asyncio.run(instance.handle_tool_call('stop_game', {}))

    instance.executor.stop_game.assert_called_once()
    assert isinstance(result, dict), "返回值应为 dict"
    # stop_game 成功时不应 isError
    assert result.get('isError') is not True, (
        f"stop_game 成功时不应 isError=True，实际: {result}"
    )

    print("  PASS test_stop_game_routes_to_executor")


def test_send_key_routes_to_executor():
    """③ send_key 路由：handle_tool_call('send_key', {'key':'enter'}) 调用 executor.send_key('enter')"""
    instance = _make_instance()
    instance.executor = MagicMock()
    instance.executor.send_key.return_value = {'success': True, 'message': 'ok'}

    result = asyncio.run(instance.handle_tool_call('send_key', {'key': 'enter'}))

    instance.executor.send_key.assert_called_once_with('enter')
    assert isinstance(result, dict), "返回值应为 dict"
    assert result.get('isError') is not True, (
        f"send_key 成功时不应 isError=True，实际: {result}"
    )

    print("  PASS test_send_key_routes_to_executor")


def test_registry_handler_is_callable():
    """每个 ToolSpec 的 handler 都应是可调用对象"""
    instance = _make_instance()

    for name, spec in instance._tool_registry.items():
        assert callable(spec.handler), (
            f"工具 {name!r} 的 handler 不可调用: {spec.handler!r}"
        )
        # schema 也应包含必要字段
        assert 'name' in spec.schema, f"工具 {name!r} schema 缺 name"
        assert spec.schema['name'] == name, (
            f"工具 {name!r} schema.name 与 registry key 不一致"
        )

    print("  PASS test_registry_handler_is_callable")


if __name__ == "__main__":
    print("=== dispatch registrar 单测（候选④收尾）===")
    tests = [
        test_single_source_consistency,
        test_unknown_tool_fallback,
        test_stop_game_routes_to_executor,
        test_send_key_routes_to_executor,
        test_registry_handler_is_callable,
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

    # 清理 patches
    for _p in _patches:
        try:
            _p.stop()
        except Exception:
            pass

    sys.exit(1 if failed else 0)
