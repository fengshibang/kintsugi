#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EnvironmentProvisioner 单测

覆盖：
- setup 方法的各组件分支（socket / http / nopause / agent_bridge / agent_lua / entry_hook）
- mode='check'（只读体检）与 mode='repair'（安装/修复）
- 返回结构校验
"""

import sys
import os
import tempfile
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from environment_provisioner import EnvironmentProvisioner, AGENT_LUA_FILES


class MockConfig:
    def __init__(self, project_root=None, war3_log_dir=None, test_module_prefix='script.src.auto-test.'):
        self.project_root = project_root
        self.war3_log_dir = war3_log_dir
        self.test_module_prefix = test_module_prefix


def _make_logger():
    logger = logging.getLogger('environment_provisioner_test')
    logger.setLevel(logging.DEBUG)
    if not logger.handlers:
        logger.addHandler(logging.NullHandler())
    return logger


def test_setup_socket_no_project_root():
    cfg = MockConfig(project_root=None)
    plugin_root = Path(tempfile.gettempdir()) / 'fake_plugin_root'
    provisioner = EnvironmentProvisioner(cfg, plugin_root, logger=_make_logger())

    arguments = {
        'source_dir': None,
        'components': ['socket'],
    }
    result = provisioner.setup(arguments)

    assert 'content' in result
    assert 'isError' in result
    text = result['content'][0]['text']
    assert 'socket' in text.lower()
    assert result['isError'] is True

    print("  PASS test_setup_socket_no_project_root")


def test_setup_http_success():
    cfg = MockConfig()
    plugin_root = Path(tempfile.gettempdir()) / 'fake_plugin_root'
    provisioner = EnvironmentProvisioner(cfg, plugin_root, logger=_make_logger())

    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stderr = ''

    with patch('environment_provisioner.subprocess.run', return_value=mock_proc) as mock_run:
        arguments = {
            'components': ['http'],
        }
        result = provisioner.setup(arguments)
        assert mock_run.called

    text = result['content'][0]['text']
    assert 'http' in text.lower()
    assert result['isError'] is False

    print("  PASS test_setup_http_success")


def test_setup_nopause_skipped():
    cfg = MockConfig(war3_log_dir=None)
    plugin_root = Path(tempfile.gettempdir()) / 'fake_plugin_root'
    provisioner = EnvironmentProvisioner(cfg, plugin_root, logger=_make_logger())

    arguments = {
        'war3_dir': None,
        'components': ['nopause'],
    }
    result = provisioner.setup(arguments)

    text = result['content'][0]['text']
    assert 'nopause' in text.lower()
    assert result['isError'] is False

    print("  PASS test_setup_nopause_skipped")


def test_setup_agent_bridge_success():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plugin_root = tmp / 'plugin'
        (plugin_root / 'bin').mkdir(parents=True)
        (plugin_root / 'bin' / 'agent_bridge.dll').write_bytes(b'MZ_FAKE_DLL')
        project_root = tmp / 'proj'
        project_root.mkdir()

        cfg = MockConfig(project_root=project_root)
        provisioner = EnvironmentProvisioner(cfg, plugin_root, logger=_make_logger())
        result = provisioner.setup({'components': ['agent_bridge']})

        assert result['isError'] is False
        assert (project_root / 'map' / 'agent_bridge.dll').exists()

    print("  PASS test_setup_agent_bridge_success")


def test_setup_agent_lua_and_entry_hook_repair_and_check():
    """测试 agent_lua 与 entry_hook 的 check(缺失报错) -> repair(自动修复) -> check(通过) 闭环"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plugin_root = tmp / 'plugin'
        for rel in AGENT_LUA_FILES:
            p = plugin_root / 'assets' / 'agent' / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("local b = require 'script.src.auto-test.agent.bridge'\n", encoding='utf-8')
        (plugin_root / 'server').mkdir(parents=True, exist_ok=True)
        (plugin_root / 'server' / 'assertions.lua').write_text('-- assertions', encoding='utf-8')
        (plugin_root / 'server' / 'jass_mock.lua').write_text('-- jass_mock', encoding='utf-8')

        project_root = tmp / 'proj'
        test_dir = project_root / 'map' / 'script' / 'src' / 'auto-test'
        test_dir.mkdir(parents=True)
        # 制造一个残留的 _test_off.lua 和缺少钩子的 init.lua
        wt_dir = test_dir / '_war3_tester'
        wt_dir.mkdir(parents=True)
        (wt_dir / '_test_off.lua').write_text('return true', encoding='utf-8')
        (test_dir / 'init.lua').write_text("print('hello init')\n", encoding='utf-8')

        cfg = MockConfig(project_root=project_root, test_module_prefix='custom.test.')
        provisioner = EnvironmentProvisioner(cfg, plugin_root, logger=_make_logger())

        # 1. 修复前 check 应报告失败
        chk1 = provisioner.setup({
            'mode': 'check',
            'components': ['agent_lua', 'entry_hook'],
        })
        assert chk1['isError'] is True, "修复前 check 应发现缺失并报错"

        # 2. 执行 repair 修复
        rep = provisioner.setup({
            'mode': 'repair',
            'components': ['agent_lua', 'entry_hook'],
        })
        assert rep['isError'] is False, f"repair 应成功: {rep['content'][0]['text']}"

        # 验证模块前缀替换与钩子注入
        deployed_init = (test_dir / 'agent' / 'init.lua').read_text(encoding='utf-8')
        assert 'custom.test.agent.bridge' in deployed_init, "应自动替换 test_module_prefix"
        assert not (wt_dir / '_test_off.lua').exists(), "repair 应清除残留 _test_off.lua"
        entry_text = (test_dir / 'init.lua').read_text(encoding='utf-8')
        assert 'custom.test.agent.init' in entry_text, "init.lua 应被注入 -test on 钩子"

        # 3. 修复后再次 check 应全绿通过
        chk2 = provisioner.setup({
            'mode': 'check',
            'components': ['agent_lua', 'entry_hook'],
        })
        assert chk2['isError'] is False, f"修复后 check 应通过: {chk2['content'][0]['text']}"

    print("  PASS test_setup_agent_lua_and_entry_hook_repair_and_check")


def test_setup_return_structure():
    cfg = MockConfig()
    plugin_root = Path(tempfile.gettempdir()) / 'fake_plugin_root'
    provisioner = EnvironmentProvisioner(cfg, plugin_root, logger=_make_logger())

    arguments = {
        'components': [],
    }
    result = provisioner.setup(arguments)

    assert 'content' in result
    assert 'isError' in result
    assert isinstance(result['content'], list)
    assert isinstance(result['isError'], bool)
    assert len(result['content']) >= 1
    assert result['content'][0]['type'] == 'text'

    print("  PASS test_setup_return_structure")


if __name__ == "__main__":
    print("=== EnvironmentProvisioner 单测 ===")
    tests = [
        test_setup_socket_no_project_root,
        test_setup_http_success,
        test_setup_nopause_skipped,
        test_setup_agent_bridge_success,
        test_setup_agent_lua_and_entry_hook_repair_and_check,
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
