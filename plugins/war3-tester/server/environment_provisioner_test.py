#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EnvironmentProvisioner 单测

覆盖：setup 方法的三种组件分支（socket/http/nopause）+ 返回结构校验
全部使用 MockConfig + MagicMock + 临时目录，不依赖真实 Config / mcp_server
"""

import sys
import os
import tempfile
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

# 确保能 import 同目录下的 environment_provisioner
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from environment_provisioner import EnvironmentProvisioner


# === MockConfig: 最小 mock，带被测用到的属性 ===

class MockConfig:
    """最小 mock config，带 environment_provisioner 用到的属性"""

    def __init__(self, project_root=None, war3_log_dir=None):
        self.project_root = project_root
        self.war3_log_dir = war3_log_dir


def _make_logger():
    """创建测试用 logger（静默）"""
    logger = logging.getLogger('environment_provisioner_test')
    logger.setLevel(logging.DEBUG)
    if not logger.handlers:
        logger.addHandler(logging.NullHandler())
    return logger


# === setup 测试 ===

def test_setup_socket_no_project_root():
    """setup: 无 source_dir 且 config.project_root=None + components=['socket'] → results 含 socket failed"""
    cfg = MockConfig(project_root=None)
    plugin_root = Path(tempfile.gettempdir()) / 'fake_plugin_root'
    provisioner = EnvironmentProvisioner(cfg, plugin_root, logger=_make_logger())

    arguments = {
        'source_dir': None,
        'components': ['socket'],
    }
    result = provisioner.setup(arguments)

    # 返回结构校验
    assert 'content' in result, f"返回应含 'content' 键: {result.keys()}"
    assert 'isError' in result, f"返回应含 'isError' 键: {result.keys()}"
    assert isinstance(result['content'], list), f"content 应为 list，实际: {type(result['content'])}"
    assert isinstance(result['isError'], bool), f"isError 应为 bool，实际: {type(result['isError'])}"

    # socket 应 failed
    text = result['content'][0]['text']
    assert 'socket' in text.lower(), f"结果文本应提及 socket: {text[:300]}"
    assert 'failed' in text.lower() or '失败' in text or '未指定' in text, \
        f"socket 应 failed: {text[:300]}"
    assert result['isError'] is True, "有 failed 组件时 isError 应为 True"

    print("  PASS test_setup_socket_no_project_root")


def test_setup_http_success():
    """setup: mock subprocess.run returncode=0 + components=['http'] → http success"""
    cfg = MockConfig()
    plugin_root = Path(tempfile.gettempdir()) / 'fake_plugin_root'
    provisioner = EnvironmentProvisioner(cfg, plugin_root, logger=_make_logger())

    # mock subprocess.run 返回 returncode=0
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stderr = ''

    with patch('environment_provisioner.subprocess.run', return_value=mock_proc) as mock_run:
        arguments = {
            'components': ['http'],
        }
        result = provisioner.setup(arguments)

        # 验证 subprocess.run 被调用
        assert mock_run.called, "subprocess.run 应被调用"

    # 返回结构校验
    assert 'content' in result, f"返回应含 'content' 键"
    assert 'isError' in result, f"返回应含 'isError' 键"
    assert isinstance(result['content'], list), "content 应为 list"
    assert isinstance(result['isError'], bool), "isError 应为 bool"

    # http 应 success
    text = result['content'][0]['text']
    assert 'http' in text.lower(), f"结果文本应提及 http: {text[:300]}"
    assert 'success' in text.lower() or '已安装' in text, \
        f"http 应 success: {text[:300]}"
    assert result['isError'] is False, "无 failed 组件时 isError 应为 False"

    print("  PASS test_setup_http_success")


def test_setup_nopause_skipped():
    """setup: config.war3_log_dir=None + components=['nopause'] → nopause skipped"""
    cfg = MockConfig(war3_log_dir=None)
    plugin_root = Path(tempfile.gettempdir()) / 'fake_plugin_root'
    provisioner = EnvironmentProvisioner(cfg, plugin_root, logger=_make_logger())

    arguments = {
        'war3_dir': None,
        'components': ['nopause'],
    }
    result = provisioner.setup(arguments)

    # 返回结构校验
    assert 'content' in result, f"返回应含 'content' 键"
    assert 'isError' in result, f"返回应含 'isError' 键"
    assert isinstance(result['content'], list), "content 应为 list"
    assert isinstance(result['isError'], bool), "isError 应为 bool"

    # nopause 应 skipped
    text = result['content'][0]['text']
    assert 'nopause' in text.lower(), f"结果文本应提及 nopause: {text[:300]}"
    assert 'skipped' in text.lower() or '跳过' in text, \
        f"nopause 应 skipped: {text[:300]}"
    # skipped 不算 failed，isError 应为 False
    assert result['isError'] is False, "仅 skipped 无 failed 时 isError 应为 False"

    print("  PASS test_setup_nopause_skipped")


def test_setup_return_structure():
    """setup: 返回结构始终含 content(list) + isError(bool) 键"""
    cfg = MockConfig()
    plugin_root = Path(tempfile.gettempdir()) / 'fake_plugin_root'
    provisioner = EnvironmentProvisioner(cfg, plugin_root, logger=_make_logger())

    # 空 components 也应有标准返回
    arguments = {
        'components': [],
    }
    result = provisioner.setup(arguments)

    assert 'content' in result, f"返回应含 'content' 键，实际 keys: {result.keys()}"
    assert 'isError' in result, f"返回应含 'isError' 键，实际 keys: {result.keys()}"
    assert isinstance(result['content'], list), \
        f"content 应为 list，实际: {type(result['content'])}"
    assert isinstance(result['isError'], bool), \
        f"isError 应为 bool，实际: {type(result['isError'])}"
    # content 至少有一个元素（type=text）
    assert len(result['content']) >= 1, "content 应至少有一个元素"
    assert result['content'][0]['type'] == 'text', "content[0] 应为 type=text"

    print("  PASS test_setup_return_structure")


if __name__ == "__main__":
    print("=== EnvironmentProvisioner 单测 ===")
    tests = [
        test_setup_socket_no_project_root,
        test_setup_http_success,
        test_setup_nopause_skipped,
        test_setup_return_structure,
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
