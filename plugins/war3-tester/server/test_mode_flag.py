#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TestModeFlag - _test_off.lua 标志管理模块

职责：
- 管理 _war3_tester/_test_off.lua 的写/删/查
- 清理 legacy 残留（test_dir 根的 _test_off.lua / _target_test.lua）
- 覆盖现有 4 处 _test_off.lua 行为：
  1. _prepare_test_entry: 删 _war3_tester/_test_off.lua + legacy 清理
  2. toggle_test 开启: 删 + legacy 清理
  3. toggle_test 关闭: 写 + 清 _target_test.lua/run_auto_test.lua + legacy 清理
  4. run_game inject_inspect: 删 + legacy 清理
  5. test_batch_runner._write_test_off: 写（固定内容 return true）

零反向依赖：只依赖 Python 标准库，不引用 mcp_server / test_batch_runner / http_receiver / config
"""

import logging
from pathlib import Path
from typing import Optional


# 标志文件内容模板
# toggle_test 关闭时使用（带来源注释）
_TOGGLE_OFF_CONTENT = (
    '-- toggle_test 生成：本文件存在则 auto-test 模块不加载（手动游戏模式）\n'
    'return true\n'
)

# test_batch_runner 测试完成后使用（带来源注释）
_AFTER_TEST_OFF_CONTENT = (
    '-- _run_single_test 完成后自动生成：手动游戏时 auto-test 模块不加载（init.lua early-return）\n'
    'return true\n'
)


class TestModeFlag:
    """
    _test_off.lua 标志管理。

    标志文件路径：_war3_tester/_test_off.lua（M1 归拢后统一位置）
    - 存在时：auto-test 模块不加载（手动游戏模式，零干扰）
    - 不存在时：auto-test 模块正常加载（测试模式）

    构造参数：
        logger: 日志记录器（可选，默认创建）
    """

    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger(__name__)

    def _get_war3_tester_dir(self, test_dir):
        """
        返回插件产物隔离子目录（_war3_tester/），不存在则创建。

        从 mcp_server._get_war3_tester_dir 忠实搬运。
        """
        wt = test_dir / '_war3_tester'
        wt.mkdir(parents=True, exist_ok=True)
        return wt

    def _get_off_path(self, test_dir):
        """获取 _war3_tester/_test_off.lua 的完整路径"""
        wt_dir = self._get_war3_tester_dir(test_dir)
        return wt_dir / '_test_off.lua'

    def enable(self, test_dir):
        """
        开启测试模式：删除 _war3_tester/_test_off.lua + legacy 清理。

        覆盖 mcp_server 的 3 处删除行为：
        - _prepare_test_entry:666-677
        - toggle_test 开启:865-869
        - run_game inject_inspect:1732-1747

        Args:
            test_dir: 测试目录 Path

        Returns:
            bool: 是否成功（True=已删除或本来就不存在）
        """
        test_dir.mkdir(parents=True, exist_ok=True)
        off_path = self._get_off_path(test_dir)

        if off_path.exists():
            try:
                off_path.unlink()
                self.logger.info("[TestModeFlag] 已删除 _war3_tester/_test_off.lua（开启测试模式）")
            except (IOError, OSError) as e:
                self.logger.warning("[TestModeFlag] 删除 _test_off.lua 失败: %s", e)
                return False

        # 兼容旧版：清理 test_dir 根的残留 _test_off.lua（过渡期）
        self._cleanup_legacy(test_dir)

        return True

    def disable(self, test_dir):
        """
        关闭测试模式：写入 _war3_tester/_test_off.lua + 清测试残留 + legacy 清理。

        覆盖 toggle_test 关闭行为（mcp_server:870-880）。

        Args:
            test_dir: 测试目录 Path

        Returns:
            bool: 是否成功写入
        """
        test_dir.mkdir(parents=True, exist_ok=True)
        wt_dir = self._get_war3_tester_dir(test_dir)
        off_path = wt_dir / '_test_off.lua'
        target_path = wt_dir / '_target_test.lua'
        run_auto_path = test_dir / 'run_auto_test.lua'

        # 兼容旧版：清理 test_dir 根的残留
        self._cleanup_legacy(test_dir)

        try:
            off_path.write_text(_TOGGLE_OFF_CONTENT, encoding='utf-8')

            # 清测试残留
            for p in (target_path, run_auto_path):
                if p.exists():
                    try:
                        p.unlink()
                    except (IOError, OSError):
                        pass

            self.logger.info("[TestModeFlag] 已写入 _war3_tester/_test_off.lua（关闭测试模式）")
            return True
        except (IOError, OSError) as e:
            self.logger.warning("[TestModeFlag] 写入 _test_off.lua 失败: %s", e)
            return False

    def is_disabled(self, test_dir):
        """
        查询测试模式是否已关闭（_test_off.lua 是否存在）。

        Args:
            test_dir: 测试目录 Path

        Returns:
            bool: True=已关闭（标志存在），False=已开启（标志不存在）
        """
        off_path = self._get_off_path(test_dir)
        return off_path.exists()

    def write_after_test(self, test_dir):
        """
        测试完成后写 _test_off.lua，让手动游戏时 auto-test 模块不加载。

        覆盖 test_batch_runner._write_test_off（test_batch_runner.py:439-456）。
        内容与 toggle_test 不同（注释不同），但行为等价（return true）。

        Args:
            test_dir: 测试目录 Path

        Returns:
            bool: 是否成功写入
        """
        try:
            wt_dir = self._get_war3_tester_dir(test_dir)
            off_path = wt_dir / '_test_off.lua'
            off_path.write_text(_AFTER_TEST_OFF_CONTENT, encoding='utf-8')
            self.logger.info(
                "[TestModeFlag] 测试完成，已写 _war3_tester/_test_off.lua（手动游戏零干扰）"
            )
            return True
        except Exception as e:
            self.logger.warning("[TestModeFlag] 写 _test_off 失败: %s", e)
            return False

    def _cleanup_legacy(self, test_dir):
        """
        清理 legacy 残留：删除 test_dir 根的 _test_off.lua / _target_test.lua。

        覆盖 mcp_server 中的 legacy 清理逻辑：
        - _prepare_test_entry:672-677（只清 _test_off.lua）
        - toggle_test:857-863（清 _test_off.lua + _target_test.lua）
        - run_game:1741-1747（只清 _test_off.lua）

        统一为：清 _test_off.lua + _target_test.lua（取最大并集）。
        """
        for name in ('_test_off.lua', '_target_test.lua'):
            legacy = test_dir / name
            if legacy.exists():
                try:
                    legacy.unlink()
                    self.logger.debug("[TestModeFlag] 已清理 legacy 残留: %s", legacy)
                except (IOError, OSError):
                    pass
