#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TestEntryPreparer 单测

覆盖：prepare 方法（写 _target_test.lua / run_auto_test.lua / 注入插件产物 / 调 TestModeFlag）
全部使用临时目录 + mock，不依赖外部服务
"""

import sys
import os
import tempfile
import shutil
import logging
from pathlib import Path
from unittest.mock import Mock, MagicMock

# 确保能 import 同目录下的 test_entry_preparer
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_entry_preparer import TestEntryPreparer
from test_mode_flag import TestModeFlag


def _make_logger():
    """创建测试用 logger（静默）"""
    logger = logging.getLogger('test_entry_preparer_test')
    logger.setLevel(logging.DEBUG)
    if not logger.handlers:
        logger.addHandler(logging.NullHandler())
    return logger


def _make_test_dir(tmpdir):
    """创建测试目录（模拟 test_dir）"""
    test_dir = Path(tmpdir) / 'auto-test'
    test_dir.mkdir()
    return test_dir


def _make_mock_config(tmpdir):
    """创建 mock config"""
    config = Mock()
    config.project_root = Path(tmpdir)
    config.test_module_prefix = ''
    config.test_bootstrap_template = ''
    config.http_port = 8766

    def resolve_path(path):
        if not path or path == '.':
            return config.project_root
        return Path(path)

    config.resolve_path = resolve_path

    def get_test_dir_path(source_dir):
        # 模拟 w2l 项目根校验
        if not (source_dir / 'w3x2lni').exists():
            return None
        return source_dir / 'auto-test'

    config.get_test_dir_path = get_test_dir_path

    return config


def _make_mock_server_dir(tmpdir):
    """创建 mock server_dir（包含 lua_bootstrap.lua）"""
    server_dir = Path(tmpdir) / 'server'
    server_dir.mkdir()

    # 创建 lua_bootstrap.lua
    bootstrap_content = """
-- 通用引导模板
local target = require('@@W3T_TARGET_TEST_MODULE@@')
print('Loading test:', target.test_name)
"""
    (server_dir / 'lua_bootstrap.lua').write_text(bootstrap_content, encoding='utf-8')

    # 创建插件产物（空文件）
    (server_dir / 'inspect_handler.lua').write_text('-- inspect handler', encoding='utf-8')
    (server_dir / 'assertions.lua').write_text('-- assertions', encoding='utf-8')
    (server_dir / 'jass_mock.lua').write_text('-- jass mock', encoding='utf-8')

    return server_dir


def test_prepare_writes_target_and_run_auto():
    """prepare: 写 _target_test.lua 和 run_auto_test.lua"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # 创建 w2l 项目根
        project_root = tmpdir / 'project'
        project_root.mkdir()
        (project_root / 'w3x2lni').mkdir()

        config = _make_mock_config(tmpdir)
        server_dir = _make_mock_server_dir(tmpdir)
        flag = TestModeFlag(logger=_make_logger())
        preparer = TestEntryPreparer(flag, server_dir, config, logger=_make_logger())

        result = preparer.prepare('test_skill_a00d', 'test_skill_a00d.lua', str(project_root))

        assert result is True, "prepare 应返回 True"

        # 检查 _target_test.lua
        target_path = project_root / 'auto-test' / '_war3_tester' / '_target_test.lua'
        assert target_path.exists(), "_target_test.lua 应被创建"
        target_content = target_path.read_text(encoding='utf-8')
        assert 'test_skill_a00d' in target_content, "应包含 test_name"
        assert 'http_port=8766' in target_content, "应包含 http_port"

        # 检查 run_auto_test.lua
        run_auto_path = project_root / 'auto-test' / 'run_auto_test.lua'
        assert run_auto_path.exists(), "run_auto_test.lua 应被创建"
        run_auto_content = run_auto_path.read_text(encoding='utf-8')
        assert '_war3_tester._target_test' in run_auto_content, "应包含 require 路径"
        assert 'inspect_handler' in run_auto_content, "应包含 inspect_handler 注入"
        assert 'assertions' in run_auto_content, "应包含 assertions 注入"
        assert 'jass_mock' in run_auto_content, "应包含 jass_mock 注入"

    print("  PASS test_prepare_writes_target_and_run_auto")


def test_prepare_infers_test_file():
    """prepare: 未提供 test_file 时自动推断"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        project_root = tmpdir / 'project'
        project_root.mkdir()
        (project_root / 'w3x2lni').mkdir()

        config = _make_mock_config(tmpdir)
        server_dir = _make_mock_server_dir(tmpdir)
        flag = TestModeFlag(logger=_make_logger())
        preparer = TestEntryPreparer(flag, server_dir, config, logger=_make_logger())

        # 不传 test_file，应自动推断为 test_skill_a00d.lua
        result = preparer.prepare('skill_a00d', None, str(project_root))

        assert result is True, "prepare 应返回 True"

        target_path = project_root / 'auto-test' / '_war3_tester' / '_target_test.lua'
        target_content = target_path.read_text(encoding='utf-8')
        assert 'test_skill_a00d.lua' in target_content, "应推断出 test_file"

    print("  PASS test_prepare_infers_test_file")


def test_prepare_handles_test_prefix():
    """prepare: test_name 已含 test_ 前缀时不重复追加"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        project_root = tmpdir / 'project'
        project_root.mkdir()
        (project_root / 'w3x2lni').mkdir()

        config = _make_mock_config(tmpdir)
        server_dir = _make_mock_server_dir(tmpdir)
        flag = TestModeFlag(logger=_make_logger())
        preparer = TestEntryPreparer(flag, server_dir, config, logger=_make_logger())

        # test_name 已含 test_ 前缀
        result = preparer.prepare('test_xinfa_faction', None, str(project_root))

        assert result is True, "prepare 应返回 True"

        target_path = project_root / 'auto-test' / '_war3_tester' / '_target_test.lua'
        target_content = target_path.read_text(encoding='utf-8')
        # 不应出现 test_test_xinfa_faction
        assert 'test_test_xinfa_faction' not in target_content, "不应重复追加 test_ 前缀"
        assert 'test_xinfa_faction.lua' in target_content, "应正确使用 test_xinfa_faction.lua"

    print("  PASS test_prepare_handles_test_prefix")


