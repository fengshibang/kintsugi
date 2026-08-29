#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DiagnosticsCollector - 诊断信息收集模块

职责：
- get_debug_output: 聚合 War3 日志 + store 缓冲的运行时错误/日志

（v0.20: analyze_screenshot/VLM 判读已移除——截图判读交由环境内视觉 MCP 完成，插件只采集）

零反向依赖：只依赖 config + store + logger，不引用 mcp_server / test_batch_runner / http_receiver
"""

import os
import json
import logging
from datetime import datetime
from typing import Optional


class DiagnosticsCollector:
    """
    诊断信息收集器。

    覆盖 _get_debug_output 的全部逻辑：
    1. get_debug_output: 聚合 War3 日志 + store.recent 的运行时错误/日志

    （v0.20: VLM 判读已移除，截图只采集不判读）

    构造参数：
        store: TestStateStore 实例（用于读取缓冲的运行时错误/日志）
        config: Config 实例（用于获取 war3_log_dir 等配置）
        logger: 日志记录器（可选）
    """

    def __init__(self, store, config, logger=None):
        self.store = store
        self.config = config
        self.logger = logger or logging.getLogger(__name__)


    def get_debug_output(self, limit=50, level="all", source_dir=None):
        """
        聚合游戏调试输出（纯读取，不启动游戏）。

        从 mcp_server._get_debug_output 忠实搬运（mcp_server.py:1136-1247）。

        聚合来源：
        1. War3 游戏日志文件（config.war3_log_dir → get_war3_log_file_path）
        2. HTTP /error 端点缓存的运行时错误（store 全局缓冲）
        3. HTTP /log 端点缓存的分级日志（store 按 test_name 分组）

        Args:
            limit: 每级最多返回条数
            level: 过滤级别 'all' | 'error' | 'warning'
            source_dir: 源码目录（可选，仅用于上下文展示）

        Returns:
            str: 格式化的调试输出文本
        """
        out = []
        out.append("## 调试输出")
        out.append(f"时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        out.append(f"过滤级别：{level}  每级上限：{limit}")
        out.append("")

        # === 1. War3 游戏日志 ===
        out.append("### War3 游戏日志")
        try:
            log_path = self.config.get_war3_log_file_path(player_id=1)
            if log_path and log_path.exists():
                out.append(f"日志文件：{log_path}")
                try:
                    raw_lines = log_path.read_text(encoding='utf-8', errors='ignore').splitlines()
                except (OSError, IOError) as e:
                    raw_lines = []
                    out.append(f"读取失败：{e}")

                # 按级别过滤（War3 日志通常无标准级别标记，按关键字猜测）
                error_keywords = ('error', '错误', 'fail', '失败', 'exception', '异常', 'FATAL', 'fatal')
                warning_keywords = ('warn', 'warning', '警告', 'deprecated')

                error_lines = []
                warning_lines = []
                other_lines = []
                for line in raw_lines:
                    line_lower = line.lower()
                    if any(kw in line_lower for kw in error_keywords):
                        error_lines.append(line)
                    elif any(kw in line_lower for kw in warning_keywords):
                        warning_lines.append(line)
                    else:
                        other_lines.append(line)

                out.append(
                    f"总行数：{len(raw_lines)}  "
                    f"错误关键字：{len(error_lines)}  "
                    f"警告关键字：{len(warning_lines)}"
                )

                if level in ('all', 'error') and error_lines:
                    out.append(f"\n#### 错误行（最近 {min(limit, len(error_lines))} 条）")
                    for l in error_lines[-limit:]:
                        out.append(f"  [ERROR] {l}")
                if level in ('all', 'warning') and warning_lines:
                    out.append(f"\n#### 警告行（最近 {min(limit, len(warning_lines))} 条）")
                    for l in warning_lines[-limit:]:
                        out.append(f"  [WARN] {l}")
                if level == 'all' and not error_lines and not warning_lines:
                    out.append("\n（日志中未发现错误/警告关键字，显示最后 10 行）")
                    for l in raw_lines[-10:]:
                        out.append(f"  {l}")
            else:
                out.append("（游戏日志文件不存在或 war3_log_dir 未配置）")
        except Exception as e:
            out.append(f"（读取游戏日志出错：{e}）")
        out.append("")

        # === 2. HTTP /error 缓存的游戏内错误 + /log 缓存的分级日志 ===
        # v0.14.0: 委托 store.recent 聚合（消除直插私有字段）
        out.append("### HTTP 缓存的运行时错误与分级日志")
        try:
            recent_entries = self.store.recent(level, limit)
            if recent_entries:
                out.append(f"缓存条目总数：{len(recent_entries)}")

                # 按来源分组展示（game_error vs log）
                game_errors = [e for e in recent_entries if e.get("_source") == "game_error"]
                log_entries = [e for e in recent_entries if e.get("_source") != "game_error"]

                if game_errors:
                    out.append(f"\n#### 运行时错误（{len(game_errors)} 条）")
                    for err in game_errors:
                        test_name = err.get('test_name', 'unknown')
                        error_msg = err.get('message', '')
                        tb = err.get('traceback', '')
                        ts = err.get('timestamp', '')
                        out.append(f"  [ERROR] [{ts}] {test_name}: {error_msg}")
                        if tb:
                            tb_short = tb[:300] + '...' if len(tb) > 300 else tb
                            for tb_line in tb_short.splitlines()[:5]:
                                out.append(f"    {tb_line}")

                if log_entries:
                    out.append(f"\n#### 分级日志（{len(log_entries)} 条）")
                    for entry in log_entries:
                        test_name = entry.get('test_name', 'unknown')
                        lvl = entry.get('level', 'info')
                        cat = entry.get('category', '')
                        msg = entry.get('message', '')
                        ts = entry.get('timestamp', '')
                        tag = 'ERROR' if lvl == 'error' else ('WARN' if lvl in ('warn', 'warning') else 'INFO')
                        out.append(f"  [{tag}] [{ts}] [{test_name}] {cat}: {msg}")
            else:
                out.append("（无缓存错误/日志）")
        except Exception as e:
            out.append(f"（读取 HTTP 缓存出错：{e}）")

        return "\n".join(out)
