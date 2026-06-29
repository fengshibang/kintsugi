#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
War3 Tester 通用 MCP Server

提供地图编译、游戏测试的 MCP 工具接口（stdio JSON-RPC）。
从基线 scripts/mcp_war3_tester.py 剥离框架耦合。

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
from pathlib import Path
from datetime import datetime

# 自解析路径（【红线 6】严禁依赖 cwd 或硬编码绝对路径）
SERVER_DIR = Path(__file__).parent
sys.path.insert(0, str(SERVER_DIR))

from config import Config
from env_bridge import create_executor
from http_receiver import HTTPReceiver
from logger import setup_logger

# 初始化配置
config = Config()

# 创建执行器（按 is_wsl() 自动选择）
executor = create_executor(config)

# HTTP 接收端
http_receiver = HTTPReceiver(host=config.http_host, port=config.http_port)


class War3TesterMCP:
    """War3 Tester MCP Server"""

    def __init__(self):
        self.project_root = config.project_root
        self.logger = setup_logger('war3-mcp')
        self.executor = executor
        self.http_receiver = http_receiver

        # MCP 能力声明
        self.capabilities = {
            "tools": [
                {
                    "name": "compile_map",
                    "description": "编译地图 - 使用 w2l.exe slk 编译地图，不启动游戏",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "source_dir": {
                                "type": "string",
                                "description": "源码目录路径，默认使用 config.compile_source_dir"
                            }
                        }
                    }
                },
                {
                    "name": "test_commit",
                    "description": "测试代码变更 - 编译地图并启动游戏运行测试",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "test_name": {
                                "type": "string",
                                "description": "测试名称，如 'test_hero_h000'"
                            },
                            "test_file": {
                                "type": "string",
                                "description": "测试 Lua 文件名（如 'test_skill_a00d.lua'）"
                            },
                            "timeout": {
                                "type": "integer",
                                "description": "等待测试完成的超时时间（秒），默认 60",
                                "default": 60
                            },
                            "platform": {
                                "type": "string",
                                "description": "游戏平台：'ydwe' 或 'kkwe'，默认自动选择",
                                "enum": ["ydwe", "kkwe"]
                            },
                            "source_dir": {
                                "type": "string",
                                "description": "源码目录路径（支持 ${workspaceRoot} 变量）"
                            }
                        },
                        "required": ["test_name"]
                    }
                },
                {
                    "name": "compile_only",
                    "description": "仅编译地图，不启动游戏",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "source_dir": {
                                "type": "string",
                                "description": "源码目录路径"
                            }
                        }
                    }
                },
                {
                    "name": "launch_only",
                    "description": "仅启动游戏，不编译",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "map_path": {
                                "type": "string",
                                "description": "地图文件路径"
                            },
                            "platform": {
                                "type": "string",
                                "description": "游戏平台：'ydwe' 或 'kkwe'",
                                "enum": ["ydwe", "kkwe"]
                            }
                        }
                    }
                },
                {
                    "name": "run_game",
                    "description": "仅启动游戏，不运行测试",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "map_path": {
                                "type": "string",
                                "description": "地图文件路径"
                            },
                            "platform": {
                                "type": "string",
                                "description": "游戏平台：'ydwe' 或 'kkwe'",
                                "enum": ["ydwe", "kkwe"]
                            }
                        }
                    }
                },
                {
                    "name": "stop_game",
                    "description": "关闭魔兽争霸 3 游戏进程",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "platform": {
                                "type": "string",
                                "description": "游戏平台：'ydwe' 或 'kkwe'",
                                "enum": ["ydwe", "kkwe"]
                            }
                        }
                    }
                },
                {
                    "name": "stop_http_server",
                    "description": "关闭 HTTP 测试服务器",
                    "inputSchema": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                },
                {
                    "name": "cleanup_all",
                    "description": "清理所有资源 - 关闭 war3.exe 进程和 HTTP 服务器",
                    "inputSchema": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                },
                {
                    "name": "take_screenshot",
                    "description": "截取游戏窗口截图",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "test_name": {
                                "type": "string",
                                "description": "测试名称，用于组织截图文件"
                            },
                            "filename": {
                                "type": "string",
                                "description": "截图文件名（可选）"
                            },
                            "window_title": {
                                "type": "string",
                                "description": "窗口标题关键词（可选）"
                            }
                        },
                        "required": ["test_name"]
                    }
                },
                {
                    "name": "send_key",
                    "description": "向 War3 游戏窗口发送键盘事件",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "key": {
                                "type": "string",
                                "description": "按键名称：'enter', 'space', 'escape', 或数字 '0'-'9'",
                                "enum": ["enter", "space", "escape", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9"]
                            }
                        },
                        "required": ["key"]
                    }
                },
            ],
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

    def _prepare_test_entry(self, test_name: str, test_file: str, source_dir: str) -> None:
        """
        准备测试入口文件（编译前调用）。

        【红线 1/4/9/10】通用化：
        - test_dir 可配置（默认 'auto-test'）
        - test_module_prefix 可配置（默认空串）
        - 严禁框架词

        Args:
            test_name: 测试名称
            test_file: 测试文件名（如 'test_skill_a00d.lua'）
            source_dir: 源码目录
        """
        # 解析 source_dir
        resolved_source = config._resolve_path(source_dir) if source_dir else self.project_root
        test_dir = config.get_test_dir_path(resolved_source)
        test_dir.mkdir(parents=True, exist_ok=True)

        # 推断 test_file
        if not test_file:
            if re.search(r'[一-鿿]', test_name):
                raise ValueError(
                    f"test_name='{test_name}' 包含中文，无法推断文件名，"
                    f"请显式传入 test_file 参数"
                )
            test_file = f'test_{test_name}.lua'

        if not test_file.endswith('.lua'):
            test_file = test_file + '.lua'

        # 构建模块名
        # test_module_base = 不含前缀的相对模块名（交给引导脚本拼 test_module_prefix）
        # module_name = 完整路径（仅用于日志）
        test_module_base = test_file.replace('.lua', '').replace('/', '.')
        module_name = config.test_module_prefix + test_module_base if config.test_module_prefix else test_module_base

        self.logger.info(f"[test_commit] test_name={test_name}, test_file={test_file}, module={module_name}")

        # 写 _target_test.lua
        target_test_path = test_dir / '_target_test.lua'
        # 【F4 修复】携带 http_host/http_port，让测试文件知道往哪 POST 结果
        # 游戏运行在 Windows 侧，统一 POST 到 127.0.0.1：
        # - WSL 模式：经 WSL2 localhost forwarding 到达 WSL 接收端（与旧硬编码 127.0.0.1 同机制）
        # - 原生 Windows：直达本机接收端
        # 注：wsl_to_windows_ip 是 WSL→Windows 方向，游戏在 Windows 侧用它方向反了
        http_host_for_game = '127.0.0.1'
        target_test_content = (
            f"return {{test_name='{test_name}', test_file='{test_file}', "
            f"test_module='{test_module_base}', test_module_prefix='{config.test_module_prefix}', "
            f"http_host='{http_host_for_game}', http_port={config.http_port}}}\n"
        )
        with open(target_test_path, 'w', encoding='utf-8') as f:
            f.write(target_test_content)
        self.logger.info(f"[test_commit] 已写入 _target_test.lua")

        # 写 run_auto_test.lua（引导模板选择逻辑）
        # 【v0.2 增强】支持 test_bootstrap_template 自定义引导模板
        run_auto_test_path = test_dir / 'run_auto_test.lua'
        bootstrap_content = None

        # 1. 若配置了自定义模板，尝试读取
        if config.test_bootstrap_template:
            custom_template_path = config._resolve_path(config.test_bootstrap_template)
            if custom_template_path.exists():
                try:
                    with open(custom_template_path, 'r', encoding='utf-8') as f:
                        bootstrap_content = f.read()
                    self.logger.info(f"[test_commit] 使用自定义引导模板: {custom_template_path}")
                except (IOError, OSError) as e:
                    self.logger.warning(f"[test_commit] 自定义模板读取失败: {e}，fallback 到通用模板")
                    bootstrap_content = None
            else:
                self.logger.warning(f"[test_commit] 自定义模板不存在: {custom_template_path}，fallback 到通用模板")

        # 2. 未配置或读取失败时，使用通用模板
        if bootstrap_content is None:
            generic_bootstrap_path = SERVER_DIR / 'lua_bootstrap.lua'
            if generic_bootstrap_path.exists():
                with open(generic_bootstrap_path, 'r', encoding='utf-8') as f:
                    bootstrap_content = f.read()
                self.logger.info(f"[test_commit] 使用通用引导模板: {generic_bootstrap_path}")
            else:
                self.logger.warning(f"[test_commit] 通用引导模板不存在: {generic_bootstrap_path}")
                return  # 无法写入引导，直接返回

        # 3. 写入 run_auto_test.lua
        with open(run_auto_test_path, 'w', encoding='utf-8') as f:
            f.write(bootstrap_content)
        self.logger.info(f"[test_commit] 已写入 run_auto_test.lua")

    def test_commit(self, test_name: str, test_file: str = None,
                    timeout: int = 60, platform: str = None, source_dir: str = None) -> dict:
        """
        运行测试 - 编译 + 启动游戏 + 等待 HTTP 结果

        Args:
            test_name: 测试名称
            test_file: 测试文件名
            timeout: 超时时间（秒）
            platform: 游戏平台
            source_dir: 源码目录
        """
        # 0. 预清理
        self.logger.info(f"[test_commit] 预清理...")
        self.executor.stop_game()
        time.sleep(3)

        # 0.5 准备测试入口
        try:
            self._prepare_test_entry(test_name, test_file, source_dir)
        except Exception as e:
            return {
                'success': False,
                'error': f'准备测试入口失败：{e}',
                'message': '测试入口准备失败'
            }

        # 1. 编译
        compile_result = self.executor.compile(source_dir)
        if not compile_result.get('success'):
            return {
                'success': False,
                'error': f'编译失败：{compile_result.get("error", "unknown")}',
                'message': '地图编译失败'
            }

        # 2. 启动游戏
        run_result = self.executor.run_game(platform=platform)
        if not run_result.get('success'):
            return {
                'success': False,
                'error': f'启动游戏失败：{run_result.get("error", "unknown")}',
                'message': '游戏启动失败'
            }

        # 3. 等待测试结果
        self.http_receiver.delete_old_result(test_name)
        result_file = self.http_receiver.get_result_file(test_name)

        self.logger.info(f"[test_commit] 等待测试结果 (超时 {timeout}s)...")
        elapsed = 0
        poll_interval = 3
        while elapsed < timeout:
            time.sleep(poll_interval)
            elapsed += poll_interval

            if result_file.exists():
                try:
                    with open(result_file, 'r', encoding='utf-8') as f:
                        test_data = json.load(f)
                    self.logger.info(f"[test_commit] 测试结果已接收: {test_name}")
                    self.executor.stop_game()
                    time.sleep(1)
                    test_success = test_data.get('success', False)
                    return {
                        'success': True,
                        'message': f'测试完成：{test_name}\n测试结果：{"通过" if test_success else "失败"}\n耗时：{elapsed}s',
                        'test_name': test_name,
                        'result': test_data,
                        'result_file': str(result_file),
                        'elapsed': elapsed,
                    }
                except (json.JSONDecodeError, IOError) as e:
                    self.logger.warning(f"[test_commit] 结果文件读取失败: {e}")
                    continue

            self.logger.info(f"[test_commit] 等待中... ({elapsed}/{timeout}s)")

        # 超时
        self.logger.warning(f"[test_commit] 等待超时 ({timeout}s)")
        self.executor.stop_game()
        return {
            'success': False,
            'error': f'测试超时 ({timeout}s)',
            'message': f'测试超时：{test_name}',
            'test_name': test_name,
        }

    async def handle_tool_call(self, tool_name: str, arguments: dict) -> dict:
        """处理工具调用"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if tool_name in ("compile_map", "compile_only"):
            source_dir = arguments.get("source_dir", str(config.compile_source_dir))
            source_dir = str(config._resolve_path(source_dir))
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

        elif tool_name == "test_commit":
            test_name = arguments.get("test_name", "unknown")
            test_file = arguments.get("test_file")
            timeout = arguments.get("timeout", 60)
            platform = arguments.get("platform")
            source_dir = arguments.get("source_dir")

            if not source_dir:
                source_dir = str(config.compile_source_dir)
            else:
                source_dir = str(config._resolve_path(source_dir))

            if not platform:
                run_mode, _ = config.get_run_mode_with_source()
                platform = run_mode

            result = self.test_commit(test_name, test_file, timeout, platform, source_dir)

            messages = [f"## 测试代码变更\n\n时间：{timestamp}"]
            if result.get("message"):
                messages.append(result.get("message", ""))
            elif result.get("error"):
                messages.append(f"\n[ERROR] {result.get('error', 'unknown')}")

            return {"content": [{"type": "text", "text": "\n".join(messages)}]}

        elif tool_name in ("launch_only", "run_game"):
            map_path = arguments.get("map_path", str(config.compile_output_path / config.compile_output_name))
            platform = arguments.get("platform")

            if not platform:
                run_mode, _ = config.get_run_mode_with_source()
                platform = run_mode

            result = self.executor.run_game(map_path, platform)

            if result.get("success"):
                return {
                    "content": [{"type": "text", "text": f"[OK] 游戏已启动\n\n{result.get('message', '')}"}]
                }
            else:
                return {
                    "content": [{"type": "text", "text": f"[FAIL] 游戏启动失败\n\n{result.get('error', '未知错误')}"}],
                    "isError": True
                }

        elif tool_name == "stop_game":
            result = self.executor.stop_game()

            if result.get("success"):
                return {
                    "content": [{"type": "text", "text": f"[OK] {result.get('message', '游戏已关闭')}"}]
                }
            else:
                return {
                    "content": [{"type": "text", "text": f"[FAIL] {result.get('error', '游戏关闭失败')}"}],
                    "isError": True
                }

        elif tool_name == "send_key":
            key = arguments.get("key", "enter")
            result = self.executor.send_key(key)

            if result.get("success"):
                return {
                    "content": [{"type": "text", "text": f"[OK] 已发送 {key} 键\n\n{result.get('message', '')}"}]
                }
            else:
                return {
                    "content": [{"type": "text", "text": f"[FAIL] 发送按键失败\n\n{result.get('error', '未知错误')}"}],
                    "isError": True
                }

        elif tool_name == "take_screenshot":
            # 【F1 修复】调用 executor.take_screenshot 实现真实截图
            test_name = arguments.get("test_name", "unknown")
            filename = arguments.get("filename")
            window_title = arguments.get("window_title")

            result = self.executor.take_screenshot(test_name, filename, window_title)

            if result.get("success"):
                return {
                    "content": [{"type": "text", "text": f"[OK] 截图已保存\n\n{result.get('message', '')}\n\nWSL 路径：{result.get('path_wsl', '')}\nWindows 路径：{result.get('path', '')}"}]
                }
            else:
                return {
                    "content": [{"type": "text", "text": f"[FAIL] 截图失败\n\n{result.get('error', '未知错误')}"}],
                    "isError": True
                }

        elif tool_name == "stop_http_server":
            self.http_receiver.stop()
            return {
                "content": [{"type": "text", "text": "[OK] HTTP 服务器将随主进程退出自动关闭"}]
            }

        elif tool_name == "cleanup_all":
            stop_result = self.executor.stop_game()
            return {
                "content": [{"type": "text", "text": f"[OK] 清理完成\n\n{stop_result.get('message', '')}"}]
            }

        else:
            return {
                "content": [{"type": "text", "text": f"未知工具：{tool_name}"}],
                "isError": True
            }

    async def handle_resource_read(self, uri: str) -> dict:
        """处理资源读取"""
        if uri == "war3://logs/compile":
            log_path = self.project_root / "logs" / "compile.log"
            if log_path.exists():
                content = log_path.read_text(encoding="utf-8", errors="ignore")[-10000:]
                return {"contents": [{"uri": uri, "text": content}]}
            return {"contents": [{"uri": uri, "text": "日志文件不存在"}]}

        elif uri == "war3://logs/game":
            log_path = config.get_war3_log_file_path(player_id=1)
            if log_path and log_path.exists():
                content = log_path.read_text(encoding="utf-8", errors="ignore")[-10000:]
                return {"contents": [{"uri": uri, "text": content}]}
            return {"contents": [{"uri": uri, "text": "日志文件不存在"}]}

        elif uri == "war3://logs/game/list":
            log_dir = config.war3_log_dir
            if log_dir and log_dir.exists():
                log_files = sorted(log_dir.glob("玩家*.log"))
                file_list = "\n".join([f.name for f in log_files[-20:]])
                return {"contents": [{"uri": uri, "text": f"最近的游戏日志文件:\n{file_list}"}]}
            return {"contents": [{"uri": uri, "text": "日志目录不存在或为空"}]}

        return {"contents": [{"uri": uri, "text": "未知资源"}]}


async def run_server():
    """运行 MCP 服务器（stdio JSON-RPC 主循环）"""
    server = War3TesterMCP()

    # 检测执行器连通性
    if not server.executor.check_connectivity():
        print(file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        if config.is_wsl:
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
        server.logger.info(f"HTTP 服务器已启动（端口 {config.http_port}）")
    else:
        server.logger.warning("HTTP 服务器启动失败")

    server.logger.info("服务器已初始化")
    print("[OK] War3 Tester MCP Server 已启动", file=sys.stderr)

    # stdio JSON-RPC 主循环
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


if __name__ == "__main__":
    asyncio.run(run_server())
