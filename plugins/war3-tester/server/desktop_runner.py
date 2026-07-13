#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
桌面 Lua 运行器 - 不启动游戏，直接用桌面 lua5.3 跑纯逻辑测试

Milestone 2: 桌面纯逻辑单测层
- 探测系统 lua5.3（或插件自带）
- 加载 jass_mock.lua + assertions.lua + 被测模块 + 测试文件
- 捕获 stdout/断言结果，按 /result 同格式返回

两套 executor 路径：
- WinProxyExecutor (is_wsl=True): 经 win_proxy TCP 转发到 Windows 执行 lua5.3
- LocalExecutor (is_wsl=False): 直接 subprocess 跑 lua5.3
"""

import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional, Dict, Any

from logger import setup_logger


class DesktopRunner:
    """桌面 Lua 运行器"""

    def __init__(self, config, executor):
        """
        Args:
            config: Config 实例
            executor: ExecutorBase 实例（WinProxyExecutor 或 LocalExecutor）
        """
        self.config = config
        self.executor = executor
        self.logger = setup_logger('desktop-runner')

    def find_lua_executable(self) -> Optional[str]:
        """
        探测 lua5.3 可执行文件

        查找顺序：
        1. 环境变量 LUA_EXE（若指定，指向 lua 可执行文件路径）
        2. 系统 PATH 中的 lua5.3 / lua53 / lua
        3. 插件目录下自带的 lua（未来扩展）

        注意：LUA_PATH 是 Lua 的 package.path 环境变量（模块搜索路径），
              不是可执行文件路径，此处不用。

        Returns:
            lua 可执行文件路径，未找到返回 None
        """
        # 1. 环境变量 LUA_EXE（注意：不是 LUA_PATH，后者是 package.path）
        env_lua = os.environ.get('LUA_EXE')
        if env_lua and os.path.isfile(env_lua):
            return env_lua

        # 2. 系统 PATH 探测
        candidates = ['lua5.3', 'lua53', 'lua']
        for cmd in candidates:
            if shutil.which(cmd):
                return cmd

        # 3. 插件目录自带（未来扩展）
        # plugin_lua = Path(__file__).parent / 'bin' / ('lua.exe' if os.name == 'nt' else 'lua')
        # if plugin_lua.exists():
        #     return str(plugin_lua)

        return None

    def run_unit_test(self, test_name: str, source_dir: str = None, timeout: int = 10) -> Dict[str, Any]:
        """
        运行桌面纯逻辑测试

        Args:
            test_name: 测试名称（如 'test_talent_config'）
            source_dir: 源码目录（默认 config.compile_source_dir）
            timeout: 超时时间（秒，默认 10）

        Returns:
            {
                'success': bool,
                'test_name': str,
                'details': str,
                'cases': list,
                'elapsed': float,
                'error': str | None,
                'failure_type': str | None,  # 'lua_not_found' | 'module_load_error' | 'assertion' | 'timeout' | 'runtime_error'
            }
        """
        start_time = time.time()

        # 1. 探测 lua 可执行文件
        lua_exe = self.find_lua_executable()
        if not lua_exe:
            return {
                'success': False,
                'test_name': test_name,
                'details': '',
                'cases': [],
                'elapsed': time.time() - start_time,
                'error': '未找到 lua5.3 可执行文件。请安装 lua5.3 或设置环境变量 LUA_EXE 指向 lua 可执行文件',
                'failure_type': 'lua_not_found',
            }

        # 2. 解析 source_dir 和测试目录
        resolved_source = self.config._resolve_path(source_dir) if source_dir else self.config.compile_source_dir
        test_dir = self.config.get_test_dir_path(resolved_source)
        if test_dir is None:
            return {
                'success': False,
                'test_name': test_name,
                'details': '',
                'cases': [],
                'elapsed': time.time() - start_time,
                'error': f'source_dir 非有效 w2l 项目根: {resolved_source}',
                'failure_type': 'env_error',
            }

        # 3. 推断测试文件
        if not test_name.startswith('test_'):
            test_file = f'test_{test_name}.lua'
        else:
            test_file = f'{test_name}.lua'

        test_file_path = test_dir / test_file
        if not test_file_path.exists():
            return {
                'success': False,
                'test_name': test_name,
                'details': '',
                'cases': [],
                'elapsed': time.time() - start_time,
                'error': f'测试文件不存在: {test_file_path}',
                'failure_type': 'module_load_error',
            }

        # 4. 构建测试模块名（require 路径）
        test_module_base = test_file.replace('.lua', '')
        test_module = self.config.test_module_prefix + test_module_base if self.config.test_module_prefix else test_module_base

        # 5. 准备 desktop_bootstrap.lua 和插件产物
        wt_dir = test_dir / '_war3_tester'
        wt_dir.mkdir(parents=True, exist_ok=True)

        # 注入插件产物（jass_mock + assertions + desktop_bootstrap）
        self._inject_desktop_assets(wt_dir)

        # 6. 构建 lua 命令行
        # lua5.3 desktop_bootstrap.lua <test_module> <source_dir> <test_dir>
        # test_module: 测试模块全名（含 prefix，由 desktop_bootstrap.lua 通过 package.path 解析）
        # source_dir:  源码根目录（让项目点分 require 能相对此目录解析）
        # test_dir:    测试目录（让 _war3_tester/ 文件和裸名测试模块能相对此目录解析）
        desktop_bootstrap_path = wt_dir / 'desktop_bootstrap.lua'
        source_dir_str = str(resolved_source)
        test_dir_str = str(test_dir)

        # 7. 执行 lua 命令
        # 根据 config.is_wsl 选择执行路径
        if self.config.is_wsl:
            # WinProxyExecutor: 经 win_proxy 转发到 Windows 执行
            result = self._run_via_winproxy(lua_exe, desktop_bootstrap_path, test_module,
                                            source_dir_str, test_dir_str, timeout)
        else:
            # LocalExecutor: 直接 subprocess 执行
            result = self._run_via_subprocess(lua_exe, desktop_bootstrap_path, test_module,
                                              source_dir_str, test_dir_str, timeout)

        # 8. 解析结果
        elapsed = time.time() - start_time
        result['elapsed'] = elapsed

        return result

    def _inject_desktop_assets(self, wt_dir: Path) -> None:
        """注入桌面测试所需的插件产物到 _war3_tester/ 子目录"""
        assets = [
            ('jass_mock.lua', 'jass_mock'),
            ('assertions.lua', 'assertions'),
            ('desktop_bootstrap.lua', 'desktop_bootstrap'),
        ]
        server_dir = Path(__file__).parent
        for filename, label in assets:
            src = server_dir / filename
            dst = wt_dir / filename
            if src.exists():
                try:
                    with open(src, 'r', encoding='utf-8') as f:
                        content = f.read()
                    with open(dst, 'w', encoding='utf-8') as f:
                        f.write(content)
                    self.logger.debug(f"[desktop_runner] 已注入 {label} → {dst}")
                except (IOError, OSError) as e:
                    self.logger.warning(f"[desktop_runner] {label} 复制失败: {e}")
            else:
                self.logger.warning(f"[desktop_runner] 源文件不存在: {src}")

    def _run_via_subprocess(self, lua_exe: str, bootstrap_path: Path, test_module: str,
                            source_dir: str, test_dir: str, timeout: int) -> Dict[str, Any]:
        """
        通过 subprocess 直接执行 lua（LocalExecutor 路径）

        Args:
            lua_exe: lua 可执行文件路径
            bootstrap_path: desktop_bootstrap.lua 路径
            test_module: 测试模块全名（含 prefix）
            source_dir: 源码根目录绝对路径（传给 desktop_bootstrap.lua 配置 package.path）
            test_dir: 测试目录绝对路径（传给 desktop_bootstrap.lua 配置 package.path）
            timeout: 超时时间

        Returns:
            结果字典
        """
        try:
            # 构建命令：lua5.3 desktop_bootstrap.lua <test_module> <source_dir> <test_dir>
            cmd = [lua_exe, str(bootstrap_path), test_module, source_dir, test_dir]
            self.logger.info(f"[desktop_runner] 执行: {' '.join(cmd)}")

            # 工作目录设为 test_dir（package.path 已在 bootstrap 内配置，cwd 作为兜底）
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=test_dir,
                timeout=timeout,
            )

            stdout = proc.stdout
            stderr = proc.stderr

            # 解析 JSON 输出
            return self._parse_lua_output(stdout, stderr, proc.returncode)

        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'test_name': test_module,
                'details': '',
                'cases': [],
                'error': f'测试超时 ({timeout}s)',
                'failure_type': 'timeout',
            }
        except Exception as e:
            return {
                'success': False,
                'test_name': test_module,
                'details': '',
                'cases': [],
                'error': f'执行失败: {e}',
                'failure_type': 'runtime_error',
            }

    def _run_via_winproxy(self, lua_exe: str, bootstrap_path: Path, test_module: str,
                          source_dir: str, test_dir: str, timeout: int) -> Dict[str, Any]:
        """
        通过 win_proxy 转发执行 lua（WinProxyExecutor 路径）

        Args:
            lua_exe: lua 可执行文件路径
            bootstrap_path: desktop_bootstrap.lua 路径（WSL 路径）
            test_module: 测试模块全名（含 prefix）
            source_dir: 源码根目录绝对路径（WSL 路径，需转换为 Windows 路径）
            test_dir: 测试目录绝对路径（WSL 路径，需转换为 Windows 路径）
            timeout: 超时时间

        Returns:
            结果字典
        """
        from config import to_windows_path

        try:
            # 转换路径为 Windows 路径（win_proxy 在 Windows 侧执行 lua）
            win_bootstrap = to_windows_path(str(bootstrap_path))
            win_source_dir = to_windows_path(source_dir)
            win_test_dir = to_windows_path(test_dir)

            # 构建请求：lua5.3 desktop_bootstrap.lua <test_module> <source_dir> <test_dir>
            request = {
                'cmd': lua_exe,
                'args': [win_bootstrap, test_module, win_source_dir, win_test_dir],
                'cwd': win_test_dir,
                'timeout': timeout,
                'wait': True,
            }

            self.logger.info(f"[desktop_runner] 经 win_proxy 执行: {lua_exe} {win_bootstrap}")

            # 发送请求
            result = self.executor._send_tcp_request(request)

            if not result.get('success'):
                return {
                    'success': False,
                    'test_name': test_module,
                    'details': '',
                    'cases': [],
                    'error': f'win_proxy 执行失败: {result.get("error", "unknown")}',
                    'failure_type': 'runtime_error',
                }

            stdout = result.get('stdout', '')
            stderr = result.get('stderr', '')
            returncode = result.get('returncode', -1)

            return self._parse_lua_output(stdout, stderr, returncode)

        except Exception as e:
            return {
                'success': False,
                'test_name': test_module,
                'details': '',
                'cases': [],
                'error': f'win_proxy 执行异常: {e}',
                'failure_type': 'runtime_error',
            }

    def _parse_lua_output(self, stdout: str, stderr: str, returncode: int) -> Dict[str, Any]:
        """
        解析 lua 输出的 JSON 结果

        Args:
            stdout: lua 标准输出
            stderr: lua 标准错误
            returncode: 返回码

        Returns:
            结果字典
        """
        # 尝试从 stdout 解析 JSON
        try:
            # 查找最后一行 JSON（desktop_bootstrap.lua 输出格式）
            lines = stdout.strip().split('\n')
            json_line = None
            for line in reversed(lines):
                line = line.strip()
                if line.startswith('{') and line.endswith('}'):
                    json_line = line
                    break

            if json_line:
                result = json.loads(json_line)
                return {
                    'success': result.get('success', False),
                    'test_name': result.get('test_name', 'unknown'),
                    'details': result.get('details', ''),
                    'cases': result.get('cases', []),
                    'error': result.get('error'),
                    'failure_type': 'assertion' if not result.get('success') else None,
                }
        except json.JSONDecodeError as e:
            self.logger.warning(f"[desktop_runner] JSON 解析失败: {e}, stdout={stdout[:200]}")

        # 解析失败，根据 returncode 判断
        if returncode != 0:
            return {
                'success': False,
                'test_name': 'unknown',
                'details': stdout,
                'cases': [],
                'error': f'lua 执行失败 (returncode={returncode}): {stderr}',
                'failure_type': 'runtime_error',
            }
        else:
            # 成功但无 JSON 输出
            return {
                'success': True,
                'test_name': 'unknown',
                'details': stdout,
                'cases': [],
                'error': None,
                'failure_type': None,
            }
