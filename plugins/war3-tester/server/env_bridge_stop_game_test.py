#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
stop_game 单测

覆盖：
- LocalExecutor.stop_game Windows 分支：无残留 / 有残留 / 异常
- LocalExecutor.stop_game Linux 分支：pkill 路径
- WinProxyExecutor.stop_game：行为不变（无残留 / 有残留 / proxy 不可用）
- 共享辅助函数 _check_war3_remaining

全部使用 MagicMock 隔离，不依赖真实 war3 进程
"""

import sys
import os
from unittest.mock import MagicMock

# 确保能 import 同目录下的 env_bridge
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from env_bridge import LocalExecutor, WinProxyExecutor, _check_war3_remaining


def _make_local_executor(is_windows=True):
    """构造 LocalExecutor 实例（绕过 __init__，避免依赖真实 Config）"""
    exe = LocalExecutor.__new__(LocalExecutor)
    exe.config = MagicMock()
    exe.config.is_windows = is_windows
    exe.logger = MagicMock()
    return exe


def _make_winproxy_executor():
    """构造 WinProxyExecutor 实例（绕过 __init__ 的端口检测）"""
    exe = WinProxyExecutor.__new__(WinProxyExecutor)
    exe.config = MagicMock()
    exe.config.is_windows = True
    exe.logger = MagicMock()
    exe.host = '127.0.0.1'
    exe.port = 8767
    exe.timeout = 300
    return exe


# ---------- LocalExecutor tests ----------

def test_local_stop_game_no_remaining():
    """Local Windows: 无残留 → success:True"""
    exe = _make_local_executor(is_windows=True)

    # execute 返回顺序：第一次 Stop-Process，第二次 tasklist
    exe.execute = MagicMock(side_effect=[
        {'success': True, 'stdout': 'Done'},
        {'success': True, 'stdout': '"Image Name","PID","Memory"\n"System",4,1024\n'},
    ])

    result = exe.stop_game()
    assert result['success'] is True, f"期望 success:True，得到 {result}"
    assert 'remaining' not in result or not result.get('remaining'), \
        f"不应有 remaining：{result}"
    print("  PASS test_local_stop_game_no_remaining")


def test_local_stop_game_with_remaining():
    """Local Windows: 有残留 → success:False + remaining 非空"""
    exe = _make_local_executor(is_windows=True)

    tasklist_csv = (
        '"Image Name","PID","Memory"\n'
        '"System",4,1024\n'
        '"war3.exe",1234,50000\n'
        '"KKWE.exe",5678,30000\n'
    )
    exe.execute = MagicMock(side_effect=[
        {'success': True, 'stdout': 'Done'},
        {'success': True, 'stdout': tasklist_csv},
    ])

    result = exe.stop_game()
    assert result['success'] is False, f"期望 success:False，得到 {result}"
    assert 'remaining' in result and len(result['remaining']) > 0, \
        f"应有 remaining：{result}"
    assert any('war3.exe' in r.lower() for r in result['remaining']), \
        f"remaining 应包含 war3.exe：{result['remaining']}"
    assert any('kkwe.exe' in r.lower() for r in result['remaining']), \
        f"remaining 应包含 KKWE.exe：{result['remaining']}"
    print("  PASS test_local_stop_game_with_remaining")


def test_local_stop_game_exception():
    """Local: 杀进程异常 → success:False"""
    exe = _make_local_executor(is_windows=True)
    exe.execute = MagicMock(side_effect=RuntimeError("powershell 崩了"))

    result = exe.stop_game()
    assert result['success'] is False, f"期望 success:False，得到 {result}"
    assert 'error' in result, f"应有 error 字段：{result}"
    assert 'powershell 崩了' in result['error']
    print("  PASS test_local_stop_game_exception")


def test_local_stop_game_linux_branch():
    """Local Linux/Mac 分支：pkill 后直接 success:True（不强求 ps 验证）"""
    exe = _make_local_executor(is_windows=False)
    exe.execute = MagicMock(return_value={'success': True})

    result = exe.stop_game()
    assert result['success'] is True, f"期望 success:True，得到 {result}"
    # 验证调用了 pkill
    exe.execute.assert_called_once()
    call_args = exe.execute.call_args
    assert call_args[0][0] == 'pkill', f"应调用 pkill，实际调用 {call_args[0][0]}"
    print("  PASS test_local_stop_game_linux_branch")


def test_local_stop_game_calls_tasklist_after_stop():
    """Local Windows: 杀完后必须调用 tasklist 验证"""
    exe = _make_local_executor(is_windows=True)
    exe.execute = MagicMock(side_effect=[
        {'success': True, 'stdout': 'Done'},
        {'success': True, 'stdout': '"Image Name"\n"System"\n'},
    ])

    exe.stop_game()
    assert exe.execute.call_count == 2, \
        f"应调用 execute 两次（Stop-Process + tasklist），实际 {exe.execute.call_count} 次"
    # 第二次调用必须是 tasklist.exe
    second_call = exe.execute.call_args_list[1]
    assert second_call[0][0] == 'tasklist.exe', \
        f"第二次调用应为 tasklist.exe，实际 {second_call[0][0]}"
    print("  PASS test_local_stop_game_calls_tasklist_after_stop")


# ---------- WinProxyExecutor tests ----------

def test_winproxy_stop_game_no_remaining():
    """WinProxy: 无残留 → success:True（行为不变）"""
    exe = _make_winproxy_executor()

    exe.require_proxy = MagicMock(return_value={'success': True})
    exe.execute = MagicMock(side_effect=[
        {'success': True, 'stdout': 'Done'},
        {'success': True, 'stdout': '"Image Name","PID"\n"System",4\n'},
    ])

    result = exe.stop_game()
    assert result['success'] is True, f"期望 success:True，得到 {result}"
    assert result.get('message') == '游戏进程已全部清除', \
        f"message 不符：{result.get('message')}"
    assert 'remaining' not in result, f"不应有 remaining：{result}"
    print("  PASS test_winproxy_stop_game_no_remaining")


def test_winproxy_stop_game_with_remaining():
    """WinProxy: 有残留 → success:False + remaining（行为不变）"""
    exe = _make_winproxy_executor()

    exe.require_proxy = MagicMock(return_value={'success': True})
    tasklist_csv = (
        '"Image Name","PID"\n'
        '"war3.exe",1234\n'
        '"War3Loader.exe",5678\n'
    )
    exe.execute = MagicMock(side_effect=[
        {'success': True, 'stdout': 'Done'},
        {'success': True, 'stdout': tasklist_csv},
    ])

    result = exe.stop_game()
    assert result['success'] is False, f"期望 success:False，得到 {result}"
    assert 'remaining' in result and len(result['remaining']) == 2, \
        f"应有 2 项 remaining：{result}"
    assert 'message' in result and '进程仍未清除' in result['message'], \
        f"message 应包含'进程仍未清除'：{result.get('message')}"
    print("  PASS test_winproxy_stop_game_with_remaining")


def test_winproxy_stop_game_proxy_unavailable():
    """WinProxy: proxy 不可用 → success:False + error"""
    exe = _make_winproxy_executor()
    exe.require_proxy = MagicMock(return_value={'success': False, 'error': '连接失败'})

    result = exe.stop_game()
    assert result['success'] is False, f"期望 success:False，得到 {result}"
    assert 'error' in result, f"应有 error 字段：{result}"
    print("  PASS test_winproxy_stop_game_proxy_unavailable")


# ---------- 共享辅助函数测试 ----------

def test_check_war3_remaining_empty():
    """_check_war3_remaining: 空输入 → success:True"""
    result = _check_war3_remaining('')
    assert result['success'] is True
    assert result.get('message') == '游戏进程已全部清除'
    print("  PASS test_check_war3_remaining_empty")


def test_check_war3_remaining_detects_all_keywords():
    """_check_war3_remaining: 6 个关键词都能识别"""
    csv = (
        '"war3.exe",1\n'
        '"War3Loader.exe",2\n'
        '"KKWE.exe",3\n'
        '"YDWE.exe",4\n'
        '"Frozen Throne",5\n'
        '"Warcraft III",6\n'
    )
    result = _check_war3_remaining(csv)
    assert result['success'] is False
    assert len(result['remaining']) == 6, \
        f"应识别 6 个残留进程，实际 {len(result['remaining'])}：{result['remaining']}"
    print("  PASS test_check_war3_remaining_detects_all_keywords")


def test_check_war3_remaining_case_insensitive():
    """_check_war3_remaining: 大小写不敏感"""
    csv = '"WAR3.EXE",1\n"kkwe.exe",2\n'
    result = _check_war3_remaining(csv)
    assert result['success'] is False
    assert len(result['remaining']) == 2
    print("  PASS test_check_war3_remaining_case_insensitive")


if __name__ == "__main__":
    print("=== stop_game 单测 ===")
    tests = [
        test_local_stop_game_no_remaining,
        test_local_stop_game_with_remaining,
        test_local_stop_game_exception,
        test_local_stop_game_linux_branch,
        test_local_stop_game_calls_tasklist_after_stop,
        test_winproxy_stop_game_no_remaining,
        test_winproxy_stop_game_with_remaining,
        test_winproxy_stop_game_proxy_unavailable,
        test_check_war3_remaining_empty,
        test_check_war3_remaining_detects_all_keywords,
        test_check_war3_remaining_case_insensitive,
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
