#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ProjectScaffolder 单测

覆盖：get_project_info / generate_test_skeleton / scaffold_test
全部使用 MockConfig + 临时目录，不依赖真实 Config / mcp_server
"""

import sys
import os
import tempfile
import logging
from pathlib import Path
from unittest.mock import MagicMock

# 确保能 import 同目录下的 scaffolder
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scaffolder import ProjectScaffolder


# === MockConfig: 最小 mock，带被测用到的三个属性/方法 ===

# 默认 19 项 module_dirs（逐字 = scaffolder.py 注释的"原 18 项"+1，通用化默认值）
DEFAULT_MODULE_DIRS = {
    '技能', 'Buffs', '物品', '任务', '副本', '进攻波', 'AI', 'NPC', '单位',
    'core', 'model', 'data', 'entities', 'components', 'systems',
    '界面', 'states', 'logic', 'types',
}


class MockConfig:
    """最小 mock config，带 scaffolder 用到的三个属性/方法"""

    def __init__(self, project_root=None, test_dir_path=None):
        self.project_root = project_root
        self._test_dir_path = test_dir_path
        self.project_info_module_dirs = list(DEFAULT_MODULE_DIRS)

    def resolve_source_dir(self, source_dir):
        """逐字返回传入值（模拟 config 的归一化）"""
        return source_dir

    def get_test_dir_path(self, resolved_source_dir):
        """返回预设的 test_dir_path（None 模拟非 w2l 项目）"""
        return self._test_dir_path


def _make_logger():
    """创建测试用 logger（静默）"""
    logger = logging.getLogger('scaffolder_test')
    logger.setLevel(logging.DEBUG)
    if not logger.handlers:
        logger.addHandler(logging.NullHandler())
    return logger


# === get_project_info 测试 ===

def test_get_project_info_dir_not_exists():
    """get_project_info: 目录不存在 → 返回含 [WARN] 源码目录不存在"""
    cfg = MockConfig()
    scaffolder = ProjectScaffolder(cfg, logger=_make_logger())

    result = scaffolder.get_project_info('/nonexistent/path/xyz_abc_123')
    assert '[WARN] 源码目录不存在' in result, f"应含 [WARN] 源码目录不存在，实际: {result[:200]}"

    print("  PASS test_get_project_info_dir_not_exists")


def test_get_project_info_valid_dir():
    """get_project_info: 有效目录 → 返回含 项目结构分析 且 module 统计含 技能"""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        # 造 技能/ 子目录 + 1 个 lua 文件
        skill_dir = root / '技能'
        skill_dir.mkdir()
        (skill_dir / 'skill_a00d.lua').write_text('-- skill\n')
        # 造 systems/init.lua
        systems_dir = root / 'systems'
        systems_dir.mkdir()
        (systems_dir / 'init.lua').write_text('-- systems init\n')

        cfg = MockConfig()
        scaffolder = ProjectScaffolder(cfg, logger=_make_logger())

        result = scaffolder.get_project_info(str(root))
        assert '项目结构分析' in result, f"应含 '项目结构分析'，实际前 300 字: {result[:300]}"
        assert '技能' in result, f"module 统计应含 '技能'，实际前 500 字: {result[:500]}"

    print("  PASS test_get_project_info_valid_dir")


# === generate_test_skeleton 测试 ===

def test_generate_test_skeleton_unit_layer():
    """generate_test_skeleton: layer='unit' → 含 @layer unit"""
    cfg = MockConfig()
    scaffolder = ProjectScaffolder(cfg, logger=_make_logger())

    content = scaffolder.generate_test_skeleton('talent', 'unit', 'test_unit_talent')
    assert '@layer unit' in content, f"unit 层骨架应含 '@layer unit'，实际前 200 字: {content[:200]}"

    print("  PASS test_generate_test_skeleton_unit_layer")


def test_generate_test_skeleton_integration_layer():
    """generate_test_skeleton: layer='integration' → 含 http_post_result"""
    cfg = MockConfig()
    scaffolder = ProjectScaffolder(cfg, logger=_make_logger())

    content = scaffolder.generate_test_skeleton('talent', 'integration', 'test_integration_talent')
    assert 'http_post_result' in content, f"integration 层骨架应含 'http_post_result'，实际前 200 字: {content[:200]}"

    print("  PASS test_generate_test_skeleton_integration_layer")


# === scaffold_test 测试 ===

def test_scaffold_test_get_test_dir_path_returns_none():
    """scaffold_test: mock config.get_test_dir_path 返回 None → result['success']==False"""
    cfg = MockConfig(test_dir_path=None)
    scaffolder = ProjectScaffolder(cfg, logger=_make_logger())

    result = scaffolder.scaffold_test('talent', 'unit', source_dir='/some/source')
    assert result['success'] is False, f"get_test_dir_path=None 时 success 应为 False，实际: {result}"
    assert result['error'] is not None, "error 字段应非 None"

    print("  PASS test_scaffold_test_get_test_dir_path_returns_none")


def test_scaffold_test_normal():
    """scaffold_test: 正常 → 生成 .lua 文件 + success:True"""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir) / 'auto-test'
        # 不预先创建 test_dir，scaffold_test 会 mkdir
        cfg = MockConfig(test_dir_path=test_dir)
        scaffolder = ProjectScaffolder(cfg, logger=_make_logger())

        result = scaffolder.scaffold_test('talent', 'unit', source_dir=tmpdir)
        assert result['success'] is True, f"应 success=True，实际: {result}"
        assert result['file'] is not None, "file 字段应非 None"
        assert result['file'].endswith('.lua'), f"文件应以 .lua 结尾，实际: {result['file']}"
        assert Path(result['file']).exists(), f"文件应实际存在: {result['file']}"

    print("  PASS test_scaffold_test_normal")


if __name__ == "__main__":
    print("=== ProjectScaffolder 单测 ===")
    tests = [
        test_get_project_info_dir_not_exists,
        test_get_project_info_valid_dir,
        test_generate_test_skeleton_unit_layer,
        test_generate_test_skeleton_integration_layer,
        test_scaffold_test_get_test_dir_path_returns_none,
        test_scaffold_test_normal,
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
