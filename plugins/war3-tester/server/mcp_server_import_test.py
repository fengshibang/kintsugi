#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mcp_server import 副作用测试

v0.19.0: 验证 import mcp_server 不触发 Config/create_executor/TestStateStore/HTTPReceiver 构造，
消除模块级实例化副作用。
"""

import sys
import os

# 确保能 import 同目录下的模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_import_no_side_effects():
    """import mcp_server 不触发四个构造函数（Config/create_executor/TestStateStore/HTTPReceiver）"""
    import importlib
    from unittest.mock import patch

    # 移除 mcp_server 缓存（如果已 import）
    if 'mcp_server' in sys.modules:
        del sys.modules['mcp_server']

    # 先 import 依赖模块（它们的构造函数会被 patch）
    import config
    import env_bridge
    import test_state_store
    import http_receiver

    # patch 四个构造函数为 MagicMock
    with patch.object(config, 'Config') as mock_config, \
         patch.object(env_bridge, 'create_executor') as mock_executor, \
         patch.object(test_state_store, 'TestStateStore') as mock_store, \
         patch.object(http_receiver, 'HTTPReceiver') as mock_http:

        # import mcp_server（触发模块级代码）
        import mcp_server

        # 断言四个构造函数都未被调用
        assert not mock_config.called, "Config() 不应在 import 时被调用"
        assert not mock_executor.called, "create_executor() 不应在 import 时被调用"
        assert not mock_store.called, "TestStateStore() 不应在 import 时被调用"
        assert not mock_http.called, "HTTPReceiver() 不应在 import 时被调用"

    print("  PASS test_import_no_side_effects")


def test_init_runtime_initializes_globals():
    """init_runtime() 调用后四个全局有值（非 None）"""
    import mcp_server

    # 调用 init_runtime（实际构造全局对象）
    mcp_server.init_runtime()

    # 断言四个全局有值
    assert mcp_server.config is not None, "init_runtime() 后 config 应有值"
    assert mcp_server.executor is not None, "init_runtime() 后 executor 应有值"
    assert mcp_server.store is not None, "init_runtime() 后 store 应有值"
    assert mcp_server.http_receiver is not None, "init_runtime() 后 http_receiver 应有值"

    print("  PASS test_init_runtime_initializes_globals")


if __name__ == "__main__":
    print("=== mcp_server import 副作用测试 ===")
    tests = [
        test_import_no_side_effects,
        test_init_runtime_initializes_globals,
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
