#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TestStateStore 单测

纯 Python 单测，不用 pytest，直接 def test_xxx + assert + __main__ 跑全部。
覆盖：并发 / merge_into / 环形 / clear_test / clear_all / recent / snapshot 隔离
"""

import sys
import os
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_state_store import TestStateStore


def test_concurrent_record_and_snapshot():
    """并发：多线程 record + 主线程 snapshot，验证无异常、无读撕裂"""
    store = TestStateStore()
    errors = []
    barrier = threading.Barrier(3)

    def writer_progress():
        try:
            barrier.wait(timeout=5)
            for i in range(500):
                store.record_progress("test_a", {"step": f"p{i}", "phase": "done"})
        except Exception as e:
            errors.append(("writer_progress", e))

    def writer_error():
        try:
            barrier.wait(timeout=5)
            for i in range(500):
                store.record_error("test_a", {"error": f"err{i}", "test_name": "test_a"})
        except Exception as e:
            errors.append(("writer_error", e))

    t1 = threading.Thread(target=writer_progress)
    t2 = threading.Thread(target=writer_error)
    t1.start()
    t2.start()

    barrier.wait(timeout=5)
    snapshot_count = 0
    for _ in range(100):
        try:
            snap = store.snapshot("test_a")
            assert isinstance(snap["progress"], list)
            assert isinstance(snap["logs"], list)
            assert isinstance(snap["game_errors"], list)
            assert len(snap["progress"]) <= 500
            assert len(snap["game_errors"]) <= 500
            snapshot_count += 1
        except Exception as e:
            errors.append(("snapshot", e))
            break
        time.sleep(0.001)

    t1.join(timeout=10)
    t2.join(timeout=10)

    assert not errors, f"并发测试出错：{errors}"
    assert snapshot_count == 100

    final = store.snapshot("test_a")
    assert len(final["progress"]) == 500
    assert len(final["game_errors"]) == 500
    print("  PASS test_concurrent_record_and_snapshot")


def test_merge_into():
    """merge_into：缓冲合进 data，原 data 字段保留，缓冲不清"""
    store = TestStateStore()

    store.record_progress("test_x", {"step": "s1"})
    store.record_progress("test_x", {"step": "s2"})
    store.record_log("test_x", {"level": "info", "message": "hello"})
    store.record_error("test_x", {"error": "err1", "test_name": "test_x"})

    data = {
        "test_name": "test_x",
        "success": True,
        "progress": [{"step": "s0"}],
        "other_field": "keep_me",
    }

    result = store.merge_into("test_x", data)

    assert result is data
    assert result["success"] is True
    assert result["other_field"] == "keep_me"
    assert result["test_name"] == "test_x"

    assert len(result["progress"]) == 3
    assert result["progress"][0]["step"] == "s0"
    assert result["progress"][1]["step"] == "s1"
    assert result["progress"][2]["step"] == "s2"

    assert len(result["logs"]) == 1
    assert result["logs"][0]["message"] == "hello"

    assert len(result["game_errors"]) == 1
    assert result["game_errors"][0]["error"] == "err1"

    snap = store.snapshot("test_x")
    assert len(snap["progress"]) == 2
    assert len(snap["logs"]) == 1

    print("  PASS test_merge_into")


def test_merge_into_no_overwrite_game_errors():
    """merge_into：data 已有 game_errors 时不覆盖"""
    store = TestStateStore()
    store.record_error("test_y", {"error": "buf_err", "test_name": "test_y"})

    data = {"game_errors": [{"error": "existing_err"}]}
    result = store.merge_into("test_y", data)

    assert len(result["game_errors"]) == 1
    assert result["game_errors"][0]["error"] == "existing_err"

    print("  PASS test_merge_into_no_overwrite_game_errors")


def test_merge_into_empty_data():
    """merge_into：data 无 progress/logs 时也能正确设置"""
    store = TestStateStore()
    store.record_progress("test_z", {"step": "s1"})
    store.record_log("test_z", {"level": "info", "message": "m1"})

    data = {"test_name": "test_z", "success": False}
    result = store.merge_into("test_z", data)

    assert len(result["progress"]) == 1
    assert result["progress"][0]["step"] == "s1"
    assert len(result["logs"]) == 1
    assert result["logs"][0]["message"] == "m1"

    print("  PASS test_merge_into_empty_data")


def test_game_errors_ring_buffer():
    """game_errors 环形：>1000 次后 len==1000 且保留最新"""
    store = TestStateStore()

    for i in range(1200):
        store.record_error("test_ring", {"error": f"err_{i}", "test_name": "test_ring"})

    with store._lock:
        assert len(store._game_errors) == 1000
        assert store._game_errors[-1]["error"] == "err_1199"
        assert store._game_errors[0]["error"] == "err_200"

    print("  PASS test_game_errors_ring_buffer")


def test_clear_test():
    """clear_test：清指定 test 的 progress/logs，game_errors 全局保留"""
    store = TestStateStore()

    store.record_progress("test_a", {"step": "a1"})
    store.record_progress("test_b", {"step": "b1"})
    store.record_log("test_a", {"level": "info", "message": "a_log"})
    store.record_log("test_b", {"level": "info", "message": "b_log"})
    store.record_error("test_a", {"error": "err_a", "test_name": "test_a"})

    store.clear_test("test_a")

    snap_a = store.snapshot("test_a")
    assert len(snap_a["progress"]) == 0
    assert len(snap_a["logs"]) == 0

    snap_b = store.snapshot("test_b")
    assert len(snap_b["progress"]) == 1
    assert len(snap_b["logs"]) == 1

    assert len(snap_a["game_errors"]) == 1
    assert snap_a["game_errors"][0]["error"] == "err_a"

    recent = store.recent("error", 10)
    assert len(recent) >= 1
    assert any(e.get("message") == "err_a" for e in recent)

    print("  PASS test_clear_test")


def test_clear_all():
    """clear_all：全清 3 个缓冲"""
    store = TestStateStore()

    store.record_progress("t", {"step": "s"})
    store.record_log("t", {"level": "info", "message": "m"})
    store.record_error("t", {"error": "e", "test_name": "t"})

    store.clear_all()

    assert store.snapshot("t")["progress"] == []
    assert store.snapshot("t")["logs"] == []
    assert store.snapshot("t")["game_errors"] == []

    print("  PASS test_clear_all")


def test_recent_level_filter():
    """recent：按 level 过滤，全局不分 test"""
    store = TestStateStore()

    store.record_log("t1", {"level": "info", "message": "info_msg"})
    store.record_log("t1", {"level": "warn", "message": "warn_msg"})
    store.record_log("t2", {"level": "error", "message": "error_msg"})
    store.record_error("t1", {"error": "game_err", "test_name": "t1"})

    all_entries = store.recent("all", 100)
    assert len(all_entries) == 4

    error_entries = store.recent("error", 100)
    assert len(error_entries) == 2

    warn_entries = store.recent("warning", 100)
    assert len(warn_entries) == 1

    recent_2 = store.recent("all", 2)
    assert len(recent_2) == 2

    print("  PASS test_recent_level_filter")


def test_snapshot_isolation():
    """snapshot 返回独立拷贝，修改不影响 store"""
    store = TestStateStore()
    store.record_progress("t", {"step": "s1"})

    snap = store.snapshot("t")
    snap["progress"].append({"step": "injected"})

    snap2 = store.snapshot("t")
    assert len(snap2["progress"]) == 1

    print("  PASS test_snapshot_isolation")


def test_snapshot_unknown_test():
    """snapshot 对不存在的 test 返回空列表"""
    store = TestStateStore()
    store.record_progress("existing", {"step": "s1"})

    snap = store.snapshot("nonexistent")
    assert snap["progress"] == []
    assert snap["logs"] == []
    assert snap["game_errors"] == []

    print("  PASS test_snapshot_unknown_test")


if __name__ == "__main__":
    print("=== TestStateStore 单测 ===")
    tests = [
        test_concurrent_record_and_snapshot,
        test_merge_into,
        test_merge_into_no_overwrite_game_errors,
        test_merge_into_empty_data,
        test_game_errors_ring_buffer,
        test_clear_test,
        test_clear_all,
        test_recent_level_filter,
        test_snapshot_isolation,
        test_snapshot_unknown_test,
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