def test_prepare_rejects_chinese_test_name():
    """prepare: test_name 含中文且未提供 test_file 时应抛异常"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        project_root = tmpdir / 'project'
        project_root.mkdir()
        (project_root / 'w3x2lni').mkdir()

        config = _make_mock_config(tmpdir)
        server_dir = _make_mock_server_dir(tmpdir)
        flag = TestModeFlag(logger=_make_logger())
        preparer = TestEntryPreparer(flag, server_dir, config, logger=_make_logger())

        try:
            preparer.prepare('测试技能', None, str(project_root))
            assert False, "应抛出 ValueError"
        except ValueError as e:
            assert '包含中文' in str(e), "异常信息应包含'包含中文'"

    print("  PASS test_prepare_rejects_chinese_test_name")


def test_prepare_calls_test_mode_flag_enable():
    """prepare: 调用 TestModeFlag.enable 删除 _test_off.lua"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        project_root = tmpdir / 'project'
        project_root.mkdir()
        (project_root / 'w3x2lni').mkdir()

        config = _make_mock_config(tmpdir)
        server_dir = _make_mock_server_dir(tmpdir)
        flag = TestModeFlag(logger=_make_logger())

        # 先创建 _test_off.lua
        test_dir = project_root / 'auto-test'
        test_dir.mkdir()
        wt_dir = test_dir / '_war3_tester'
        wt_dir.mkdir()
        (wt_dir / '_test_off.lua').write_text('return true')

        preparer = TestEntryPreparer(flag, server_dir, config, logger=_make_logger())
        preparer.prepare('test_skill', 'test_skill.lua', str(project_root))

        # _test_off.lua 应被删除
        assert not (wt_dir / '_test_off.lua').exists(), "_test_off.lua 应被 enable 删除"

    print("  PASS test_prepare_calls_test_mode_flag_enable")


def test_prepare_injects_assets():
    """prepare: 注入插件产物到 _war3_tester/"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        project_root = tmpdir / 'project'
        project_root.mkdir()
        (project_root / 'w3x2lni').mkdir()

        config = _make_mock_config(tmpdir)
        server_dir = _make_mock_server_dir(tmpdir)
        flag = TestModeFlag(logger=_make_logger())
        preparer = TestEntryPreparer(flag, server_dir, config, logger=_make_logger())

        preparer.prepare('test_skill', 'test_skill.lua', str(project_root))

        wt_dir = project_root / 'auto-test' / '_war3_tester'
        assert (wt_dir / 'inspect_handler.lua').exists(), "应注入 inspect_handler.lua"
        assert (wt_dir / 'assertions.lua').exists(), "应注入 assertions.lua"
        assert (wt_dir / 'jass_mock.lua').exists(), "应注入 jass_mock.lua"

    print("  PASS test_prepare_injects_assets")


def test_prepare_returns_false_when_not_w2l_root():
    """prepare: source_dir 非 w2l 项目根时返回 False"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # 不创建 w3x2lni 目录
        project_root = tmpdir / 'project'
        project_root.mkdir()

        config = _make_mock_config(tmpdir)
        server_dir = _make_mock_server_dir(tmpdir)
        flag = TestModeFlag(logger=_make_logger())
        preparer = TestEntryPreparer(flag, server_dir, config, logger=_make_logger())

        result = preparer.prepare('test_skill', 'test_skill.lua', str(project_root))

        assert result is False, "非 w2l 项目根时应返回 False"

    print("  PASS test_prepare_returns_false_when_not_w2l_root")


def test_prepare_returns_false_when_no_bootstrap():
    """prepare: 无引导模板时返回 False"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        project_root = tmpdir / 'project'
        project_root.mkdir()
        (project_root / 'w3x2lni').mkdir()

        config = _make_mock_config(tmpdir)

        # server_dir 不包含 lua_bootstrap.lua
        server_dir = tmpdir / 'server'
        server_dir.mkdir()

        flag = TestModeFlag(logger=_make_logger())
        preparer = TestEntryPreparer(flag, server_dir, config, logger=_make_logger())

        result = preparer.prepare('test_skill', 'test_skill.lua', str(project_root))

        assert result is False, "无引导模板时应返回 False"

    print("  PASS test_prepare_returns_false_when_no_bootstrap")


if __name__ == "__main__":
    print("=== TestEntryPreparer 单测 ===")
    tests = [
        test_prepare_writes_target_and_run_auto,
        test_prepare_infers_test_file,
        test_prepare_handles_test_prefix,
        test_prepare_rejects_chinese_test_name,
        test_prepare_calls_test_mode_flag_enable,
        test_prepare_injects_assets,
        test_prepare_returns_false_when_not_w2l_root,
        test_prepare_returns_false_when_no_bootstrap,
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
