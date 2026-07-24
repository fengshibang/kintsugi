#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TestStateStore - 跨线程状态 owner（候选 3 第一阶段）

设计文档：docs/plans/2026-07-22-war3-tester-teststatestore-design.md

职责：
- 持有 5 个跨线程共享缓冲：_game_errors / _progress / _logs /
  _inspect_pending / _inspect_results
- 单把 RLock 覆盖所有方法，消除跨线程竞态
- 零反向依赖：不 import http_receiver / mcp_server / batch_runner

本阶段只新建文件，不改任何现有文件。迁移（HTTPReceiver 瘦身、
mcp_server 注入、batch_runner 切换）在下一阶段进行。
"""

import os
import time
import threading


class TestStateStore:
    """
    跨线程状态 owner。

    缓冲：
      _game_errors     : list[dict]，全局，环形上限 1000
      _progress        : dict[test_name -> list[entry]]
      _logs            : dict[test_name -> list[entry]]
      _inspect_pending : list[{id, expr}]，FIFO 队列
      _inspect_results : dict[id -> data]

    锁：单把 RLock，所有 public 方法 with self._lock 包裹。
    """

    _GAME_ERRORS_CAP = 1000  # 环形上限

    def __init__(self):
        self._lock = threading.RLock()
        self._game_errors = []           # 全局，环形上限 1000
        self._progress = {}              # test_name -> list
        self._logs = {}                  # test_name -> list
        self._inspect_pending = []       # FIFO: append 入，pop(0) 出
        self._inspect_results = {}       # id -> data

    # ── 写入（加锁） ─────────────────────────────────────────────

    def record_progress(self, test_name, entry):
        """记录一条进度条目（按 test_name 分桶）"""
        with self._lock:
            self._progress.setdefault(test_name, []).append(entry)

    def record_log(self, test_name, entry):
        """记录一条结构化日志（按 test_name 分桶）"""
        with self._lock:
            self._logs.setdefault(test_name, []).append(entry)

    def record_error(self, test_name, entry):
        """记录一条全局游戏错误，超 1000 淘汰最旧"""
        with self._lock:
            # 确保 entry 带 test_name（调用方通常已设，这里做兜底）
            if isinstance(entry, dict) and 'test_name' not in entry:
                entry['test_name'] = test_name
            self._game_errors.append(entry)
            if len(self._game_errors) > self._GAME_ERRORS_CAP:
                # 淘汰最旧的一条（保留最新 1000）
                del self._game_errors[0]

    def record_inspect_result(self, id, data):
        """记录一条 inspect 查询结果（游戏端回传）"""
        with self._lock:
            self._inspect_results[id] = data

    # ── inspect 协议 ─────────────────────────────────────────────

    def submit_inspect(self, expr, mode='inspect'):
        """
        提交一个运行时查询，返回唯一 id。

        id 格式：q_{int(time.time()*1000)}_{os.getpid()}
        入队到 _inspect_pending，游戏端 take_pending_inspect 取走执行。

        mode:
          - 'inspect'（默认）：只读表达式，游戏端 load('return ' .. expr)
          - 'exec'：语句块（可带副作用、可改游戏态），游戏端 load(expr)
        """
        with self._lock:
            id = f"q_{int(time.time() * 1000)}_{os.getpid()}"
            self._inspect_pending.append({"id": id, "expr": expr, "mode": mode})
            return id

    def take_inspect(self, id, timeout):
        """
        轮询等待 inspect 结果，超时返回 None。

        0.2s 间隔轮询 _inspect_results[id]，取到即 pop 返回。
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self._lock:
                if id in self._inspect_results:
                    return self._inspect_results.pop(id)
            time.sleep(0.2)
        return None

    def take_pending_inspect(self):
        """
        游戏端拉取一条待执行查询（FIFO pop(0)）。

        无待执行时返回 None。
        """
        with self._lock:
            if not self._inspect_pending:
                return None
            return self._inspect_pending.pop(0)

    # ── 读取 / 合并 ──────────────────────────────────────────────

    def snapshot(self, test_name):
        """
        原子拷贝指定 test_name 的缓冲状态（单段 with lock，全程持锁）。

        返回 dict：
          progress     : list（该 test 的进度条目浅拷贝）
          logs         : list（该 test 的日志条目浅拷贝）
          game_errors  : list（全局 _game_errors 中 test_name 匹配的条目）
        """
        with self._lock:
            return {
                "progress": list(self._progress.get(test_name, [])),
                "logs": list(self._logs.get(test_name, [])),
                "game_errors": [
                    e for e in self._game_errors
                    if isinstance(e, dict) and e.get("test_name", "unknown") == test_name
                ],
            }

    def merge_into(self, test_name, data):
        """
        把缓冲的 progress / logs / game_errors 合并进 data dict。

        - data["progress"] = data.get("progress", []) + 缓冲 progress
        - data["logs"]     = data.get("logs", [])     + 缓冲 logs
        - data["game_errors"] = 过滤后的 game_errors（覆盖或设置）
        - 不清缓冲（诊断后由 clear_test 清）
        - 返回 data
        """
        with self._lock:
            buf_progress = list(self._progress.get(test_name, []))
            buf_logs = list(self._logs.get(test_name, []))
            related_errors = [
                e for e in self._game_errors
                if isinstance(e, dict) and e.get("test_name", "unknown") == test_name
            ]

        # 合并 progress：原 data 字段保留在前，缓冲追加在后
        existing_progress = data.get("progress") or []
        data["progress"] = (existing_progress + buf_progress) if existing_progress else list(buf_progress)

        # 合并 logs：同上
        existing_logs = data.get("logs") or []
        data["logs"] = (existing_logs + buf_logs) if existing_logs else list(buf_logs)

        # game_errors：直接设置（与 http_receiver 基线行为一致）
        if related_errors and not data.get("game_errors"):
            data["game_errors"] = related_errors

        return data

    def recent(self, level, limit):
        """
        全局最近日志/错误（不过滤 test_name），给 get_debug_output 用。

        合并 _logs（全部 test）+ _game_errors，按 level 过滤，取最近 limit 条。

        level: "all" | "error" | "warning"
          - "all"     : 全部条目
          - "error"   : 只 _game_errors + _logs 中 level=="error"
          - "warning" : 只 _logs 中 level in ("warn", "warning")
        """
        with self._lock:
            # 合并所有日志条目（带统一结构）
            all_entries = []
            for entries in self._logs.values():
                all_entries.extend(entries)
            # game_errors 转为统一结构（带 level="error"）
            for e in self._game_errors:
                if isinstance(e, dict):
                    all_entries.append({
                        "level": "error",
                        "message": e.get("error", ""),
                        "test_name": e.get("test_name", "unknown"),
                        "timestamp": e.get("timestamp", ""),
                        "traceback": e.get("traceback", ""),
                        "_source": "game_error",
                    })

            # 按 level 过滤
            if level == "error":
                filtered = [
                    e for e in all_entries
                    if (isinstance(e, dict) and e.get("level") == "error")
                ]
            elif level == "warning":
                filtered = [
                    e for e in all_entries
                    if (isinstance(e, dict) and e.get("level") in ("warn", "warning"))
                ]
            else:  # "all"
                filtered = list(all_entries)

            # 取最近 limit 条
            return filtered[-limit:] if limit > 0 else []

    # ── 清理 ─────────────────────────────────────────────────────

    def clear_test(self, test_name):
        """
        清除指定 test 的 progress / logs 缓冲。

        不清 _game_errors（全局保留，只 clear_all 清）。
        """
        with self._lock:
            self._progress.pop(test_name, None)
            self._logs.pop(test_name, None)

    def clear_all(self):
        """清除全部 5 个缓冲"""
        with self._lock:
            self._game_errors.clear()
            self._progress.clear()
            self._logs.clear()
            self._inspect_pending.clear()
            self._inspect_results.clear()
