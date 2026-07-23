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


def test_init_initializes_instance_attrs():
    """War3TesterMCP.__init__ 构造后四实例属性有值(非 None)

    v0.19.5(候选④): init_runtime/模块级全局废弃,四对象改 __init__ 构造存 self。
    """
    from unittest.mock import patch, MagicMock
    import mcp_server

    with patch.object(mcp_server, 'Config', return_value=MagicMock(http_host='127.0.0.1', http_port=0, project_root=None)) as mock_config, \
         patch.object(mcp_server, 'create_executor', return_value=MagicMock()) as mock_executor, \
         patch.object(mcp_server, 'TestStateStore', return_value=MagicMock()) as mock_store, \
         patch.object(mcp_server, 'HTTPReceiver', return_value=MagicMock()) as mock_http:
        server = mcp_server.War3TesterMCP()

    # 四构造函数被调用(__init__ 构造四全局)
    assert mock_config.called, "Config() 应在 __init__ 被调用"
    assert mock_executor.called, "create_executor() 应在 __init__ 被调用"
    assert mock_store.called, "TestStateStore() 应在 __init__ 被调用"
    assert mock_http.called, "HTTPReceiver() 应在 __init__ 被调用"
    # 四实例属性有值
    assert server.config is not None, "__init__ 后 self.config 应有值"
    assert server.executor is not None, "__init__ 后 self.executor 应有值"
    assert server.store is not None, "__init__ 后 self.store 应有值"
    assert server.http_receiver is not None, "__init__ 后 self.http_receiver 应有值"

    print("  PASS test_init_initializes_instance_attrs")


if __name__ == "__main__":
    print("=== mcp_server import 副作用测试 ===")
    tests = [
        test_import_no_side_effects,
        test_init_initializes_instance_attrs,
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
