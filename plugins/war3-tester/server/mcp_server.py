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
import base64
import mimetypes
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime

# 自解析路径（【红线 6】严禁依赖 cwd 或硬编码绝对路径）
SERVER_DIR = Path(__file__).parent
sys.path.insert(0, str(SERVER_DIR))

from config import Config
from env_bridge import create_executor
from http_receiver import HTTPReceiver
from test_batch_runner import TestBatchRunner
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
        # v2: 批量测试编排器（复用 _prepare_test_entry，与 test_commit 共享单测执行核心）
        self.batch_runner = TestBatchRunner(config, executor, http_receiver, self)

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
                            },
                            "auto_screenshot_on_failure": {
                                "type": "boolean",
                                "default": True,
                                "description": "失败时自动截图（仅 crash/timeout/unknown 触发，v2 增强）"
                            }
                        },
                        "required": ["test_name"]
                    }
                },
                {
                    "name": "run_test_batch",
                    "description": "批量运行测试 - 顺序运行多个测试（每个独立游戏会话），返回结构化汇总。支持 filter=all/failed/列表、重试、超时、失败截图、failure_type 分类（v2 新增）",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "test_filter": {
                                "type": ["string", "array"],
                                "description": "'all'(默认) | 'failed'(复用上次失败列表) | 测试名/文件名列表 | glob 子串",
                                "default": "all"
                            },
                            "stop_on_first_failure": {
                                "type": "boolean", "default": False,
                                "description": "首个失败即停止后续测试"
                            },
                            "max_retries": {
                                "type": "integer", "default": 1,
                                "description": "单测失败最大重试次数"
                            },
                            "timeout_per_test": {
                                "type": "integer", "default": 90,
                                "description": "单测超时秒数"
                            },
                            "auto_screenshot_on_failure": {
                                "type": "boolean", "default": True,
                                "description": "失败时自动截图（仅 crash/timeout/unknown 触发）"
                            },
                            "platform": {
                                "type": "string", "enum": ["ydwe", "kkwe"],
                                "description": "游戏平台，默认自动选择"
                            },
                            "source_dir": {
                                "type": "string",
                                "description": "源码目录路径"
                            }
                        }
                    }
                },
                {
                    "name": "discover_tests",
                    "description": "发现测试 - 扫描测试目录，返回测试列表 + 分类(sync/async) + 估算耗时（v2 新增）",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "filter": {
                                "type": "string",
                                "description": "过滤子串（匹配 test_name），可选"
                            },
                            "source_dir": {
                                "type": "string",
                                "description": "源码目录路径"
                            }
                        }
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
                    "name": "analyze_screenshot",
                    "description": "用多模态视觉模型（VLM）分析游戏截图，返回画面判读文本。需要环境变量 VLM_MODEL/VLM_BASE_URL/VLM_API_KEY",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "png_path": {
                                "type": "string",
                                "description": "截图 PNG 文件路径（Windows 绝对路径或相对路径）"
                            },
                            "prompt": {
                                "type": "string",
                                "description": "自定义分析提示词（可选，默认判读画面状态/UI元素/是否卡对话框/可见数值）"
                            }
                        },
                        "required": ["png_path"]
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
                {
                    "name": "toggle_test",
                    "description": "一键开关自动测试模式。关闭时 auto-test 模块不加载（手动游戏零干扰：无横幅/无 log 拦截/无自动选难度/无自动跑测试）；开启时恢复默认加载。变更后自动重编译地图。",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "enabled": {
                                "type": "boolean",
                                "description": "true=开启(恢复 auto-test 加载，跑测试仍需 test_commit)；false=关闭(模块不加载，手动游戏零干扰)"
                            },
                            "source_dir": {
                                "type": "string",
                                "description": "源码目录路径，默认 config.compile_source_dir"
                            }
                        },
                        "required": ["enabled"]
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

        # 测试时强制开启：删除 toggle_test 写入的关闭标志，确保 test_commit 能跑测试
        off_path = test_dir / '_test_off.lua'
        if off_path.exists():
            off_path.unlink()
            self.logger.info("[test_commit] 已删除 _test_off.lua（强制开启测试模式）")

        # 推断 test_file
        if not test_file:
            if re.search(r'[一-鿿]', test_name):
                raise ValueError(
                    f"test_name='{test_name}' 包含中文，无法推断文件名，"
                    f"请显式传入 test_file 参数"
                )
            # 修复：test_name 可能已含 'test_' 前缀（如 'test_xinfa_faction'），
            # 此时不再追加，避免生成 'test_test_xinfa_faction.lua' 致 require 失败、test_commit 报 env_error
            if test_name.startswith('test_'):
                test_file = f'{test_name}.lua'
            else:
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
                    timeout: int = 60, platform: str = None, source_dir: str = None,
                    auto_screenshot_on_failure: bool = True) -> dict:
        """运行测试 - 编译 + 启动游戏 + 等待 HTTP 结果

        v2 增强（设计文档 4.1）：委托 batch_runner._run_single_test，与 run_test_batch
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
        single = self.batch_runner._run_single_test(
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

        关闭(false)：写入 _test_off.lua（内容 return true），auto-test/init.lua 顶部
            pcall(require) 命中后整个模块 early-return → 手动游戏零干扰。
            同时删除 _target_test.lua / run_auto_test.lua 残留，避免旧测试入口意外激活。
        开启(true)：删除 _test_off.lua，恢复 auto-test 模块默认加载。
        注：跑测试本身仍需 test_commit（它写入 _target_test.lua，并会自动删除 _test_off.lua）。
        """
        test_dir = config.get_test_dir_path(config._resolve_path(source_dir))
        test_dir.mkdir(parents=True, exist_ok=True)
        off_path = test_dir / '_test_off.lua'
        target_path = test_dir / '_target_test.lua'
        run_auto_path = test_dir / 'run_auto_test.lua'

        if enabled:
            if off_path.exists():
                off_path.unlink()
            action = '已开启：auto-test 模块恢复加载（跑测试请用 test_commit）'
            self.logger.info('[toggle_test] 开启：删除 _test_off.lua')
        else:
            # 写关闭标志 + 清测试残留，确保手动游戏零干扰
            off_path.write_text(
                '-- toggle_test 生成：本文件存在则 auto-test 模块不加载（手动游戏模式）\n'
                'return true\n',
                encoding='utf-8')
            for p in (target_path, run_auto_path):
                if p.exists():
                    p.unlink()
            action = '已关闭：auto-test 模块不加载，手动游戏零干扰'
            self.logger.info('[toggle_test] 关闭：写入 _test_off.lua，清理 _target_test.lua/run_auto_test.lua 残留')

        # 重编译让 .w3x 反映标志文件变更
        compile_result = self.executor.compile(source_dir)
        return {
            'success': compile_result.get('success', False),
            'enabled': enabled,
            'action': action,
            'compile_error': compile_result.get('error') if not compile_result.get('success') else None,
        }

    def _read_image_b64(self, path: str):
        """读取图片，返回 (base64 数据, media_type)。"""
        if not os.path.isfile(path):
            raise FileNotFoundError(f"截图文件不存在: {path}")
        mime = mimetypes.guess_type(path)[0] or "image/png"
        # Anthropic 兼容接口只接受 image/png、image/jpeg、image/gif、image/webp
        if mime not in ("image/png", "image/jpeg", "image/gif", "image/webp"):
            mime = "image/png"
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode(), mime

    def analyze_screenshot(self, png_path: str, prompt: str = "") -> str:
        """调用多模态视觉模型（VLM）分析截图，返回文本结果。

        逻辑照搬 scripts/analyze_screenshot.py 的 analyze() 函数：
        - 读图 → base64 → 调 Anthropic 兼容接口 POST {VLM_BASE_URL}/v1/messages
        - 模型/URL/key 从环境变量读：VLM_MODEL、VLM_BASE_URL、VLM_API_KEY
        - 缺任一项都明确报错（不静默用默认值）
        """
        if not prompt:
            prompt = (
                "你是 War3 自动化测试的视觉判读助手。请分析这张游戏截图，输出：\n"
                "1. 画面状态（主菜单/选难度/对战中/结算 等）\n"
                "2. UI 元素（对话框、按钮、血条、技能栏是否可见）\n"
                "3. 是否卡在需要用户输入的对话框（是/否 + 依据）\n"
                "4. 单位/血量等可见数值\n"
                "简洁分条作答。"
            )

        b64, mime = self._read_image_b64(png_path)

        # 环境变量读取（缺任一项报错，不静默用默认值）
        base_url = os.environ.get("VLM_BASE_URL") or os.environ.get("ANTHROPIC_BASE_URL")
        if not base_url:
            raise RuntimeError(
                "未配置 VLM_BASE_URL（或 ANTHROPIC_BASE_URL）。"
                "请在 ~/.claude/settings.json 的 env 中设置 VLM_BASE_URL，"
                "然后 /mcp 重连 war3-tester。"
            )
        model = os.environ.get("VLM_MODEL")
        if not model:
            raise RuntimeError(
                "未配置 VLM_MODEL（视觉多模态模型名）。"
                "请在 ~/.claude/settings.json 的 env 中设置 VLM_MODEL"
                "（当前视觉模型，例如 qwen3.7-plus），然后 /mcp 重连 war3-tester。"
            )
        api_key = os.environ.get("VLM_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
        if not api_key:
            raise RuntimeError(
                "未配置 VLM_API_KEY（或 ANTHROPIC_AUTH_TOKEN）。"
                "请在 ~/.claude/settings.json 的 env 中设置 API token，"
                "然后 /mcp 重连 war3-tester。"
            )

        payload = {
            "model": model,
            "max_tokens": 1024,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": mime,
                                "data": b64,
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        }

        req = urllib.request.Request(
            f"{base_url.rstrip('/')}/v1/messages",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"代理返回 HTTP {e.code}:\n{body}") from None
        except urllib.error.URLError as e:
            raise RuntimeError(f"无法连接代理 {base_url}: {e.reason}") from None

        # Anthropic 兼容响应：content 是 block 数组
        blocks = data.get("content", [])
        texts = [b.get("text", "") for b in blocks if b.get("type") == "text"]
        result = "\n".join(t for t in texts if t).strip()
        if not result:
            raise RuntimeError(f"模型未返回文本。原始响应:\n{json.dumps(data, ensure_ascii=False)}")
        return result

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
            auto_screenshot_on_failure = arguments.get("auto_screenshot_on_failure", True)

            if not source_dir:
                source_dir = str(config.compile_source_dir)
            else:
                source_dir = str(config._resolve_path(source_dir))

            if not platform:
                run_mode, _ = config.get_run_mode_with_source()
                platform = run_mode

            result = self.test_commit(test_name, test_file, timeout, platform, source_dir,
                                      auto_screenshot_on_failure)

            messages = [f"## 测试代码变更\n\n时间：{timestamp}"]
            if result.get("message"):
                messages.append(result.get("message", ""))
            elif result.get("error"):
                messages.append(f"\n[ERROR] {result.get('error', 'unknown')}")

            return {"content": [{"type": "text", "text": "\n".join(messages)}]}

        elif tool_name == "run_test_batch":
            test_filter = arguments.get("test_filter", "all")
            stop_on_first_failure = arguments.get("stop_on_first_failure", False)
            max_retries = arguments.get("max_retries", 1)
            timeout_per_test = arguments.get("timeout_per_test", 90)
            auto_ss = arguments.get("auto_screenshot_on_failure", True)
            platform = arguments.get("platform")
            source_dir = arguments.get("source_dir")
            if source_dir:
                source_dir = str(config._resolve_path(source_dir))
            if not platform:
                run_mode, _ = config.get_run_mode_with_source()
                platform = run_mode

            batch_result = self.batch_runner.run_test_batch(
                test_filter=test_filter, stop_on_first_failure=stop_on_first_failure,
                max_retries=max_retries, timeout_per_test=timeout_per_test,
                auto_screenshot_on_failure=auto_ss, source_dir=source_dir, platform=platform)

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

        elif tool_name == "discover_tests":
            flt = arguments.get("filter")
            source_dir = arguments.get("source_dir")
            if source_dir:
                source_dir = str(config._resolve_path(source_dir))
            discovery = self.batch_runner.discover_tests(source_dir, filter_pattern=flt)
            if discovery.get("success"):
                tests = discovery.get("tests", [])
                lines = [f"发现 {len(tests)} 个测试（估算 {discovery.get('total_est_seconds')}s）："]
                for t in tests:
                    lines.append(f"  - {t['test_name']} ({t['type']}, ~{t['est_seconds']}s)")
                return {"content": [{"type": "text",
                                     "text": f"## 测试发现\n\n时间：{timestamp}\n\n" + "\n".join(lines)}]}
            return {"content": [{"type": "text", "text": f"[FAIL] {discovery.get('error', '未知错误')}"}],
                    "isError": True}

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

        elif tool_name == "analyze_screenshot":
            png_path = arguments.get("png_path")
            prompt = arguments.get("prompt", "")
            if not png_path:
                return {
                    "content": [{"type": "text", "text": "[FAIL] 缺少 png_path 参数"}],
                    "isError": True
                }
            try:
                analysis_text = self.analyze_screenshot(png_path, prompt)
                return {
                    "content": [{"type": "text", "text": f"[OK] 截图分析完成\n\n时间：{timestamp}\n\n{analysis_text}"}]
                }
            except Exception as e:
                return {
                    "content": [{"type": "text", "text": f"[FAIL] 截图分析失败\n\n{e}"}],
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

        elif tool_name == "toggle_test":
            enabled = arguments.get("enabled", True)
            source_dir = arguments.get("source_dir")
            if not source_dir:
                source_dir = str(config.compile_source_dir)
            else:
                source_dir = str(config._resolve_path(source_dir))

            result = self.toggle_test(enabled, source_dir)
            if result.get("success"):
                return {
                    "content": [{"type": "text",
                                 "text": f"[OK] 测试模式{result.get('action', '')}\n\n时间：{timestamp}"}]
                }
            else:
                msg = f"[FAIL] toggle_test 未完成\n\n时间：{timestamp}\n"
                if result.get("compile_error"):
                    msg += f"编译失败：{result['compile_error']}"
                return {"content": [{"type": "text", "text": msg}], "isError": True}

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
