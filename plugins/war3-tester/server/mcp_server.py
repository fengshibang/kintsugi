#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
War3 Tester 通用 MCP Server

提供地图编译、游戏测试与 Named Pipe LLM Agent 桥接的 MCP 工具接口（stdio JSON-RPC）。

工具：
- compile_map / compile_only: 编译地图
- run_game / launch_only: 启动游戏
- stop_game: 停止游戏
- send_key: 发送键盘事件
- take_screenshot: 截取游戏窗口
- test_commit: 运行测试（编译+启动+等待结果）
- run_test_batch / discover_tests / run_unit_test / scaffold_test / tdd_red / tdd_green
- watch_unit_tests / stop_watch / get_watch_results
- toggle_test / get_project_info / get_debug_output / save_adapter_hook / setup_environment
- inspect_game / exec_game: 通过 Windows 命名管道 (\\.\pipe\war3_agent) 执行 Lua 查询/语句
- game_status / game_set_mode / game_observe / game_act / game_events / game_inspect / game_setup / game_report_bug:
  LLM Agent 实机探索、步进冻结与五大 Oracle Bug 巡检工具集
- cleanup_all: 清理所有资源
- stop_http_server: 停止 HTTP 服务器
"""

import asyncio
import json
import sys
import time
import re
import os
import base64
import mimetypes
import shutil
import urllib.request
import urllib.error
import subprocess
import atexit
import signal
from pathlib import Path
from datetime import datetime
from typing import Optional

# 自解析路径（【红线 6】严禁依赖 cwd 或硬编码绝对路径）
SERVER_DIR = Path(__file__).parent
sys.path.insert(0, str(SERVER_DIR))

from config import Config
from env_bridge import create_executor
from http_receiver import HTTPReceiver
from test_batch_runner import TestBatchRunner
from desktop_runner import DesktopRunner
from watcher import FileWatcher
from logger import setup_logger
from test_state_store import TestStateStore
from test_mode_flag import TestModeFlag
from test_entry_preparer import TestEntryPreparer
from diagnostics_collector import DiagnosticsCollector
from scaffolder import ProjectScaffolder
from environment_provisioner import EnvironmentProvisioner
from pipe_client import PipeClient, PipeClientError


class ToolSpec:
    """工具注册条目：绑定 schema 与 handler 到同一条目（单源注册）。"""
    __slots__ = ('name', 'schema', 'handler')

    def __init__(self, name: str, schema: dict, handler):
        self.name = name
        self.schema = schema
        self.handler = handler


class War3TesterMCP:
    """War3 Tester MCP Server"""

    def __init__(self):
        _war3_project_root = os.getenv('WAR3_PROJECT_ROOT')
        self.config = Config(project_root=Path(_war3_project_root) if _war3_project_root else None)
        self.logger = setup_logger('war3-mcp')
        self.executor = create_executor(self.config)
        self.store = TestStateStore()
        self.http_receiver = HTTPReceiver(host=self.config.http_host, port=self.config.http_port, store=self.store)
        self.pipe_client = PipeClient()
        self.project_root = self.config.project_root

        self.test_mode_flag = TestModeFlag(logger=self.logger)
        self.diagnostics_collector = DiagnosticsCollector(self.store, self.config, logger=self.logger)
        self.test_entry_preparer = TestEntryPreparer(
            self.test_mode_flag, SERVER_DIR, self.config, logger=self.logger
        )
        self.project_scaffolder = ProjectScaffolder(self.config, logger=self.logger)
        self.environment_provisioner = EnvironmentProvisioner(
            self.config, SERVER_DIR.parent, logger=self.logger
        )

        self.batch_runner = TestBatchRunner(
            self.config, self.executor, self.http_receiver,
            test_mode_flag=self.test_mode_flag,
            test_entry_preparer=self.test_entry_preparer,
            diagnostics_collector=self.diagnostics_collector,
            store=self.store,
            pipe_client=self.pipe_client
        )
        self.desktop_runner = DesktopRunner(self.config, self.executor)
        self.file_watcher = FileWatcher(self.desktop_runner, self.config)

        self._tool_registry = self._register_tools()

        self.capabilities = {
            "tools": [spec.schema for spec in self._tool_registry.values()],
            "resources": [
                {
                    "uri": "war3://logs/compile",
                    "name": "编译日志",
                    "description": "地图编译日志"
                },
                {
                    "uri": "war3://logs/game",
                    "name": "游戏日志",
                    "description": "War3 游戏运行日志"
                },
                {
                    "uri": "war3://logs/game/list",
                    "name": "游戏日志列表",
                    "description": "可用的游戏日志文件列表"
                }
            ]
        }

    def _format_pipe_value(self, val) -> str:
        if isinstance(val, (dict, list)):
            return json.dumps(val, ensure_ascii=False, indent=2)
        return str(val)

    def _register_tools(self) -> dict:
        """注册所有工具到 registry（单源）。"""
        registry = {}

        def _add(name, description, input_schema, handler):
            schema = {
                "name": name,
                "description": description,
                "inputSchema": input_schema
            }
            registry[name] = ToolSpec(name, schema, handler)

        # 1. compile_map / compile_only
        def _handle_compile(arguments):
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            source_dir = self.config.resolve_source_dir(arguments.get("source_dir"))
            result = self.executor.compile(source_dir)
            if result.get("success"):
                return {
                    "content": [{"type": "text", "text": f"[OK] 地图编译成功\n\n时间：{timestamp}\n\n{result.get('message', '')}"}]
                }
            else:
                return {
                    "content": [{"type": "text", "text": f"[FAIL] 地图编译失败\n\n时间：{timestamp}\n\n{result.get('error', '未知错误')}"}],
                    "isError": True
                }

        _add("compile_map",
             "编译地图 - 使用 w2l.exe slk 编译地图，不启动游戏",
             {"type": "object", "properties": {
                 "source_dir": {"type": "string", "description": "源码目录路径，默认使用 config.compile_source_dir"}
             }},
             _handle_compile)

        _add("compile_only",
             "仅编译地图，不启动游戏",
             {"type": "object", "properties": {
                 "source_dir": {"type": "string", "description": "源码目录路径"}
             }},
             _handle_compile)

        # 2. test_commit
        def _handle_test_commit(arguments):
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            test_name = arguments.get("test_name", "unknown")
            test_file = arguments.get("test_file")
            timeout = arguments.get("timeout", 60)
            platform = arguments.get("platform")
            source_dir = self.config.resolve_source_dir(arguments.get("source_dir"))
            auto_screenshot_on_failure = arguments.get("auto_screenshot_on_failure", True)
            if not platform:
                run_mode, _ = self.config.get_run_mode_with_source()
                platform = run_mode
            result = self.test_commit(test_name, test_file, timeout, platform, source_dir,
                                      auto_screenshot_on_failure)
            messages = [f"## 测试代码变更\n\n时间：{timestamp}"]
            if result.get("message"):
                messages.append(result.get("message", ""))
            elif result.get("error"):
                messages.append(f"\n[ERROR] {result.get('error', 'unknown')}")
            return {"content": [{"type": "text", "text": "\n".join(messages)}]}

        _add("test_commit",
             "测试代码变更 - 编译地图并启动游戏运行测试",
             {"type": "object", "properties": {
                 "test_name": {"type": "string", "description": "测试名称，如 'test_hero_h000'"},
                 "test_file": {"type": "string", "description": "测试 Lua 文件名（如 'test_skill_a00d.lua'）"},
                 "timeout": {"type": "integer", "description": "等待测试完成的超时时间（秒），默认 60", "default": 60},
                 "platform": {"type": "string", "description": "游戏平台：'ydwe' 或 'kkwe'，默认自动选择", "enum": ["ydwe", "kkwe"]},
                 "source_dir": {"type": "string", "description": "源码目录路径（支持 ${workspaceRoot} 变量）"},
                 "auto_screenshot_on_failure": {"type": "boolean", "default": True, "description": "失败时自动截图（仅 crash/timeout/unknown 触发，v2 增强）"}
             }, "required": ["test_name"]},
             _handle_test_commit)

        # 3. run_test_batch
        def _handle_run_test_batch(arguments):
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            test_filter = arguments.get("test_filter", "all")
            stop_on_first_failure = arguments.get("stop_on_first_failure", False)
            max_retries = arguments.get("max_retries", 1)
            timeout_per_test = arguments.get("timeout_per_test", 90)
            auto_ss = arguments.get("auto_screenshot_on_failure", True)
            platform = arguments.get("platform")
            source_dir = arguments.get("source_dir")
            layer = arguments.get("layer")
            if source_dir:
                source_dir = str(self.config.resolve_path(source_dir))
            if not platform:
                run_mode, _ = self.config.get_run_mode_with_source()
                platform = run_mode
            batch_result = self.batch_runner.run_test_batch(
                test_filter=test_filter, stop_on_first_failure=stop_on_first_failure,
                max_retries=max_retries, timeout_per_test=timeout_per_test,
                auto_screenshot_on_failure=auto_ss, source_dir=source_dir, platform=platform,
                layer=layer)
            messages = [f"## 批量测试\n\n时间：{timestamp}", batch_result.get("message", "")]
            if not batch_result.get("success") and batch_result.get("error"):
                messages.append(f"\n[ERROR] {batch_result['error']}")
            summary = batch_result.get("summary", {})
            if summary:
                messages.append(f"\n汇总：{summary.get('passed')}/{summary.get('total')} 通过，"
                                f"failure_types={summary.get('failure_types', {})}")
            failed = batch_result.get("failed", [])
            if failed:
                messages.append(f"失败列表：{failed}")
            return {"content": [{"type": "text", "text": "\n".join(messages)}]}

        _add("run_test_batch",
             "批量运行测试 - 顺序运行多个测试（每个独立游戏会话），返回结构化汇总。支持 filter=all/failed/列表、重试、超时、失败截图、failure_type 分类（v2 新增）",
             {"type": "object", "properties": {
                 "test_filter": {"type": ["string", "array"], "description": "'all'(默认) | 'failed'(复用上次失败列表) | 测试名/文件名列表 | glob 子串", "default": "all"},
                 "stop_on_first_failure": {"type": "boolean", "default": False, "description": "首个失败即停止后续测试"},
                 "max_retries": {"type": "integer", "default": 1, "description": "单测失败最大重试次数"},
                 "timeout_per_test": {"type": "integer", "default": 90, "description": "单测超时秒数"},
                 "auto_screenshot_on_failure": {"type": "boolean", "default": True, "description": "失败时自动截图（仅 crash/timeout/unknown 触发）"},
                 "platform": {"type": "string", "enum": ["ydwe", "kkwe"], "description": "游戏平台，默认自动选择"},
                 "source_dir": {"type": "string", "description": "源码目录路径"},
                 "layer": {"type": "string", "description": "按测试层过滤：'all'(默认) | 'unit' | 'integration' | 'e2e'（M3 新增）", "enum": ["all", "unit", "integration", "e2e"]}
             }},
             _handle_run_test_batch)

        # 4. discover_tests
        def _handle_discover_tests(arguments):
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            flt = arguments.get("filter")
            source_dir = arguments.get("source_dir")
            layer = arguments.get("layer")
            if source_dir:
                source_dir = str(self.config.resolve_path(source_dir))
            discovery = self.batch_runner.discover_tests(source_dir, filter_pattern=flt, layer=layer)
            if discovery.get("success"):
                tests = discovery.get("tests", [])
                lines = [f"发现 {len(tests)} 个测试（估算 {discovery.get('total_est_seconds')}s）："]
                for t in tests:
                    layer_info = f", layer={t.get('layer', 'integration')}"
                    lines.append(f"  - {t['test_name']} ({t['type']}{layer_info}, ~{t['est_seconds']}s)")
                return {"content": [{"type": "text", "text": f"## 测试发现\n\n时间：{timestamp}\n\n" + "\n".join(lines)}]}
            return {"content": [{"type": "text", "text": f"[FAIL] {discovery.get('error', '未知错误')}"}], "isError": True}

        _add("discover_tests",
             "发现测试 - 扫描测试目录，返回测试列表 + 分类(sync/async) + 估算耗时（v2 新增）",
             {"type": "object", "properties": {
                 "filter": {"type": "string", "description": "过滤子串（匹配 test_name），可选"},
                 "source_dir": {"type": "string", "description": "源码目录路径"}
             }},
             _handle_discover_tests)

        # 5. launch_only / run_game
        def _handle_launch_or_run(tool_name, arguments):
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            map_path = arguments.get("map_path", str(self.config.compile_output_path / self.config.compile_output_name))
            platform = arguments.get("platform")
            inject_inspect = arguments.get("inject_inspect", True) if tool_name == "run_game" else False
            if not platform:
                run_mode, _ = self.config.get_run_mode_with_source()
                platform = run_mode
            if inject_inspect:
                resolved_source = self.config.resolve_source_dir(arguments.get("source_dir"))
                test_dir = self.test_entry_preparer.prepare_inspect_only(resolved_source)
                if test_dir is None:
                    return {
                        "content": [{"type": "text", "text": f"[FAIL] source_dir 非有效 w2l 项目根（缺 w3x2lni/）: {resolved_source}，可能传错（如多了子目录）"}],
                        "isError": True
                    }
                compile_result = self.executor.compile(resolved_source)
                if not compile_result.get("success"):
                    return {
                        "content": [{"type": "text", "text": f"[FAIL] 地图编译失败（inject_inspect 启用）\n\n时间：{timestamp}\n\n{compile_result.get('error', '未知错误')}"}],
                        "isError": True
                    }
                self.logger.info("[run_game] 编译成功，准备启动游戏（Named Pipe Agent 已注入）")
            result = self.executor.run_game(map_path, platform)
            if result.get("success"):
                msg = f"[OK] 游戏已启动\n\n{result.get('message', '')}"
                if inject_inspect:
                    msg += "\n\n（Named Pipe Agent 引导已注入，可使用 inspect_game / exec_game / game_* 工具）"
                return {"content": [{"type": "text", "text": msg}]}
            else:
                return {
                    "content": [{"type": "text", "text": f"[FAIL] 游戏启动失败\n\n{result.get('error', '未知错误')}"}],
                    "isError": True
                }

        _add("launch_only",
             "仅启动游戏，不编译",
             {"type": "object", "properties": {
                 "map_path": {"type": "string", "description": "地图文件路径"},
                 "platform": {"type": "string", "description": "游戏平台：'ydwe' 或 'kkwe'", "enum": ["ydwe", "kkwe"]}
             }},
             lambda args: _handle_launch_or_run("launch_only", args))

        _add("run_game",
             "仅启动游戏，不运行测试",
             {"type": "object", "properties": {
                 "map_path": {"type": "string", "description": "地图文件路径"},
                 "platform": {"type": "string", "description": "游戏平台：'ydwe' 或 'kkwe'", "enum": ["ydwe", "kkwe"]},
                 "inject_inspect": {"type": "boolean", "description": "是否自动注入 Named Pipe Agent 启动引导并重编译（默认 True，支持 inspect_game/exec_game/game_* 工具直接连接 \\\\.\\pipe\\war3_agent）", "default": True},
                 "source_dir": {"type": "string", "description": "inject_inspect 启用时，地图源码目录（如 D:\\maps\\wzns），默认 config.compile_source_dir"}
             }},
             lambda args: _handle_launch_or_run("run_game", args))

        # 6. stop_game
        def _handle_stop_game(arguments):
            self.pipe_client.close()
            result = self.executor.stop_game()
            if result.get("success"):
                return {"content": [{"type": "text", "text": f"[OK] {result.get('message', '游戏已关闭')}"}]}
            else:
                detail = result.get('message') or result.get('error') or '游戏关闭失败'
                if result.get('remaining'):
                    detail += f"\n残留: {result['remaining']}"
                return {"content": [{"type": "text", "text": f"[FAIL] {detail}"}], "isError": True}

        _add("stop_game",
             "关闭魔兽争霸 3 游戏进程",
             {"type": "object", "properties": {
                 "platform": {"type": "string", "description": "游戏平台：'ydwe' 或 'kkwe'", "enum": ["ydwe", "kkwe"]}
             }},
             _handle_stop_game)

        # 7. stop_http_server
        def _handle_stop_http_server(arguments):
            self.http_receiver.stop()
            return {"content": [{"type": "text", "text": "[OK] HTTP 服务器将随主进程退出自动关闭"}]}

        _add("stop_http_server",
             "关闭 HTTP 测试服务器",
             {"type": "object", "properties": {}, "required": []},
             _handle_stop_http_server)

        # 8. cleanup_all
        def _handle_cleanup_all(arguments):
            self.pipe_client.close()
            stop_result = self.executor.stop_game()
            self.http_receiver.stop()
            return {"content": [{"type": "text", "text": f"[OK] 清理完成\n\n{stop_result.get('message', '')}"}]}

        _add("cleanup_all",
             "清理所有资源 - 关闭 war3.exe 进程、命名管道连接和 HTTP 服务器",
             {"type": "object", "properties": {}, "required": []},
             _handle_cleanup_all)

        # 9. take_screenshot
        def _handle_take_screenshot(arguments):
            test_name = arguments.get("test_name", "unknown")
            filename = arguments.get("filename")
            window_title = arguments.get("window_title")
            result = self.executor.take_screenshot(test_name, filename, window_title)
            if result.get("success"):
                base_text = (f"[OK] 截图已保存\n\n{result.get('message', '')}\n\n"
                             f"WSL 路径：{result.get('path_wsl', '')}\nWindows 路径：{result.get('path', '')}"
                             f"\n\n(判读请用环境内视觉 MCP 工具读取上述路径，本插件不做判读)")
                return {"content": [{"type": "text", "text": base_text}]}
            else:
                return {"content": [{"type": "text", "text": f"[FAIL] 截图失败\n\n{result.get('error', '未知错误')}"}], "isError": True}

        _add("take_screenshot",
             "截取游戏窗口截图，只负责采集并返回 PNG 路径。画面判读请用环境内的视觉 MCP 工具（如 zhipuVision 的 analyze_image）读取返回的路径，本插件不含判读能力。",
             {"type": "object", "properties": {
                 "test_name": {"type": "string", "description": "测试名称，用于组织截图文件"},
                 "filename": {"type": "string", "description": "截图文件名（可选）"},
                 "window_title": {"type": "string", "description": "窗口标题关键词（可选）"}
             }, "required": ["test_name"]},
             _handle_take_screenshot)

        # 10. send_key
        def _handle_send_key(arguments):
            key = arguments.get("key", "enter")
            result = self.executor.send_key(key)
            if result.get("success"):
                return {"content": [{"type": "text", "text": f"[OK] 已发送 {key} 键\n\n{result.get('message', '')}"}]}
            else:
                return {"content": [{"type": "text", "text": f"[FAIL] 发送按键失败\n\n{result.get('error', '未知错误')}"}], "isError": True}

        _add("send_key",
             "向 War3 游戏窗口发送键盘事件。支持单键（'enter', 'a', 'f1', 'up' 等）和组合键（'ctrl+c', 'shift+a', 'alt+f4', 'ctrl+shift+s' 等，+ 分隔修饰键与主键）。",
             {"type": "object", "properties": {
                 "key": {"type": "string", "description": "按键名称。单键如 'enter', 'space', 'escape', 'a'-'z', '0'-'9', 'f1'-'f12', 'up', 'down', 'left', 'right', 'shift', 'ctrl', 'alt', 'tab', 'backspace', 'delete' 等。组合键用 + 分隔：'ctrl+c', 'shift+enter', 'alt+f4', 'ctrl+shift+a'。"}
             }, "required": ["key"]},
             _handle_send_key)

        # 12. toggle_test
        def _handle_toggle_test(arguments):
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            enabled = arguments.get("enabled", True)
            source_dir = self.config.resolve_source_dir(arguments.get("source_dir"))
            result = self.toggle_test(enabled, source_dir)
            if result.get("success"):
                return {"content": [{"type": "text", "text": f"[OK] 测试模式{result.get('action', '')}\n\n时间：{timestamp}"}]}
            else:
                msg = f"[FAIL] toggle_test 未完成\n\n时间：{timestamp}\n"
                if result.get("compile_error"):
                    msg += f"编译失败：{result['compile_error']}"
                return {"content": [{"type": "text", "text": msg}], "isError": True}

        _add("toggle_test",
             "一键开关自动测试模式。关闭时 auto-test 模块不加载（手动游戏零干扰：无横幅/无 log 拦截/无自动选难度/无自动跑测试）；开启时恢复默认加载。变更后自动重编译地图。",
             {"type": "object", "properties": {
                 "enabled": {"type": "boolean", "description": "true=开启(恢复 auto-test 加载，跑测试仍需 test_commit)；false=关闭(模块不加载，手动游戏零干扰)"},
                 "source_dir": {"type": "string", "description": "源码目录路径，默认 config.compile_source_dir"}
             }, "required": ["enabled"]},
             _handle_toggle_test)

        # 13. get_project_info
        def _handle_get_project_info(arguments):
            try:
                source_dir = self.config.resolve_source_dir(arguments.get("source_dir"))
                max_depth = arguments.get("max_depth", 3)
                result = self._get_project_info(source_dir, max_depth)
                return {"content": [{"type": "text", "text": result}]}
            except Exception as e:
                return {"content": [{"type": "text", "text": f"[FAIL] get_project_info 失败：{e}"}], "isError": True}

        _add("get_project_info",
             "地图/脚本结构分析 - 扫描项目地图脚本目录，返回结构化分析：目录树概要、各模块文件计数、代码行数统计、关键入口文件。纯静态分析，只读文件系统，不启动游戏。",
             {"type": "object", "properties": {
                 "source_dir": {"type": "string", "description": "源码目录路径，默认 config.compile_source_dir"},
                 "max_depth": {"type": "integer", "description": "目录树扫描最大深度，默认 3", "default": 3}
             }},
             _handle_get_project_info)

        # 14. inspect_game (Named Pipe)
        def _handle_inspect_game(arguments):
            expr = arguments.get("expr")
            timeout = arguments.get("timeout", 5)
            pid = arguments.get("pid")
            if not expr:
                return {"content": [{"type": "text", "text": "[FAIL] 缺少 expr 参数"}], "isError": True}
            try:
                resp = self.pipe_client.request(
                    "inspect",
                    {"expr": expr},
                    timeout_ms=int(timeout * 1000),
                    pid=pid
                )
            except Exception as e:
                return {"content": [{"type": "text", "text": f"[FAIL] 命名管道查询失败：{e}"}], "isError": True}

            if resp.get("ok"):
                payload = resp.get("payload", {})
                val = payload.get("result") if isinstance(payload, dict) else payload
                return {"content": [{"type": "text", "text": f"[OK] 查询结果：\n{self._format_pipe_value(val)}"}]}
            else:
                err = resp.get("error", {})
                err_msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
                return {"content": [{"type": "text", "text": f"[FAIL] 游戏端执行错误：{err_msg}"}], "isError": True}

        _add("inspect_game",
             "运行时对象检查（Named Pipe） - 通过 Windows 命名管道 (\\\\.\\pipe\\war3_agent) 在游戏内实时执行 Lua 表达式并返回结果。支持多进程并发且无端口冲突。",
             {"type": "object", "properties": {
                 "expr": {"type": "string", "description": "要在游戏内执行的 Lua 表达式（如 'Player.get(1):getGold()'）"},
                 "timeout": {"type": "integer", "description": "超时时间（秒），默认 5", "default": 5},
                 "pid": {"type": "integer", "description": "指定连接的 War3.exe 进程 PID（多开时可选，连接 \\\\.\\pipe\\war3_agent_<pid>）"}
             }, "required": ["expr"]},
             _handle_inspect_game)

        # 14b. exec_game (Named Pipe)
        def _handle_exec_game(arguments):
            code = arguments.get("code")
            timeout = arguments.get("timeout", 5)
            pid = arguments.get("pid")
            if not code:
                return {"content": [{"type": "text", "text": "[FAIL] 缺少 code 参数"}], "isError": True}
            try:
                resp = self.pipe_client.request(
                    "inspect",
                    {"expr": code},
                    timeout_ms=int(timeout * 1000),
                    pid=pid
                )
            except Exception as e:
                return {"content": [{"type": "text", "text": f"[FAIL] 命名管道执行失败：{e}"}], "isError": True}

            if resp.get("ok"):
                payload = resp.get("payload", {})
                val = payload.get("result") if isinstance(payload, dict) else payload
                return {"content": [{"type": "text", "text": f"[OK] 执行结果：\n{self._format_pipe_value(val)}"}]}
            else:
                err = resp.get("error", {})
                err_msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
                return {"content": [{"type": "text", "text": f"[FAIL] 游戏端执行错误：{err_msg}"}], "isError": True}

        _add("exec_game",
             "游戏端执行 Lua 语句块（Named Pipe） - 通过 Windows 命名管道 (\\\\.\\pipe\\war3_agent) 在游戏内执行任意 Lua 语句块（可带副作用、修改游戏态）并回传返回值。",
             {"type": "object", "properties": {
                 "code": {"type": "string", "description": "要在游戏内执行的 Lua 语句块（如 'Player.get(1):addGold(100); return Player.get(1):getGold()'）"},
                 "timeout": {"type": "integer", "description": "超时时间（秒），默认 5", "default": 5},
                 "pid": {"type": "integer", "description": "指定连接的 War3.exe 进程 PID（多开时可选）"}
             }, "required": ["code"]},
             _handle_exec_game)

        # 15. get_debug_output
        def _handle_get_debug_output(arguments):
            try:
                limit = arguments.get("limit", 50)
                level = arguments.get("level", "all")
                source_dir = arguments.get("source_dir")
                result = self._get_debug_output(limit, level, source_dir)
                return {"content": [{"type": "text", "text": result}]}
            except Exception as e:
                return {"content": [{"type": "text", "text": f"[FAIL] get_debug_output 失败：{e}"}], "isError": True}

        _add("get_debug_output",
             "调试输出捕获 - 聚合游戏的调试输出：① War3 游戏日志（按 config.war3_log_dir 定位）② HTTP /error 端点缓存的运行时错误。按 error/warning 分级返回最近 N 条。纯读取，不启动游戏。",
             {"type": "object", "properties": {
                 "limit": {"type": "integer", "description": "每级最多返回条数，默认 50", "default": 50},
                 "level": {"type": "string", "description": "过滤级别：'all'(默认) | 'error' | 'warning'", "enum": ["all", "error", "warning"]},
                 "source_dir": {"type": "string", "description": "源码目录路径（仅用于日志上下文，可选）"}
             }},
             _handle_get_debug_output)

        # 16. run_unit_test
        def _handle_run_unit_test(arguments):
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            test_name = arguments.get("test_name", "unknown")
            source_dir = arguments.get("source_dir")
            timeout = arguments.get("timeout", 10)
            if source_dir:
                source_dir = str(self.config.resolve_path(source_dir))
            try:
                result = self.desktop_runner.run_unit_test(test_name, source_dir, timeout)
                messages = [f"## 桌面单测\n\n时间：{timestamp}"]
                messages.append(f"测试名称：{result.get('test_name', test_name)}")
                messages.append(f"结果：{'通过' if result.get('success') else '失败'}")
                messages.append(f"耗时：{result.get('elapsed', 0):.2f}s")
                if result.get('failure_type'):
                    messages.append(f"failure_type: {result.get('failure_type')}")
                if result.get('error'):
                    messages.append(f"错误：{result.get('error')}")
                if result.get('details'):
                    messages.append(f"\n详情：\n{result.get('details')}")
                if result.get('cases'):
                    messages.append(f"\n用例：{result.get('cases')}")
                return {"content": [{"type": "text", "text": "\n".join(messages)}]}
            except Exception as e:
                return {"content": [{"type": "text", "text": f"[FAIL] run_unit_test 失败：{e}"}], "isError": True}

        _add("run_unit_test",
             "桌面纯逻辑单测 - 不编译地图、不启动游戏，用桌面 lua5.3 秒级跑纯逻辑测试。依赖 jass_mock 隔离游戏 API，适合 TDD 快速反馈循环。",
             {"type": "object", "properties": {
                 "test_name": {"type": "string", "description": "测试名称（如 'test_talent_config'）"},
                 "source_dir": {"type": "string", "description": "源码目录路径（默认 config.compile_source_dir）"},
                 "timeout": {"type": "integer", "description": "超时时间（秒），默认 10", "default": 10}
             }, "required": ["test_name"]},
             _handle_run_unit_test)

        # 17. scaffold_test
        def _handle_scaffold_test(arguments):
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            module = arguments.get("module")
            layer = arguments.get("layer", "unit")
            name = arguments.get("name")
            if not module:
                return {"content": [{"type": "text", "text": "[FAIL] 缺少 module 参数"}], "isError": True}
            source_dir = self.config.resolve_source_dir(arguments.get("source_dir"))
            try:
                result = self._scaffold_test(module, layer, name, source_dir)
                if result.get("success"):
                    messages = [f"## 测试骨架生成\n\n时间：{timestamp}"]
                    messages.append(f"模块：{module}")
                    messages.append(f"层：{layer}")
                    messages.append(f"文件：{result.get('file')}")
                    messages.append(f"\n{result.get('message')}")
                    return {"content": [{"type": "text", "text": "\n".join(messages)}]}
                else:
                    return {"content": [{"type": "text", "text": f"[FAIL] {result.get('error', '生成失败')}"}], "isError": True}
            except Exception as e:
                return {"content": [{"type": "text", "text": f"[FAIL] scaffold_test 失败：{e}"}], "isError": True}

        _add("scaffold_test",
             "生成 TDD 测试骨架 - 按模块名+层生成 Arrange-Act-Assert 三段式测试文件，自动注册进测试列表。unit 层用桌面跑（秒级），integration/e2e 用游戏内跑。",
             {"type": "object", "properties": {
                 "module": {"type": "string", "description": "模块名（如 'talent'、'skill_a00d'）"},
                 "layer": {"type": "string", "description": "测试层：'unit'（桌面秒级）| 'integration'（游戏内）| 'e2e'（全流程）", "enum": ["unit", "integration", "e2e"]},
                 "name": {"type": "string", "description": "测试名（可选，默认 test_<layer>_<module>）"},
                 "source_dir": {"type": "string", "description": "源码目录路径（默认 config.compile_source_dir）"}
             }, "required": ["module", "layer"]},
             _handle_scaffold_test)

        # 17.5 save_adapter_hook
        def _handle_save_adapter_hook(arguments):
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            name = arguments.get("name")
            content = arguments.get("content")
            source_dir = arguments.get("source_dir")
            if not name:
                return {"content": [{"type": "text", "text": "[FAIL] 缺少 name 参数"}], "isError": True}
            if not content:
                return {"content": [{"type": "text", "text": "[FAIL] 缺少 content 参数"}], "isError": True}
            try:
                result = self._save_adapter_hook(name, content, source_dir)
                if result.get("success"):
                    messages = [f"## 适配钩子保存\n\n时间：{timestamp}"]
                    messages.append(f"钩子名：{name}")
                    messages.append(f"文件：{result.get('file')}")
                    messages.append(f"\n{result.get('message')}")
                    return {"content": [{"type": "text", "text": "\n".join(messages)}]}
                else:
                    return {"content": [{"type": "text", "text": f"[FAIL] {result.get('error', '保存失败')}"}], "isError": True}
            except Exception as e:
                return {"content": [{"type": "text", "text": f"[FAIL] save_adapter_hook 失败：{e}"}], "isError": True}

        _add("save_adapter_hook",
             "保存 AI 生成的适配钩子 - 持久化到 _war3_tester/adapters/ 目录，test_entry_preparer 自动生成 adapter_loader.lua，启动时自动加载。",
             {"type": "object", "properties": {
                 "name": {"type": "string", "description": "钩子名（不含 .lua 后缀，如 'difficulty_skip'）"},
                 "content": {"type": "string", "description": "钩子 lua 内容"},
                 "source_dir": {"type": "string", "description": "源码目录路径（默认 config.compile_source_dir）"}
             }, "required": ["name", "content"]},
             _handle_save_adapter_hook)

        # 18. tdd_red
        def _handle_tdd_red(arguments):
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            test_name = arguments.get("test_name", "unknown")
            layer = arguments.get("layer", "unit")
            source_dir = arguments.get("source_dir")
            timeout = arguments.get("timeout", 60)
            if source_dir:
                source_dir = str(self.config.resolve_path(source_dir))
            try:
                result = self._tdd_red(test_name, layer, source_dir, timeout)
                messages = [f"## TDD Red 阶段\n\n时间：{timestamp}"]
                messages.append(f"测试：{test_name}")
                messages.append(f"层：{layer}")
                messages.append(f"状态：{result.get('status')}")
                messages.append(f"failure_type: {result.get('failure_type')}")
                if result.get('status') == 'red_valid':
                    messages.append("\n✅ Red 成立：测试预期失败，测试有效")
                elif result.get('status') == 'red_invalid':
                    messages.append("\n❌ Red 不成立：测试写错或环境问题")
                    messages.append(f"原因：{result.get('reason')}")
                elif result.get('status') == 'green':
                    messages.append("\n⚠️ 测试通过了，但预期应该失败")
                if result.get('error'):
                    messages.append(f"\n错误：{result.get('error')}")
                return {"content": [{"type": "text", "text": "\n".join(messages)}]}
            except Exception as e:
                return {"content": [{"type": "text", "text": f"[FAIL] tdd_red 失败：{e}"}], "isError": True}

        _add("tdd_red",
             "TDD Red 阶段 - 跑测试预期失败，确认测试有效。区分「预期 assertion fail」（测试有效，Red 成立）vs「意外 env_error/compile_error」（测试写错，Red 不成立）。unit 层用 run_unit_test，integration/e2e 用 test_commit。",
             {"type": "object", "properties": {
                 "test_name": {"type": "string", "description": "测试名称"},
                 "layer": {"type": "string", "description": "测试层（决定用 run_unit_test 还是 test_commit）", "enum": ["unit", "integration", "e2e"], "default": "unit"},
                 "source_dir": {"type": "string", "description": "源码目录路径"},
                 "timeout": {"type": "integer", "description": "超时时间（秒），默认 60", "default": 60}
             }, "required": ["test_name"]},
             _handle_tdd_red)

        # 19. tdd_green
        def _handle_tdd_green(arguments):
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            test_name = arguments.get("test_name", "unknown")
            layer = arguments.get("layer", "unit")
            source_dir = arguments.get("source_dir")
            timeout = arguments.get("timeout", 60)
            if source_dir:
                source_dir = str(self.config.resolve_path(source_dir))
            try:
                result = self._tdd_green(test_name, layer, source_dir, timeout)
                messages = [f"## TDD Green 阶段\n\n时间：{timestamp}"]
                messages.append(f"测试：{test_name}")
                messages.append(f"层：{layer}")
                messages.append(f"结果：{'通过' if result.get('success') else '失败'}")
                messages.append(f"耗时：{result.get('elapsed', 0):.2f}s")
                if result.get('success'):
                    messages.append("\n✅ Green 成立：测试通过")
                else:
                    messages.append("\n❌ Green 不成立：测试仍失败")
                    messages.append(f"failure_type: {result.get('failure_type')}")
                    if result.get('error'):
                        messages.append(f"错误：{result.get('error')}")
                return {"content": [{"type": "text", "text": "\n".join(messages)}]}
            except Exception as e:
                return {"content": [{"type": "text", "text": f"[FAIL] tdd_green 失败：{e}"}], "isError": True}

        _add("tdd_green",
             "TDD Green 阶段 - 跑测试预期通过。unit 层用 run_unit_test，integration/e2e 用 test_commit。",
             {"type": "object", "properties": {
                 "test_name": {"type": "string", "description": "测试名称"},
                 "layer": {"type": "string", "description": "测试层", "enum": ["unit", "integration", "e2e"], "default": "unit"},
                 "source_dir": {"type": "string", "description": "源码目录路径"},
                 "timeout": {"type": "integer", "description": "超时时间（秒），默认 60", "default": 60}
             }, "required": ["test_name"]},
             _handle_tdd_green)

        # 20. watch_unit_tests
        def _handle_watch_unit_tests(arguments):
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            test_name = arguments.get("test_name", "unknown")
            source_dir = arguments.get("source_dir")
            poll_interval = arguments.get("poll_interval", 1.0)
            debounce_delay = arguments.get("debounce_delay", 0.5)
            if source_dir:
                source_dir = str(self.config.resolve_path(source_dir))
            try:
                result = self.file_watcher.start_watch(test_name, source_dir, poll_interval, debounce_delay)
                if result.get('success'):
                    messages = [f"## 文件监控已启动\n\n时间：{timestamp}"]
                    messages.append(result.get('message', ''))
                    return {"content": [{"type": "text", "text": "\n".join(messages)}]}
                else:
                    return {"content": [{"type": "text", "text": f"[FAIL] {result.get('message', '启动失败')}"}], "isError": True}
            except Exception as e:
                return {"content": [{"type": "text", "text": f"[FAIL] watch_unit_tests 失败：{e}"}], "isError": True}

        _add("watch_unit_tests",
             "【M4 方向 F】启动文件监控模式 - 监控测试文件和源文件改动，自动重跑相关 unit 测试。后台线程运行，不阻塞 MCP。结果累积到日志文件。",
             {"type": "object", "properties": {
                 "test_name": {"type": "string", "description": "测试名称（如 'test_talent_config'）"},
                 "source_dir": {"type": "string", "description": "源码目录路径（默认 config.compile_source_dir）"},
                 "poll_interval": {"type": "number", "description": "轮询间隔（秒），默认 1.0", "default": 1.0},
                 "debounce_delay": {"type": "number", "description": "防抖延迟（秒），默认 0.5", "default": 0.5}
             }, "required": ["test_name"]},
             _handle_watch_unit_tests)

        # 21. stop_watch
        def _handle_stop_watch(arguments):
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            try:
                result = self.file_watcher.stop_watch()
                if result.get('success'):
                    messages = [f"## 文件监控已停止\n\n时间：{timestamp}"]
                    messages.append(result.get('message', ''))
                    return {"content": [{"type": "text", "text": "\n".join(messages)}]}
                else:
                    return {"content": [{"type": "text", "text": f"[FAIL] {result.get('message', '停止失败')}"}], "isError": True}
            except Exception as e:
                return {"content": [{"type": "text", "text": f"[FAIL] stop_watch 失败：{e}"}], "isError": True}

        _add("stop_watch",
             "【M4 方向 F】停止文件监控模式",
             {"type": "object", "properties": {}},
             _handle_stop_watch)

        # 22. get_watch_results
        def _handle_get_watch_results(arguments):
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            try:
                result = self.file_watcher.get_results()
                messages = [f"## 文件监控结果\n\n时间：{timestamp}"]
                messages.append(f"监控状态：{'运行中' if result.get('watching') else '已停止'}")
                messages.append(f"测试名称：{result.get('test_name', 'N/A')}")
                messages.append(f"总运行次数：{result.get('count', 0)}")
                if result.get('log_file'):
                    messages.append(f"日志文件：{result.get('log_file')}")
                results = result.get('results', [])
                if results:
                    messages.append("\n### 最近 10 次运行：")
                    for r in results[-10:]:
                        status = "✅" if r.get('success') else "❌"
                        messages.append(f"{status} {r.get('timestamp', '')} | "
                                       f"触发：{r.get('trigger', '')} | "
                                       f"结果：{'通过' if r.get('success') else r.get('failure_type', '失败')} | "
                                       f"耗时：{r.get('elapsed', 0):.2f}s")
                        if r.get('error'):
                            messages.append(f"   错误：{r.get('error')}")
                return {"content": [{"type": "text", "text": "\n".join(messages)}]}
            except Exception as e:
                return {"content": [{"type": "text", "text": f"[FAIL] get_watch_results 失败：{e}"}], "isError": True}

        _add("get_watch_results",
             "【M4 方向 F】获取文件监控累积的测试结果",
             {"type": "object", "properties": {}},
             _handle_get_watch_results)

        # 23. setup_environment
        def _handle_setup_environment(arguments):
            return self.environment_provisioner.setup(arguments)

        _add("setup_environment",
             "一键安装、体检或修复测试与 Named Pipe Agent 环境组件。支持 mode='repair'（默认，安装缺失并修复损坏组件）、'install'（仅装缺失）、'check'（只读体检）。涵盖六大项目组件（socket / http / nopause / agent_bridge / agent_lua / entry_hook）及可选 plugin_sync（同步插件缓存）。",
             {"type": "object", "properties": {
                 "source_dir": {"type": "string", "description": "目标项目根目录（如 'D:\\\\maps\\\\wzns'），默认取环境变量 WAR3_PROJECT_ROOT"},
                 "mode": {"type": "string", "enum": ["repair", "install", "check"], "default": "repair", "description": "执行模式：'repair'(默认，安装并覆盖修复所有组件) | 'install'(仅安装缺失文件) | 'check'(只读体检诊断)"},
                 "components": {
                     "type": "array",
                     "items": {"type": "string", "enum": ["socket", "http", "nopause", "agent_bridge", "agent_lua", "entry_hook", "plugin_sync"]},
                     "description": "要处理的组件列表，默认处理项目全部六大组件：socket(socket.dll) / http(flask) / nopause(nopause.asi) / agent_bridge(agent_bridge.dll) / agent_lua(15个Lua Agent及Oracle脚本) / entry_hook(-test on入口钩子)",
                     "default": ["socket", "http", "nopause", "agent_bridge", "agent_lua", "entry_hook"]
                 },
                 "war3_dir": {"type": "string", "description": "war3 安装目录（war3.exe 同目录，用于 nopause.asi / agent_bridge.asi 部署）"}
             }},
             _handle_setup_environment)

        # ── 24~31: LLM Agent 命名管道探索与步进控制工具集 ──────────────────────────

        def _call_pipe_tool(req_type: str, payload: dict = None, timeout_ms: int = 10000, pid: Optional[int] = None) -> dict:
            try:
                resp = self.pipe_client.request(req_type, payload, timeout_ms=timeout_ms, pid=pid)
                if resp.get("ok"):
                    return {"content": [{"type": "text", "text": self._format_pipe_value(resp.get("payload", {}))}]}
                else:
                    err = resp.get("error", {})
                    err_msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
                    return {"content": [{"type": "text", "text": f"[FAIL] {err_msg}"}], "isError": True}
            except Exception as e:
                return {"content": [{"type": "text", "text": f"[FAIL] 命名管道请求失败 ({req_type})：{e}"}], "isError": True}

        # 24. game_status
        def _handle_game_status(arguments):
            pid = arguments.get("pid")
            try:
                ping_resp = self.pipe_client.request("ping", {}, timeout_ms=3000, pid=pid)
                status_resp = self.pipe_client.request("status", {}, timeout_ms=3000, pid=pid)
                combined = {
                    "ping": ping_resp.get("payload", {}),
                    "runtime": status_resp.get("payload", {}) if status_resp.get("ok") else status_resp.get("error")
                }
                return {"content": [{"type": "text", "text": self._format_pipe_value(combined)}]}
            except Exception as e:
                return {"content": [{"type": "text", "text": f"[FAIL] game_status 失败：{e}"}], "isError": True}

        _add("game_status",
             "查询游戏内 Named Pipe Agent 桥接状态、插件版本、Lua 帧钟与当前冻结状态（step/free）。",
             {"type": "object", "properties": {
                 "pid": {"type": "integer", "description": "可选 War3.exe 进程 PID（多开时指定 \\\\.\\pipe\\war3_agent_<pid>）"}
             }},
             _handle_game_status)

        # 25. game_set_mode
        def _handle_game_set_mode(arguments):
            mode = arguments.get("mode", "free")
            pid = arguments.get("pid")
            try:
                resp = self.pipe_client.request("set_mode", {"mode": mode}, timeout_ms=5000, pid=pid)
                if mode == "free":
                    self.pipe_client.request("resume", {}, timeout_ms=5000, pid=pid)
                if resp.get("ok"):
                    return {"content": [{"type": "text", "text": self._format_pipe_value(resp.get("payload", {}))}]}
                return {"content": [{"type": "text", "text": f"[FAIL] {resp.get('error')}"}], "isError": True}
            except Exception as e:
                return {"content": [{"type": "text", "text": f"[FAIL] game_set_mode 失败：{e}"}], "isError": True}

        _add("game_set_mode",
             "切换游戏运行模式：'step'（步进冻结模式，每次 game_act 推进指定秒数后硬冻结主线程等待 LLM 决策）或 'free'（自由运行模式，立即解除冻结恢复正常游玩）。",
             {"type": "object", "properties": {
                 "mode": {"type": "string", "enum": ["step", "free"], "description": "'step' 步进冻结 | 'free' 自由运行"},
                 "pid": {"type": "integer", "description": "可选 War3.exe 进程 PID"}
             }, "required": ["mode"]},
             _handle_game_set_mode)

        # 26. game_observe
        def _handle_game_observe(arguments):
            detail = arguments.get("detail", "full")
            radius = arguments.get("radius", 1200)
            pid = arguments.get("pid")
            return _call_pipe_tool("observe", {"detail": detail, "radius": radius}, timeout_ms=5000, pid=pid)

        _add("game_observe",
             "获取游戏当前结构化视界快照（英雄属性/坐标/技能冷却/背包、半径内敌友单位、未选英雄时的候选英雄台、最近事件摘要）。",
             {"type": "object", "properties": {
                 "detail": {"type": "string", "enum": ["full", "brief"], "default": "full", "description": "'full' 完整快照（含技能与背包）| 'brief' 简要快照"},
                 "radius": {"type": "integer", "default": 1200, "description": "周围单位搜索半径，默认 1200"},
                 "pid": {"type": "integer", "description": "可选 War3.exe 进程 PID"}
             }},
             _handle_game_observe)

        # 27. game_act
        def _handle_game_act(arguments):
            actions = arguments.get("actions", [])
            run_seconds = float(arguments.get("run_seconds", 1.0))
            pid = arguments.get("pid")
            timeout_ms = int(run_seconds * 1000 + 10000)
            return _call_pipe_tool("act", {"actions": actions, "run_seconds": run_seconds}, timeout_ms=timeout_ms, pid=pid)

        _add("game_act",
             "下发一组语义动作（select_hero / move / attack / attack_move / cast / use_item / stop / chat / wait）并推进游戏 run_seconds 秒。在 step 模式下推进完成后自动冻结并返回期间事件与最新观测。",
             {"type": "object", "properties": {
                 "actions": {
                     "type": "array",
                     "description": "语义动作列表，每项为对象，如 {'op': 'select_hero', 'unit_id': 1048902} 或 {'op': 'attack', 'target_id': 1049100} 或 {'op': 'cast', 'slot': 'Q', 'target': 'point', 'x': 0, 'y': 0}",
                     "items": {"type": "object"}
                 },
                 "run_seconds": {"type": "number", "default": 1.0, "description": "动作下发后推进游戏的时长（秒，0.1 ~ 10.0），默认 1.0"},
                 "pid": {"type": "integer", "description": "可选 War3.exe 进程 PID"}
             }, "required": ["actions"]},
             _handle_game_act)

        # 28. game_events
        def _handle_game_events(arguments):
            since_seq = arguments.get("since_seq", 0)
            kinds = arguments.get("kinds")
            pid = arguments.get("pid")
            return _call_pipe_tool("events", {"since_seq": since_seq, "kinds": kinds}, timeout_ms=5000, pid=pid)

        _add("game_events",
             "增量拉取自指定 seq 以后的游戏事件流（伤害 unit_damaged、击杀 unit_died、五大 Oracle 违规 violation 等）。",
             {"type": "object", "properties": {
                 "since_seq": {"type": "integer", "default": 0, "description": "起始事件序号（不含），默认 0"},
                 "kinds": {"type": "array", "items": {"type": "string"}, "description": "按事件类型过滤（如 ['violation', 'unit_died']），可选"},
                 "pid": {"type": "integer", "description": "可选 War3.exe 进程 PID"}
             }},
             _handle_game_events)

        # 29. game_inspect
        def _handle_game_inspect(arguments):
            expr = arguments.get("expr", "")
            pid = arguments.get("pid")
            return _call_pipe_tool("inspect", {"expr": expr}, timeout_ms=5000, pid=pid)

        _add("game_inspect",
             "对游戏内 Lua 表达式求值并返回结构化 JSON 结果（与 inspect_game 共享命名管道通道）。",
             {"type": "object", "properties": {
                 "expr": {"type": "string", "description": "Lua 表达式"},
                 "pid": {"type": "integer", "description": "可选 War3.exe 进程 PID"}
             }, "required": ["expr"]},
             _handle_game_inspect)

        # 30. game_setup
        def _handle_game_setup(arguments):
            cmd = arguments.get("cmd")
            args = arguments.get("args", {})
            pid = arguments.get("pid")
            return _call_pipe_tool("setup", {"cmd": cmd, "args": args}, timeout_ms=5000, pid=pid)

        _add("game_setup",
             "预置游戏测试场景：支持 spawn_enemy（刷怪）、set_hero_level（设等级）、grant_item（发物品）、add_gold（加金币）、heal_full（满状态）、reset_cooldowns（刷CD）、teleport（传送）、kill_all_enemies（清场）、clear_ground_items（清掉落）。",
             {"type": "object", "properties": {
                 "cmd": {
                     "type": "string",
                     "enum": ["spawn_enemy", "set_hero_level", "grant_item", "add_gold", "heal_full", "reset_cooldowns", "teleport", "kill_all_enemies", "clear_ground_items"],
                     "description": "场景预置指令名"
                 },
                 "args": {"type": "object", "description": "指令参数字典，如 {'level': 10} 或 {'unit_type': 'hfoo', 'count': 3, 'dx': 300, 'dy': 0}"},
                 "pid": {"type": "integer", "description": "可选 War3.exe 进程 PID"}
             }, "required": ["cmd"]},
             _handle_game_setup)

        # 31. game_report_bug
        def _handle_game_report_bug(arguments):
            title = arguments.get("title", "未命名 Bug")
            severity = arguments.get("severity", "medium")
            steps = arguments.get("steps", [])
            evidence_seqs = arguments.get("evidence_seqs", [])
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            bugs_file = SERVER_DIR / "logs" / "agent_bugs.md"
            bugs_file.parent.mkdir(parents=True, exist_ok=True)
            lines = [
                f"## [{severity.upper()}] {title}",
                f"- **时间**: {timestamp}",
                f"- **证据事件序号**: {evidence_seqs}",
                "- **复现步骤**:",
            ]
            for idx, s in enumerate(steps, 1):
                lines.append(f"  {idx}. {s}")
            lines.append("\n---\n")
            with open(bugs_file, "a", encoding="utf-8") as f:
                f.write("\n".join(lines))
            return {"content": [{"type": "text", "text": f"[OK] Bug 已记录到 {bugs_file}\n标题：{title}"}]}

        _add("game_report_bug",
             "提交 LLM Agent 探索测试发现的 Bug 报告，持久化到插件 logs/agent_bugs.md。",
             {"type": "object", "properties": {
                 "title": {"type": "string", "description": "Bug 标题"},
                 "severity": {"type": "string", "enum": ["high", "medium", "low"], "default": "medium", "description": "严重程度"},
                 "steps": {"type": "array", "items": {"type": "string"}, "description": "复现步骤列表"},
                 "evidence_seqs": {"type": "array", "items": {"type": "integer"}, "description": "关联的违规/事件序号列表"}
             }, "required": ["title", "severity", "steps"]},
             _handle_game_report_bug)

        return registry

    async def handle_tool_call(self, tool_name: str, arguments: dict) -> dict:
        """查表分发。从 registry 查找 handler 并调用。未知工具走 fallback。"""
        spec = self._tool_registry.get(tool_name)
        if spec:
            return await spec.handler(arguments) if asyncio.iscoroutinefunction(spec.handler) else spec.handler(arguments)
        return {
            "content": [{"type": "text", "text": f"未知工具：{tool_name}"}],
            "isError": True
        }

    def _prepare_test_entry(self, test_name: str, test_file: str, source_dir: str) -> None:
        """准备测试入口文件（编译前调用）。"""
        self.test_entry_preparer.prepare(test_name, test_file, source_dir)

    def test_commit(self, test_name: str, test_file: str = None,
                    timeout: int = 60, platform: str = None, source_dir: str = None,
                    auto_screenshot_on_failure: bool = True) -> dict:
        """运行测试 - 编译 + 启动游戏 + 等待 HTTP 结果"""
        single = self.batch_runner.run_single_test(
            test_name, test_file, timeout, platform, source_dir, auto_screenshot_on_failure)

        success = single.get('success', False)
        message_lines = [f'测试完成：{test_name}', f'结果：{"通过" if success else "失败"}',
                         f'耗时：{single.get("elapsed", 0)}s']
        if single.get('failure_type'):
            message_lines.append(f'failure_type: {single.get("failure_type")}')
        if single.get('error'):
            message_lines.append(f'错误：{single.get("error")}')
        if single.get('screenshots'):
            message_lines.append(f'截图：{single.get("screenshots")}')

        return {
            'success': success,
            'message': '\n'.join(message_lines),
            'test_name': test_name,
            'result': single.get('result'),
            'result_file': single.get('result_file'),
            'elapsed': single.get('elapsed', 0),
            'failure_type': single.get('failure_type'),
            'game_errors': single.get('game_errors'),
            'crash_log': single.get('crash_log'),
            'screenshots': single.get('screenshots'),
            'progress': single.get('progress'),
            'logs': single.get('logs'),
        }

    def toggle_test(self, enabled: bool, source_dir: str) -> dict:
        """一键开关自动测试模式（写/删 _test_off.lua + 清测试残留 + 重编译）。"""
        test_dir = self.config.get_test_dir_path(self.config.resolve_path(source_dir))
        if test_dir is None:
            return {'success': False, 'enabled': enabled,
                    'action': '失败：source_dir 非有效 w2l 项目根',
                    'compile_error': f'source_dir 非有效 w2l 项目根（缺 w3x2lni/）: {source_dir}'}
        if enabled:
            self.test_mode_flag.enable(test_dir)
            action = '已开启：auto-test 模块恢复加载（跑测试请用 test_commit）'
            self.logger.info('[toggle_test] 开启：删除 _war3_tester/_test_off.lua')
        else:
            self.test_mode_flag.disable(test_dir)
            action = '已关闭：auto-test 模块不加载，手动游戏零干扰'
            self.logger.info('[toggle_test] 关闭：写入 _war3_tester/_test_off.lua，清理 _target_test.lua/run_auto_test.lua 残留')

        compile_result = self.executor.compile(source_dir)
        return {
            'success': compile_result.get('success', False),
            'enabled': enabled,
            'action': action,
            'compile_error': compile_result.get('error') if not compile_result.get('success') else None,
        }

    def _get_project_info(self, source_dir: str, max_depth: int = 3) -> str:
        return self.project_scaffolder.get_project_info(source_dir, max_depth)

    def _get_debug_output(self, limit: int = 50, level: str = "all", source_dir: str = None) -> str:
        return self.diagnostics_collector.get_debug_output(limit, level, source_dir)

    def _scaffold_test(self, module: str, layer: str, name: str = None, source_dir: str = None) -> dict:
        return self.project_scaffolder.scaffold_test(module, layer, name, source_dir)

    def _save_adapter_hook(self, name: str, content: str, source_dir: str = None) -> dict:
        return self.project_scaffolder.save_adapter_hook(name, content, source_dir)

    def _generate_test_skeleton(self, module: str, layer: str, test_name: str) -> str:
        return self.project_scaffolder.generate_test_skeleton(module, layer, test_name)

    def _tdd_red(self, test_name: str, layer: str, source_dir: str = None, timeout: int = 60) -> dict:
        if layer == 'unit':
            result = self.desktop_runner.run_unit_test(test_name, source_dir, timeout)
        else:
            result = self.test_commit(test_name, None, timeout, None, source_dir, False)

        elapsed = result.get('elapsed', 0)
        failure_type = result.get('failure_type')
        success = result.get('success', False)

        if success:
            return {
                'status': 'green',
                'failure_type': None,
                'reason': '测试通过了，但 Red 阶段预期应该失败。请检查测试是否真的在验证未实现的功能',
                'error': None,
                'elapsed': elapsed,
            }

        if failure_type == 'assertion':
            return {
                'status': 'red_valid',
                'failure_type': failure_type,
                'reason': '测试预期失败（assertion failure），Red 成立：测试逻辑正确，功能未实现',
                'error': result.get('error'),
                'elapsed': elapsed,
            }
        else:
            return {
                'status': 'red_invalid',
                'failure_type': failure_type,
                'reason': f'测试失败原因不是 assertion failure，而是 {failure_type}。'
                          f'runtime_error 可能是测试写错（调用 nil 函数、数组越界等），'
                          f'env_error/compile_error 是环境问题。请检查测试代码',
                'error': result.get('error'),
                'elapsed': elapsed,
            }

    def _tdd_green(self, test_name: str, layer: str, source_dir: str = None, timeout: int = 60) -> dict:
        if layer == 'unit':
            result = self.desktop_runner.run_unit_test(test_name, source_dir, timeout)
        else:
            result = self.test_commit(test_name, None, timeout, None, source_dir, True)
        return result

    async def handle_resource_read(self, uri: str) -> dict:
        """处理资源读取"""
        if uri == "war3://logs/compile":
            log_path = self.project_root / "logs" / "compile.log"
            if log_path.exists():
                content = log_path.read_text(encoding="utf-8", errors="ignore")[-10000:]
                return {"contents": [{"uri": uri, "text": content}]}
            return {"contents": [{"uri": uri, "text": "日志文件不存在"}]}

        elif uri == "war3://logs/game":
            log_path = self.config.get_war3_log_file_path(player_id=1)
            if log_path and log_path.exists():
                content = log_path.read_text(encoding="utf-8", errors="ignore")[-10000:]
                return {"contents": [{"uri": uri, "text": content}]}
            return {"contents": [{"uri": uri, "text": "日志文件不存在"}]}

        elif uri == "war3://logs/game/list":
            log_dir = self.config.war3_log_dir
            if log_dir and log_dir.exists():
                log_files = sorted(log_dir.glob("玩家*.log"))
                file_list = "\n".join([f.name for f in log_files[-20:]])
                return {"contents": [{"uri": uri, "text": f"最近的游戏日志文件:\n{file_list}"}]}
            return {"contents": [{"uri": uri, "text": "日志目录不存在或为空"}]}

        return {"contents": [{"uri": uri, "text": "未知资源"}]}


async def run_server():
    """运行 MCP 服务器（stdio JSON-RPC 主循环）"""
    server = War3TesterMCP()

    if not server.executor.check_connectivity():
        print(file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        if server.config.is_wsl:
            print("[ERROR] 无法连接到 Windows 代理", file=sys.stderr)
            print("请确保 Windows 代理已启动:", file=sys.stderr)
            print("  python win_proxy.py start", file=sys.stderr)
        else:
            print("[ERROR] 本地执行器不可用", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        return

    server.logger.info("执行器连接检测通过（全链路采用 Windows 命名管道 \\\\.\\pipe\\war3_agent，已废除 8766 HTTP 端口监听）")
    server.logger.info("服务器已初始化")
    print("[OK] War3 Tester MCP Server 已启动 (Named Pipe Mode)", file=sys.stderr)

    def _cleanup_on_exit():
        """退出清理：关命名管道 + 若本实例曾自动拉起测试游戏进程则清理"""
        try:
            server.pipe_client.close()
        except Exception:
            pass

        if getattr(server.batch_runner, "launched_war3", False) and (server.config.is_windows or server.config.is_wsl):
            for proc_name in server.config.war3_process_names:
                try:
                    subprocess.run(
                        ['taskkill', '/IM', proc_name, '/F'],
                        capture_output=True,
                        timeout=5
                    )
                except Exception:
                    pass

    atexit.register(_cleanup_on_exit)

    def _on_sigterm(signum, frame):
        server.logger.info("收到 SIGTERM，执行退出清理")
        _cleanup_on_exit()
        sys.exit(0)
    signal.signal(signal.SIGTERM, _on_sigterm)

    try:
        while True:
            try:
                line = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
                if not line:
                    break

                line = line.strip()
                if not line:
                    continue

                request = json.loads(line)
                method = request.get("method")
                params = request.get("params", {})
                request_id = request.get("id")

                if method == "initialize":
                    response = {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {
                            "protocolVersion": "2024-11-05",
                            "capabilities": {
                                "tools": {"listChanged": False},
                                "resources": {"subscribe": False, "listChanged": False}
                            },
                            "serverInfo": {
                                "name": "war3-tester",
                                "version": "0.21.0"
                            }
                        }
                    }

                elif method == "tools/list":
                    response = {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {"tools": server.capabilities["tools"]}
                    }

                elif method == "tools/call":
                    tool_name = params.get("name")
                    arguments = params.get("arguments", {})
                    result = await server.handle_tool_call(tool_name, arguments)
                    response = {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": result
                    }

                elif method == "resources/list":
                    response = {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {"resources": server.capabilities["resources"]}
                    }

                elif method == "resources/read":
                    uri = params.get("uri")
                    result = await server.handle_resource_read(uri)
                    response = {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": result
                    }

                elif method == "notifications/initialized":
                    continue

                else:
                    response = {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {
                            "code": -32601,
                            "message": f"Method not found: {method}"
                        }
                    }

                print(json.dumps(response, ensure_ascii=False), flush=True)

            except json.JSONDecodeError as e:
                server.logger.error(f"JSON 解析错误：{str(e)}")
                error_response = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": f"Parse error: {str(e)}"}
                }
                print(json.dumps(error_response, ensure_ascii=False), flush=True)
            except Exception as e:
                server.logger.error(f"内部错误：{str(e)}", exc_info=True)
                error_response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32603, "message": f"Internal error: {str(e)}"}
                }
                print(json.dumps(error_response, ensure_ascii=False), flush=True)
    finally:
        _cleanup_on_exit()


if __name__ == "__main__":
    asyncio.run(run_server())
