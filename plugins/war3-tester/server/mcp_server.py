#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
War3 Tester 通用 MCP Server

提供地图编译、游戏测试的 MCP 工具接口（stdio JSON-RPC）。

工具：
- compile_map / compile_only: 编译地图
- run_game / launch_only: 启动游戏
- stop_game: 停止游戏
- send_key: 发送键盘事件
- take_screenshot: 截取游戏窗口
- test_commit: 运行测试（编译+启动+等待结果）
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
# v0.15.0: 三 module（消除 mcp_server↔batch_runner 循环依赖）
from test_mode_flag import TestModeFlag
from test_entry_preparer import TestEntryPreparer
from diagnostics_collector import DiagnosticsCollector

# v0.19.5(候选④): 模块级全局已废弃,四对象(config/executor/store/http_receiver)改由
# War3TesterMCP.__init__ 构造并存 self。import mcp_server 不触发构造(__init__ 在实例化时调),
# 保留"消除 import 副作用"(v0.19.0 目标)。


class ToolSpec:
    """工具注册条目：绑定 schema 与 handler 到同一条目（单源注册）。

    v0.17.0: 消除 schema 与 handler 双源注册。capabilities["tools"] 由 registry 单源生成，
    handle_tool_call 改为查表分发。新增工具只需在 _register_tools() 添加一个 ToolSpec。
    """
    __slots__ = ('name', 'schema', 'handler')

    def __init__(self, name: str, schema: dict, handler):
        self.name = name
        self.schema = schema
        self.handler = handler


class War3TesterMCP:
    """War3 Tester MCP Server"""

    def __init__(self):
        # v0.19.5(候选④): 构造四全局(废弃 init_runtime/模块级全局),存 self。
        # import mcp_server 不触发构造(__init__ 在 War3TesterMCP() 时调),保留消除 import 副作用。
        _war3_project_root = os.getenv('WAR3_PROJECT_ROOT')
        self.config = Config(project_root=Path(_war3_project_root) if _war3_project_root else None)
        self.logger = setup_logger('war3-mcp')
        self.executor = create_executor(self.config)
        self.store = TestStateStore()  # v0.14.0: 跨线程状态 owner
        self.http_receiver = HTTPReceiver(host=self.config.http_host, port=self.config.http_port, store=self.store)
        self.project_root = self.config.project_root

        # v0.15.0: 三 module（消除 mcp_server↔batch_runner 循环依赖）
        self.test_mode_flag = TestModeFlag(logger=self.logger)
        self.diagnostics_collector = DiagnosticsCollector(self.store, self.config, logger=self.logger)
        self.test_entry_preparer = TestEntryPreparer(
            self.test_mode_flag, SERVER_DIR, self.config, logger=self.logger
        )

        # v2: 批量测试编排器（注入 store + 三 module，与 http_receiver 共享状态访问）
        self.batch_runner = TestBatchRunner(
            self.config, self.executor, self.http_receiver,
            test_mode_flag=self.test_mode_flag,
            test_entry_preparer=self.test_entry_preparer,
            diagnostics_collector=self.diagnostics_collector,
            store=self.store
        )
        # M2: 桌面纯逻辑单测运行器（不启动游戏，秒级反馈）
        self.desktop_runner = DesktopRunner(self.config, self.executor)
        # M4: 文件监控器（watch 模式）
        self.file_watcher = FileWatcher(self.desktop_runner, self.config)

        # v0.17.0: 工具注册表（单源）。capabilities["tools"] 与 handle_tool_call 都从这里派生。
        self._tool_registry = self._register_tools()

        # MCP 能力声明（tools 由 registry 单源生成，resources 仍手写）
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

    def _register_tools(self) -> dict:
        """v0.17.0: 注册所有工具到 registry（单源）。

        每个 ToolSpec 绑定 schema 与 handler。capabilities["tools"] 由此派生，
        handle_tool_call 改为查表分发。新增工具只需在此添加一个 ToolSpec。

        Returns:
            dict: name -> ToolSpec
        """
        registry = {}

        def _add(name, description, input_schema, handler):
            schema = {
                "name": name,
                "description": description,
                "inputSchema": input_schema
            }
            registry[name] = ToolSpec(name, schema, handler)

        # 1. compile_map / compile_only（合并：同一 handler 服务两个 name）
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

        # 5. launch_only / run_game（合并：同一 handler，通过 tool_name 区分 inject_inspect 行为）
        def _handle_launch_or_run(tool_name, arguments):
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            map_path = arguments.get("map_path", str(self.config.compile_output_path / self.config.compile_output_name))
            platform = arguments.get("platform")
            inject_inspect = arguments.get("inject_inspect", True) if tool_name == "run_game" else False
            if not platform:
                run_mode, _ = self.config.get_run_mode_with_source()
                platform = run_mode
            if inject_inspect:
                # v0.19.3: 收敛 source_dir 归一化(×3 复用)
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
                self.logger.info(f"[run_game] 编译成功，准备启动游戏（inject_inspect 已注入）")
            result = self.executor.run_game(map_path, platform)
            if result.get("success"):
                msg = f"[OK] 游戏已启动\n\n{result.get('message', '')}"
                if inject_inspect:
                    msg += "\n\n（inspect_handler 已注入，可使用 inspect_game 运行时查询）"
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
                 "inject_inspect": {"type": "boolean", "description": "是否注入运行时查询处理器（inspect_handler）。True 时自动注入 inspect_handler + 写 inspect-only run_auto_test + 删 _test_off + 编译，让 inspect_game 在 run_game 启动的游戏里可用。默认 True", "default": True},
                 "source_dir": {"type": "string", "description": "inject_inspect 启用时，地图源码目录（如 D:\\maps\\wzns），默认 config.compile_source_dir"}
             }},
             lambda args: _handle_launch_or_run("run_game", args))

        # 6. stop_game
        def _handle_stop_game(arguments):
            result = self.executor.stop_game()
            if result.get("success"):
                return {"content": [{"type": "text", "text": f"[OK] {result.get('message', '游戏已关闭')}"}]}
            else:
                return {"content": [{"type": "text", "text": f"[FAIL] {result.get('error', '游戏关闭失败')}"}], "isError": True}

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
            stop_result = self.executor.stop_game()
            self.http_receiver.stop()
            return {"content": [{"type": "text", "text": f"[OK] 清理完成\n\n{stop_result.get('message', '')}"}]}

        _add("cleanup_all",
             "清理所有资源 - 关闭 war3.exe 进程和 HTTP 服务器",
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
                             f"WSL 路径：{result.get('path_wsl', '')}\nWindows 路径：{result.get('path', '')}")
                if getattr(config, 'take_screenshot_auto_analyze', True):
                    png_path = result.get('path') or result.get('path_wsl')
                    try:
                        analysis = self.analyze_screenshot(png_path)
                        base_text += f"\n\n--- VLM 判读 ---\n{analysis}"
                    except Exception as e:
                        base_text += (f"\n\n--- VLM 判读失败(不影响截图使用) ---\n{e}"
                                      f"\n(关闭自动判读:config.json 设 take_screenshot_auto_analyze=false)")
                return {"content": [{"type": "text", "text": base_text}]}
            else:
                return {"content": [{"type": "text", "text": f"[FAIL] 截图失败\n\n{result.get('error', '未知错误')}"}], "isError": True}

        _add("take_screenshot",
             "截取游戏窗口截图。成功后默认自动调 VLM(analyze_screenshot)判读画面,返回含判读文本;VLM 未配或判读失败则 graceful 仅返回路径不阻塞。config.json 的 take_screenshot_auto_analyze=false 可关闭自动判读。",
             {"type": "object", "properties": {
                 "test_name": {"type": "string", "description": "测试名称，用于组织截图文件"},
                 "filename": {"type": "string", "description": "截图文件名（可选）"},
                 "window_title": {"type": "string", "description": "窗口标题关键词（可选）"}
             }, "required": ["test_name"]},
             _handle_take_screenshot)

        # 10. analyze_screenshot
        def _handle_analyze_screenshot(arguments):
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            png_path = arguments.get("png_path")
            prompt = arguments.get("prompt", "")
            if not png_path:
                return {"content": [{"type": "text", "text": "[FAIL] 缺少 png_path 参数"}], "isError": True}
            try:
                analysis_text = self.analyze_screenshot(png_path, prompt)
                return {"content": [{"type": "text", "text": f"[OK] 截图分析完成\n\n时间：{timestamp}\n\n{analysis_text}"}]}
            except Exception as e:
                return {"content": [{"type": "text", "text": f"[FAIL] 截图分析失败\n\n{e}"}], "isError": True}

        _add("analyze_screenshot",
             "用多模态视觉模型（VLM）分析游戏截图，返回画面判读文本。需要环境变量 VLM_MODEL/VLM_BASE_URL/VLM_API_KEY",
             {"type": "object", "properties": {
                 "png_path": {"type": "string", "description": "截图 PNG 文件路径（Windows 绝对路径或相对路径）"},
                 "prompt": {"type": "string", "description": "自定义分析提示词（可选，默认判读画面状态/UI元素/是否卡对话框/可见数值）"}
             }, "required": ["png_path"]},
             _handle_analyze_screenshot)

        # 11. send_key
        def _handle_send_key(arguments):
            key = arguments.get("key", "enter")
            result = self.executor.send_key(key)
            if result.get("success"):
                return {"content": [{"type": "text", "text": f"[OK] 已发送 {key} 键\n\n{result.get('message', '')}"}]}
            else:
                return {"content": [{"type": "text", "text": f"[FAIL] 发送按键失败\n\n{result.get('error', '未知错误')}"}], "isError": True}

        _add("send_key",
             "向 War3 游戏窗口发送键盘事件。支持单键（'enter', 'a', 'f1', 'up' 等）和组合键（'ctrl+c', 'shift+a', 'alt+f4', 'ctrl+shift+s' 等，+ 分隔修饰键与主键）。完整 VK 表：字母 A-Z、数字 0-9、F1-F12、方向键、修饰键(Shift/Ctrl/Alt)、Tab/Backspace/Delete/Home/End/PageUp/PageDown 等。",
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
             "地图/脚本结构分析 - 扫描项目地图脚本目录，返回结构化分析：目录树概要、各模块文件计数（技能/Buff/物品/任务/副本/系统/entities/components 等子目录）、代码行数统计、关键入口文件（init.lua 等）。纯静态分析，只读文件系统，不启动游戏。",
             {"type": "object", "properties": {
                 "source_dir": {"type": "string", "description": "源码目录路径，默认 config.compile_source_dir"},
                 "max_depth": {"type": "integer", "description": "目录树扫描最大深度，默认 3", "default": 3}
             }},
             _handle_get_project_info)

        # 14. inspect_game
        def _handle_inspect_game(arguments):
            expr = arguments.get("expr")
            timeout = arguments.get("timeout", 5)
            if not expr:
                return {"content": [{"type": "text", "text": "[FAIL] 缺少 expr 参数"}], "isError": True}
            try:
                query_id = self.store.submit_inspect(expr)
            except Exception as e:
                return {"content": [{"type": "text", "text": f"[FAIL] 加入查询队列失败：{e}"}], "isError": True}
            result = self.store.take_inspect(query_id, timeout=timeout)
            if result:
                if "error" in result:
                    return {"content": [{"type": "text", "text": f"[FAIL] 游戏端执行错误：{result['error']}"}], "isError": True}
                else:
                    value = result.get("value", "")
                    return {"content": [{"type": "text", "text": f"[OK] 查询结果：\n{value}"}]}
            return {"content": [{"type": "text", "text": f"[FAIL] 超时（{timeout}秒）：游戏端未回传结果"}], "isError": True}

        _add("inspect_game",
             "运行时对象检查 - 在游戏内执行一段 Lua 表达式并返回结果。AI 调用后，MCP 将查询放入 pending 队列，游戏端轮询拉取执行并回传结果。用于运行时调试、查看单位属性、检查游戏状态等。",
             {"type": "object", "properties": {
                 "expr": {"type": "string", "description": "要在游戏内执行的 Lua 表达式（如 'UnitObj.all_count()' 或 'Player(1):getGold()'）"},
                 "timeout": {"type": "integer", "description": "等待游戏端回传结果的超时时间（秒），默认 5", "default": 5}
             }, "required": ["expr"]},
             _handle_inspect_game)

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
             "调试输出捕获 - 聚合游戏的调试输出：① War3 游戏日志（按 config.war3_log_dir 定位）② HTTP /error 端点缓存的运行时错误（http_receiver 内存缓冲）。按 error/warning 分级返回最近 N 条。纯读取，不启动游戏。",
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
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            source_dir = arguments.get("source_dir")
            components = arguments.get("components", ["socket", "http", "nopause"])
            war3_dir = arguments.get("war3_dir")
            if source_dir:
                project_root = Path(source_dir)
            elif self.config.project_root:
                project_root = self.config.project_root
            else:
                project_root = None
            if not war3_dir and self.config.war3_log_dir:
                try:
                    inferred_war3_dir = Path(self.config.war3_log_dir).parent
                    if inferred_war3_dir.exists():
                        war3_dir = str(inferred_war3_dir)
                except Exception:
                    pass
            plugin_root = SERVER_DIR.parent
            results = []
            if "socket" in components:
                try:
                    if not project_root:
                        results.append({"component": "socket", "status": "failed", "message": "未指定 source_dir 且 WAR3_PROJECT_ROOT 未设置"})
                    else:
                        socket_src_dir = plugin_root / "bin" / "socket"
                        socket_dst_dir = project_root / "map"
                        if not socket_src_dir.exists():
                            results.append({"component": "socket", "status": "failed", "message": f"插件 bin/socket 目录不存在：{socket_src_dir}"})
                        else:
                            socket_dst_dir.mkdir(parents=True, exist_ok=True)
                            copied_files = []
                            for dll_name in ["socket.dll", "libwinpthread-1.dll"]:
                                src = socket_src_dir / dll_name
                                dst = socket_dst_dir / dll_name
                                if src.exists():
                                    shutil.copy2(src, dst)
                                    copied_files.append(str(dst))
                            if copied_files:
                                results.append({"component": "socket", "status": "success", "message": f"已拷贝 {len(copied_files)} 个文件到 {socket_dst_dir}", "files": copied_files})
                            else:
                                results.append({"component": "socket", "status": "failed", "message": "未找到 socket.dll 或 libwinpthread-1.dll"})
                except Exception as e:
                    results.append({"component": "socket", "status": "failed", "message": f"部署失败：{e}"})
            if "http" in components:
                try:
                    proc = subprocess.run([sys.executable, "-m", "pip", "install", "flask", "werkzeug"], capture_output=True, text=True, timeout=120)
                    if proc.returncode == 0:
                        results.append({"component": "http", "status": "success", "message": "flask + werkzeug 已安装（或已是最新）"})
                    else:
                        results.append({"component": "http", "status": "failed", "message": f"pip install 失败：{proc.stderr}"})
                except subprocess.TimeoutExpired:
                    results.append({"component": "http", "status": "failed", "message": "pip install 超时（120秒）"})
                except Exception as e:
                    results.append({"component": "http", "status": "failed", "message": f"pip install 异常：{e}"})
            if "nopause" in components:
                try:
                    if not war3_dir:
                        results.append({"component": "nopause", "status": "skipped", "message": "未指定 war3_dir 且无法从 config.war3_log_dir 反推，请传参 war3_dir"})
                    else:
                        nopause_src = plugin_root / "bin" / "nopause.asi"
                        nopause_dst = Path(war3_dir) / "nopause.asi"
                        if not nopause_src.exists():
                            results.append({"component": "nopause", "status": "failed", "message": f"插件 bin/nopause.asi 不存在：{nopause_src}"})
                        else:
                            shutil.copy2(nopause_src, nopause_dst)
                            results.append({"component": "nopause", "status": "success", "message": f"已拷贝 nopause.asi 到 {nopause_dst}"})
                except Exception as e:
                    results.append({"component": "nopause", "status": "failed", "message": f"部署失败：{e}"})
            messages = [f"## 环境部署结果\n\n时间：{timestamp}"]
            if project_root:
                messages.append(f"项目根目录：{project_root}")
            if war3_dir:
                messages.append(f"War3 安装目录：{war3_dir}")
            messages.append("")
            success_count = sum(1 for r in results if r.get("status") == "success")
            failed_count = sum(1 for r in results if r.get("status") == "failed")
            skipped_count = sum(1 for r in results if r.get("status") == "skipped")
            messages.append(f"总计：{len(results)} 个组件（成功 {success_count} / 失败 {failed_count} / 跳过 {skipped_count}）\n")
            for r in results:
                status_icon = "✅" if r.get("status") == "success" else ("❌" if r.get("status") == "failed" else "⚠️")
                messages.append(f"{status_icon} {r.get('component')}: {r.get('status')}")
                messages.append(f"   {r.get('message')}")
                if r.get("files"):
                    for f in r["files"]:
                        messages.append(f"   - {f}")
                messages.append("")
            is_error = failed_count > 0
            return {"content": [{"type": "text", "text": "\n".join(messages)}], "isError": is_error}

        _add("setup_environment",
             "一键部署测试环境组件（socket.dll/nopause.asi/Flask 依赖）。游戏端靠 socket.dll 发 HTTP 回传测试结果，靠 nopause.asi 防失焦暂停，MCP 端靠 Flask 接收。缺装任一组件会导致 test_commit 静默超时。",
             {"type": "object", "properties": {
                 "source_dir": {"type": "string", "description": "目标项目根目录，默认取环境变量 WAR3_PROJECT_ROOT"},
                 "components": {"type": "array", "items": {"type": "string", "enum": ["socket", "http", "nopause"]}, "description": "要安装的组件列表，默认三个全装：socket（拷 socket.dll 到项目 map/）、http（pip install flask werkzeug）、nopause（拷 nopause.asi 到 war3 安装目录）", "default": ["socket", "http", "nopause"]},
                 "war3_dir": {"type": "string", "description": "war3 安装目录（war3.exe 同目录，用于 nopause 部署）。默认从 config.war3_log_dir 反推；反推不到则跳过 nopause 并提示传参"}
             }},
             _handle_setup_environment)

        return registry

    async def handle_tool_call(self, tool_name: str, arguments: dict) -> dict:
        """v0.17.0: 查表分发。从 registry 查找 handler 并调用。未知工具走 fallback。"""
        spec = self._tool_registry.get(tool_name)
        if spec:
            return await spec.handler(arguments) if asyncio.iscoroutinefunction(spec.handler) else spec.handler(arguments)
        # fallback: 未知工具
        return {
            "content": [{"type": "text", "text": f"未知工具：{tool_name}"}],
            "isError": True
        }

    def _prepare_test_entry(self, test_name: str, test_file: str, source_dir: str) -> None:
        """
        准备测试入口文件（编译前调用）。

        v0.15.0: 委托 TestEntryPreparer.prepare（消除反向依赖，保留方法签名供内部调用）

        Args:
            test_name: 测试名称
            test_file: 测试文件名（如 'test_skill_a00d.lua'）
            source_dir: 源码目录
        """
        # v0.15.0: 委托 test_entry_preparer（内部已含 _get_war3_tester_dir/_inject_war3_tester_assets/删_test_off）
        self.test_entry_preparer.prepare(test_name, test_file, source_dir)

    def test_commit(self, test_name: str, test_file: str = None,
                    timeout: int = 60, platform: str = None, source_dir: str = None,
                    auto_screenshot_on_failure: bool = True) -> dict:
        """运行测试 - 编译 + 启动游戏 + 等待 HTTP 结果

        v2 增强（设计文档 4.1）：委托 batch_runner.run_single_test，与 run_test_batch
        共享单测执行核心，自动获得：
        - 进程存活监控（游戏崩溃 → failure_type='crash'）
        - failure_type 分类（compile_error/crash/timeout/assertion/runtime_error/env_error）
        - 失败按类型触发截图（仅 crash/timeout/unknown）
        - 结果附加 game_errors / progress / logs / crash_log

        Args:
            test_name: 测试名称
            test_file: 测试文件名
            timeout: 超时时间（秒）
            platform: 游戏平台
            source_dir: 源码目录
            auto_screenshot_on_failure: 失败时自动截图
        """
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
            # v2 字段
            'failure_type': single.get('failure_type'),
            'game_errors': single.get('game_errors'),
            'crash_log': single.get('crash_log'),
            'screenshots': single.get('screenshots'),
            'progress': single.get('progress'),
            'logs': single.get('logs'),
        }

    def toggle_test(self, enabled: bool, source_dir: str) -> dict:
        """一键开关自动测试模式（写/删 _test_off.lua + 清测试残留 + 重编译）。

        【M1 归拢】_test_off.lua / _target_test.lua / run_auto_test.lua 均移入 _war3_tester/。

        关闭(false)：写入 _war3_tester/_test_off.lua（内容 return true），auto-test/init.lua 顶部
            pcall(require) 命中后整个模块 early-return → 手动游戏零干扰。
            同时删除 _war3_tester/_target_test.lua / run_auto_test.lua 残留，避免旧测试入口意外激活。
        开启(true)：删除 _war3_tester/_test_off.lua，恢复 auto-test 模块默认加载。
        注：跑测试本身仍需 test_commit（它写入 _war3_tester/_target_test.lua，并会自动删除 _test_off.lua）。
        """
        test_dir = self.config.get_test_dir_path(self.config.resolve_path(source_dir))
        if test_dir is None:
            return {'success': False, 'enabled': enabled,
                    'action': '失败：source_dir 非有效 w2l 项目根',
                    'compile_error': f'source_dir 非有效 w2l 项目根（缺 w3x2lni/）: {source_dir}'}
        # v0.15.0: 委托 test_mode_flag（内部已含 _test_off 写/删 + legacy 清理 + _target_test/run_auto_test 残留清理）
        if enabled:
            self.test_mode_flag.enable(test_dir)
            action = '已开启：auto-test 模块恢复加载（跑测试请用 test_commit）'
            self.logger.info('[toggle_test] 开启：删除 _war3_tester/_test_off.lua')
        else:
            self.test_mode_flag.disable(test_dir)
            action = '已关闭：auto-test 模块不加载，手动游戏零干扰'
            self.logger.info('[toggle_test] 关闭：写入 _war3_tester/_test_off.lua，清理 _target_test.lua/run_auto_test.lua 残留')

        # 重编译让 .w3x 反映标志文件变更
        compile_result = self.executor.compile(source_dir)
        return {
            'success': compile_result.get('success', False),
            'enabled': enabled,
            'action': action,
            'compile_error': compile_result.get('error') if not compile_result.get('success') else None,
        }

    def analyze_screenshot(self, png_path: str, prompt: str = "") -> str:
        """调用多模态视觉模型（VLM）分析截图，返回文本结果。

        v0.15.0: 委托 diagnostics_collector（thin delegate）
        """
        return self.diagnostics_collector.analyze_screenshot(png_path, prompt)

    def _get_project_info(self, source_dir: str, max_depth: int = 3) -> str:
        """
        扫描项目地图脚本目录，返回结构化分析（纯静态，只读）。

        分析内容：
        1. 目录树概要（限 max_depth 层）
        2. 各模块子目录文件计数（按约定子目录名识别）
        3. 代码行数统计（按文件扩展名分组）
        4. 关键入口文件列表（init.lua 等）

        Args:
            source_dir: 源码根目录（通常为 config.compile_source_dir）
            max_depth: 目录树扫描最大深度

        Returns:
            格式化的分析文本
        """
        root = Path(source_dir)
        if not root.exists() or not root.is_dir():
            return f"[WARN] 源码目录不存在或不是目录：{source_dir}"

        # 跳过的噪声目录
        skip_dirs = {
            '.git', 'node_modules', '__pycache__', '.codegraph',
            'logs', 'archive', '.idea', '.vs', 'dist', 'build',
            '.claude', 'w3x2lni',
        }

        # 关注的模块子目录（War3 ECS 项目约定）
        module_dirs = {
            '技能', 'Buffs', '物品', '任务', '副本', 'systems', 'entities',
            'components', 'model', 'data', 'NPC', '单位', '进攻波', 'AI',
            'states', 'logic', 'types', 'core', '界面',
        }

        # 关键入口文件名
        entry_files = {'init.lua', 'main.lua', 'app.lua', 'config.lua', 'bootstrap.lua'}

        # === 1. 目录树 + 2. 模块计数 + 3. 行数统计 + 4. 入口文件 ===
        dir_tree_lines = []
        module_counts = {}  # module_name -> file_count
        ext_line_counts = {}  # ext -> total_lines
        ext_file_counts = {}  # ext -> file_count
        entry_file_list = []  # list of relative paths
        total_files = 0
        total_lines = 0

        def scan_dir(current: Path, depth: int, prefix: str):
            """递归扫描目录"""
            nonlocal total_files, total_lines
            if depth > max_depth:
                return

            try:
                entries = sorted(current.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
            except (PermissionError, OSError):
                return

            for entry in entries:
                if entry.name.startswith('.'):
                    continue
                if entry.is_dir():
                    if entry.name in skip_dirs:
                        continue
                    if depth < max_depth:
                        dir_tree_lines.append(f"{prefix}📁 {entry.name}/")
                        scan_dir(entry, depth + 1, prefix + "  ")
                    else:
                        # 最深层只列目录名，不递归
                        dir_tree_lines.append(f"{prefix}📁 {entry.name}/")
                elif entry.is_file():
                    total_files += 1
                    rel = str(entry.relative_to(root))
                    ext = entry.suffix.lower()
                    if ext:
                        ext_file_counts[ext] = ext_file_counts.get(ext, 0) + 1
                        try:
                            line_count = sum(1 for _ in entry.open('r', encoding='utf-8', errors='ignore'))
                        except (OSError, PermissionError):
                            line_count = 0
                        ext_line_counts[ext] = ext_line_counts.get(ext, 0) + line_count
                        total_lines += line_count

                    # 模块目录归属统计（只看直接子目录）
                    parts = entry.relative_to(root).parts
                    if len(parts) >= 2 and parts[0] in module_dirs:
                        mod = parts[0]
                        module_counts[mod] = module_counts.get(mod, 0) + 1

                    # 入口文件
                    if entry.name in entry_files:
                        entry_file_list.append(rel)

        dir_tree_lines.append(f"📁 {root.name}/")
        scan_dir(root, 1, "  ")

        # === 组装输出 ===
        out = []
        out.append(f"## 项目结构分析")
        out.append(f"扫描目录：{root}")
        out.append(f"扫描时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        out.append(f"总文件数：{total_files}  总代码行数：{total_lines}")
        out.append("")

        # 模块计数
        out.append("### 模块文件计数")
        if module_counts:
            for mod in sorted(module_counts.keys()):
                out.append(f"  {mod}: {module_counts[mod]} 个文件")
        else:
            out.append("  （未发现约定的模块子目录）")
        out.append("")

        # 行数按扩展名
        out.append("### 代码行数统计（按扩展名）")
        if ext_line_counts:
            for ext in sorted(ext_line_counts.keys(), key=lambda e: -ext_line_counts.get(e, 0)):
                out.append(f"  {ext}: {ext_file_counts.get(ext, 0)} 个文件, {ext_line_counts[ext]} 行")
        else:
            out.append("  （无代码文件）")
        out.append("")

        # 入口文件
        out.append("### 关键入口文件")
        if entry_file_list:
            for ef in sorted(entry_file_list):
                out.append(f"  {ef}")
        else:
            out.append("  （未发现 init.lua / main.lua 等入口文件）")
        out.append("")

        # 目录树（截断防爆）
        out.append(f"### 目录树（max_depth={max_depth}）")
        max_tree_lines = 200
        if len(dir_tree_lines) > max_tree_lines:
            out.extend(dir_tree_lines[:max_tree_lines])
            out.append(f"  ... 已截断（共 {len(dir_tree_lines)} 行，显示前 {max_tree_lines} 行）")
        else:
            out.extend(dir_tree_lines)

        return "\n".join(out)

    def _get_debug_output(self, limit: int = 50, level: str = "all", source_dir: str = None) -> str:
        """
        聚合游戏调试输出（纯读取，不启动游戏）。

        v0.15.0: 委托 diagnostics_collector（thin delegate）
        """
        return self.diagnostics_collector.get_debug_output(limit, level, source_dir)

    def _scaffold_test(self, module: str, layer: str, name: str = None, source_dir: str = None) -> dict:
        """
        生成 TDD 测试骨架（M3 方向 D）

        Args:
            module: 模块名（如 'talent'、'skill_a00d'）
            layer: 测试层 'unit' | 'integration' | 'e2e'
            name: 测试名（可选，默认 test_<layer>_<module>）
            source_dir: 源码目录

        Returns:
            {'success': bool, 'file': str, 'message': str, 'error': str | None}
        """
        # v0.19.3: 收敛 source_dir 归一化
        resolved = self.config.resolve_source_dir(source_dir)
        test_dir = self.config.get_test_dir_path(resolved)
        if test_dir is None:
            return {
                'success': False,
                'file': None,
                'message': '',
                'error': f'source_dir 非有效 w2l 项目根: {resolved}',
            }

        test_dir.mkdir(parents=True, exist_ok=True)

        # 生成测试文件名
        if name:
            test_name = name if name.startswith('test_') else f'test_{name}'
        else:
            test_name = f'test_{layer}_{module}'

        test_file = f'{test_name}.lua'
        test_file_path = test_dir / test_file

        # 检查文件是否已存在
        if test_file_path.exists():
            return {
                'success': False,
                'file': str(test_file_path),
                'message': '',
                'error': f'测试文件已存在: {test_file_path}',
            }

        # 生成骨架内容
        content = self._generate_test_skeleton(module, layer, test_name)

        try:
            with open(test_file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return {
                'success': True,
                'file': str(test_file_path),
                'message': f'已生成测试骨架: {test_file}\n\n'
                           f'下一步:\n'
                           f'1. 编辑 {test_file} 填充测试逻辑\n'
                           f'2. 运行 tdd_red(test_name="{test_name}", layer="{layer}") 确认 Red\n'
                           f'3. 实现功能代码\n'
                           f'4. 运行 tdd_green(test_name="{test_name}", layer="{layer}") 确认 Green',
                'error': None,
            }
        except Exception as e:
            return {
                'success': False,
                'file': str(test_file_path),
                'message': '',
                'error': f'写入文件失败: {e}',
            }

    def _generate_test_skeleton(self, module: str, layer: str, test_name: str) -> str:
        """生成测试骨架内容（通用，不硬编码项目路径）"""

        # 根据 layer 选择不同的引导方式
        if layer == 'unit':
            # 桌面单测：使用 jass_mock + assertions
            header = f'-- @layer unit\n'
            header += f'-- TDD 测试骨架: {test_name}\n'
            header += f'-- 桌面纯逻辑单测（秒级反馈）\n\n'
            header += f'-- 加载插件内置断言库（由 desktop_bootstrap 注入到 _G.__war3_tester_assertions）\n'
            header += f'local assert = _G.__war3_tester_assertions or {{}}\n'
            header += f'local assertEquals = assert.assertEquals or function(a, b, msg) error(msg or "assertion failed") end\n'
            header += f'local assertTrue = assert.assertTrue or function(cond, msg) if not cond then error(msg or "assertTrue failed") end end\n\n'
            header += f'-- 加载 jass mock（由 desktop_bootstrap 注入到 _G.__war3_tester_jass_mock）\n'
            header += f'-- local jass_mock = _G.__war3_tester_jass_mock\n\n'
            # unit 层使用 _G.__test_result（desktop_bootstrap 解析它）
            result_reporting = f'''
-- ============================================================================
-- 测试入口（最小契约: RunAutoTest）
-- ============================================================================

function RunAutoTest()
    print("=== 开始测试: {test_name} ===")

    local success, err = pcall(test_case_1)
    if not success then
        print("[FAIL] test_case_1: " .. tostring(err))
        -- 桌面层：设 _G.__test_result 让 desktop_bootstrap 解析为失败
        _G.__test_result = {{success=false, test_name='{test_name}', details=tostring(err), cases={{}}}}
        return
    end

    print("=== 测试完成: {test_name} ===")
    -- 桌面层：设 _G.__test_result 让 desktop_bootstrap 解析为成功
    _G.__test_result = {{success=true, test_name='{test_name}', details='all passed', cases={{}}}}
end
'''
        else:
            # integration/e2e: 游戏内测试，必须 HTTP POST /result
            header = f'-- @layer {layer}\n'
            header += f'-- TDD 测试骨架: {test_name}\n'
            header += f'-- 游戏内测试（需编译+启动游戏）\n\n'
            header += f'-- 加载插件内置断言库（由 lua_bootstrap 注入到 _G.__war3_tester_assertions）\n'
            header += f'local assert = _G.__war3_tester_assertions or {{}}\n'
            header += f'local assertEquals = assert.assertEquals or function(a, b, msg) error(msg or "assertion failed") end\n'
            header += f'local assertTrue = assert.assertTrue or function(cond, msg) if not cond then error(msg or "assertTrue failed") end end\n\n'
            # integration/e2e 层必须 HTTP POST（test_commit 不读 _G.__test_result）
            # 【通用性】不硬编码任何项目专有 require 路径，由项目自身提供 HTTP 客户端
            result_reporting = f'''
-- ============================================================================
-- HTTP POST 结果上报（通用骨架 - 需项目适配）
-- ============================================================================
-- 【重要】integration/e2e 层必须 HTTP POST 结果到 8766，test_commit 才能接收。
-- _G.__test_result 仅桌面层（desktop_bootstrap）使用，游戏内无效。
-- data 必须含 assertions 字段，_classify_failure 才能判定 assertion 失败。
--
-- 【适配说明】
-- War3 定制 Lua 通常无 luasocket（socket.http 不可用），需用项目/平台自身 HTTP 客户端。
-- 下方 http_post_result 是占位实现，需项目根据自身框架适配 HTTP POST 逻辑。
-- 参考范例：examples/wzns/run_auto_test.framework.lua（wzns 框架的 HTTP 适配器）
-- ============================================================================

local function http_post_result(test_name, success, details, assertions)
    local data = {{
        test_name = test_name,
        success = success,
        details = details or '',
        -- assertions 字段：_classify_failure 读取它判定 failure_type=assertion
        -- 格式: {{name='...', passed=true|false, message='...'}}, ...}}
        assertions = assertions or {{}},
    }}

    -- TODO: 项目适配 - 使用项目自身的 HTTP 客户端 POST 结果到 8766
    -- 常见模式（需项目实现）：
    --   local http_client = require('<your_project>.http_client')
    --   http_client.post('http://127.0.0.1:8766/result', data)
    --
    -- 参考范例：examples/wzns/run_auto_test.framework.lua 的 exportResults 函数
    --
    -- 占位实现：仅打印日志，实际游戏内不会上报（test_commit 会超时）
    print(string.format('[HTTP] TODO: 需项目适配 HTTP POST 到 http://127.0.0.1:8766/result'))
    print(string.format('[HTTP] test_name=%s, success=%s', test_name, tostring(success)))

    -- fallback 到 _G.__test_result（仅桌面层有效，游戏内 test_commit 不读）
    _G.__test_result = data
end

-- ============================================================================
-- 测试入口（最小契约: RunAutoTest）
-- ============================================================================

function RunAutoTest()
    print("=== 开始测试: {test_name} ===")

    local success, err = pcall(test_case_1)
    if not success then
        print("[FAIL] test_case_1: " .. tostring(err))
        -- 游戏内：HTTP POST 结果到 8766（test_commit 依赖此机制）
        -- assertions 含 passed=false 让 _classify_failure 判定 assertion（tdd_red -> red_valid）
        http_post_result('{test_name}', false, tostring(err),
            {{name='test_case_1', passed=false, message=tostring(err)}})
        return
    end

    print("=== 测试完成: {test_name} ===")
    -- 游戏内：HTTP POST 结果到 8766（test_commit 依赖此机制）
    http_post_result('{test_name}', true, 'all passed',
        {{name='test_case_1', passed=true}})
end
'''

        # TDD 三段式骨架（通用部分）
        skeleton = f'''
-- ============================================================================
-- 测试模块: {module}
-- 测试层: {layer}
-- ============================================================================

-- Arrange: 准备测试数据和环境
local function setup()
    -- TODO: 初始化测试数据
    -- 例如: local data = {{id = 1, name = "test"}}
    return {{}}
end

-- Act: 执行被测功能
local function execute(data)
    -- TODO: 调用被测函数
    -- 例如: local result = MyModule.process(data)
    -- return result
    return nil
end

-- Assert: 验证结果
local function verify(result)
    -- TODO: 断言检查结果
    -- 例如: assertEquals(result.id, 1, "ID 应该为 1")
    -- 例如: assertTrue(result.success, "应该成功")
end

-- ============================================================================
-- 测试用例
-- ============================================================================

local function test_case_1()
    print("[TEST] test_case_1: 基本功能测试")

    -- Arrange
    local data = setup()

    -- Act
    local result = execute(data)

    -- Assert
    verify(result)

    print("[PASS] test_case_1")
end

'''

        return header + skeleton + result_reporting

    def _tdd_red(self, test_name: str, layer: str, source_dir: str = None, timeout: int = 60) -> dict:
        """
        TDD Red 阶段 - 跑测试预期失败，确认测试有效（M3 方向 E）

        关键：区分「预期 assertion fail」（测试有效，Red 成立）vs「意外 env_error/compile_error」
        （测试写错或环境问题，Red 不成立）。

        Returns:
            {
                'status': 'red_valid' | 'red_invalid' | 'green',
                'failure_type': str | None,
                'reason': str | None,
                'error': str | None,
                'elapsed': float,
            }
        """
        # 根据 layer 选择运行方式
        if layer == 'unit':
            # 桌面单测
            result = self.desktop_runner.run_unit_test(test_name, source_dir, timeout)
        else:
            # integration/e2e: 游戏内测试
            result = self.test_commit(test_name, None, timeout, None, source_dir, False)

        elapsed = result.get('elapsed', 0)
        failure_type = result.get('failure_type')
        success = result.get('success', False)

        # 判断 Red 是否成立
        if success:
            # 测试通过了，但预期应该失败
            return {
                'status': 'green',
                'failure_type': None,
                'reason': '测试通过了，但 Red 阶段预期应该失败。请检查测试是否真的在验证未实现的功能',
                'error': None,
                'elapsed': elapsed,
            }

        # 测试失败了，判断是否是「预期失败」
        # 预期失败 = assertion failure（测试逻辑正确，功能未实现导致断言失败）
        # 非预期失败 = runtime_error / env_error / compile_error / module_load_error 等
        #   runtime_error = 测试运行时错（调用 nil 函数、数组越界等），可能是测试写错，不一定是功能未实现
        #   env_error / compile_error / module_load_error = 测试写错或环境问题
        if failure_type == 'assertion':
            # Red 成立：测试逻辑正确，断言失败，功能未实现
            return {
                'status': 'red_valid',
                'failure_type': failure_type,
                'reason': '测试预期失败（assertion failure），Red 成立：测试逻辑正确，功能未实现',
                'error': result.get('error'),
                'elapsed': elapsed,
            }
        else:
            # Red 不成立：非 assertion 失败，可能是测试写错或环境问题
            # runtime_error：可能是测试代码 bug（调用 nil 函数、数组越界等），需检查测试代码
            # env_error/compile_error/module_load_error：环境问题或测试文件写错
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
        """
        TDD Green 阶段 - 跑测试预期通过（M3 方向 E）

        Returns:
            与 test_commit / run_unit_test 同结构的 result
        """
        # 根据 layer 选择运行方式
        if layer == 'unit':
            # 桌面单测
            result = self.desktop_runner.run_unit_test(test_name, source_dir, timeout)
        else:
            # integration/e2e: 游戏内测试
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
    # v0.19.5(候选④): init_runtime 废弃,War3TesterMCP.__init__ 构造四全局
    server = War3TesterMCP()

    # 检测执行器连通性
    if not server.executor.check_connectivity():
        print(file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        if self.config.is_wsl:
            print("[ERROR] 无法连接到 Windows 代理", file=sys.stderr)
            print("请确保 Windows 代理已启动:", file=sys.stderr)
            print("  python win_proxy.py start", file=sys.stderr)
        else:
            print("[ERROR] 本地执行器不可用", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        return

    server.logger.info("执行器连接检测通过")

    # 启动 HTTP 接收端
    http_result = server.http_receiver.start()
    if http_result:
        server.logger.info(f"HTTP 服务器已启动（端口 {server.config.http_port}）")
    else:
        server.logger.warning("HTTP 服务器启动失败")

    server.logger.info("服务器已初始化")
    print("[OK] War3 Tester MCP Server 已启动", file=sys.stderr)

    def _cleanup_on_exit():
        """退出清理：停 HTTP 接收端 + 杀 war3 进程（仅 Windows）"""
        try:
            server.http_receiver.stop()
        except Exception as e:
            server.logger.warning(f"退出清理 http_receiver.stop 异常：{e}")

        # war3 是 Windows 游戏，仅 Windows 执行 taskkill；Linux/macOS 跳过
        if server.config.is_windows or server.config.is_wsl:
            for proc_name in server.config.war3_process_names:
                try:
                    subprocess.run(
                        ['taskkill', '/IM', proc_name, '/F'],
                        capture_output=True,
                        timeout=5
                    )
                except Exception:
                    pass

    # 兜底：atexit 保证任何退出路径都执行清理
    atexit.register(_cleanup_on_exit)

    # SIGTERM handler：Claude Code /exit 给 MCP 发 SIGTERM 时触发清理
    # Windows 下 SIGTERM 可注册，但实际是否触发取决于退出方式（TerminateProcess 等价 SIGKILL 不跑 handler）
    def _on_sigterm(signum, frame):
        server.logger.info("收到 SIGTERM，执行退出清理")
        _cleanup_on_exit()
        sys.exit(0)
    signal.signal(signal.SIGTERM, _on_sigterm)

    # stdio JSON-RPC 主循环
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
                                "version": "1.0.0"
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
