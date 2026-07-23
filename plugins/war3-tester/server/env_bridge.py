#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
环境执行器桥接模块

抽象 WSL/原生 Windows 差异，提供统一的执行器接口：
- WinProxyExecutor: WSL 模式，经 TCP 8767 转发到 Windows win_proxy 执行
- LocalExecutor: 原生 Windows 模式，直接 subprocess 跑 exe

按 config.is_wsl() 自动选择执行器。
"""

import json
import socket
import struct
import time
import subprocess
import threading
import os
from pathlib import Path
from typing import Optional, List, Dict, Any

from config import Config, to_windows_path, is_port_available, find_available_port
from logger import setup_logger


def _check_war3_remaining(tasklist_stdout: str) -> dict:
    """
    共享：解析 tasklist /FO CSV 输出，检查 war3 相关进程残留。

    与 WinProxyExecutor.stop_game 的验证逻辑完全等价（单一来源）。
    返回：
      无残留 → {'success': True, 'message': '游戏进程已全部清除'}
      有残留 → {'success': False, 'message': '进程仍未清除：...', 'remaining': [...]}
    """
    # 防御 stdout=None：subprocess 在某些环境（疑似 Python 3.14）返回 stdout=None，
    # 不防御则 split crash 导致 stop_game 整体失败（尽管 powershell 杀进程已执行）
    lines = (tasklist_stdout or '').split('\n')
    remaining = []
    for line in lines:
        lower = line.lower()
        if any(x in lower for x in ['war3.exe', 'war3loader', 'kkwe.exe', 'ydwe.exe', 'frozen', 'warcraft iii']):
            remaining.append(line.strip())

    if remaining:
        return {
            'success': False,
            'message': f'进程仍未清除：{", ".join(remaining)}',
            'remaining': remaining
        }
    return {'success': True, 'message': '游戏进程已全部清除'}


class ExecutorBase:
    """执行器基类（接口定义）"""

    def execute(self, cmd: str, args: list = None, kwargs: dict = None,
                skip_policy: bool = False) -> dict:
        """
        通用命令执行

        Args:
            cmd: 命令名称（如 'w2l.exe', 'python3'）
            args: 参数列表
            kwargs: 关键字参数（如 {'cwd': '...', 'timeout': 60}）
            skip_policy: 是否跳过策略检查

        Returns:
            {'success': bool, ...} 结果字典
        """
        raise NotImplementedError

    def send_request(self, action: str, args: dict = None) -> dict:
        """发送请求（旧格式，向后兼容）"""
        raise NotImplementedError

    def require_proxy(self) -> dict:
        """检查执行器是否就绪"""
        raise NotImplementedError


class WinProxyExecutor(ExecutorBase):
    """
    WSL 模式执行器：通过 TCP 连接到 Windows win_proxy 代理执行命令

    协议：length-prefixed JSON（4 字节大端长度 + JSON 数据）
    端口：8767（与 win_proxy.py 保持一致）
    """

    def __init__(self, config: Config):
        self.config = config
        self.logger = setup_logger('win-proxy-executor')
        self.host = config.windows_to_wsl_ip if config.is_windows else config.wsl_to_windows_ip
        self.port = 8767
        self.timeout = 300
        self._detect_port_if_needed()

    def _detect_port_if_needed(self) -> None:
        """检测端口（多实例模式下自动查找可用端口）"""
        if self.config.multi_instance:
            available_port = find_available_port(
                self.config.service_port_min,
                self.config.service_port_max,
                self.host
            )
            if available_port and available_port != self.port:
                self.logger.info(f"多实例模式：使用端口 {available_port}")
                self.port = available_port
        else:
            if not is_port_available(self.port, self.host):
                self.logger.debug(f"端口 {self.port} 已被占用（服务运行中）")

    def require_proxy(self) -> dict:
        """强制检查 win_proxy 连接"""
        error_msg = (
            f"❌ win_proxy 未运行或无法连接 ({self.host}:{self.port})\n\n"
            "请在 Windows 环境下启动代理：\n"
            "  python win_proxy.py start"
        )
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            result = sock.connect_ex((self.host, self.port))
            sock.close()
            if result == 0:
                self.logger.info(f"✅ 代理连接检查通过 ({self.host}:{self.port})")
                return {'success': True}
            else:
                return {'success': False, 'error': error_msg}
        except Exception as e:
            self.logger.error(f"代理连接检查异常：{e}")
            return {'success': False, 'error': f'❌ win_proxy 连接检查失败：{e}\n\n{error_msg}'}

    def check_connectivity(self) -> bool:
        """检测代理是否就绪（3 秒超时）"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            result = sock.connect_ex((self.host, self.port))
            sock.close()
            return result == 0
        except Exception:
            return False

    def _send_tcp_request(self, request: dict, max_retries: int = 3) -> dict:
        """发送 TCP 请求到 Windows 服务（带重试机制）"""
        last_error = None

        for attempt in range(max_retries):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(self.timeout)
                sock.connect((self.host, self.port))

                data = json.dumps(request, ensure_ascii=False).encode('utf-8')
                sock.sendall(struct.pack('>I', len(data)) + data)

                length_data = b''
                while len(length_data) < 4:
                    chunk = sock.recv(4 - len(length_data))
                    if not chunk:
                        raise ConnectionError("连接中断")
                    length_data += chunk

                data_length = struct.unpack('>I', length_data)[0]

                response_data = b''
                while len(response_data) < data_length:
                    chunk = sock.recv(min(4096, data_length - len(response_data)))
                    if not chunk:
                        raise ConnectionError("连接中断")
                    response_data += chunk

                try:
                    response = json.loads(response_data.decode('utf-8'))
                except json.JSONDecodeError as e:
                    self.logger.error(f"JSON 解析错误：{e}")
                    return {
                        "success": False,
                        "error": f"JSON 解析错误：{e}",
                        "raw_response": response_data.decode('utf-8', errors='replace')
                    }

                sock.close()
                return response

            except socket.timeout:
                last_error = f"请求超时 ({self.timeout}秒)"
                self.logger.warning(f"第 {attempt + 1}/{max_retries} 次尝试失败：{last_error}")
            except ConnectionRefusedError:
                last_error = f"无法连接到 Windows 代理 ({self.host}:{self.port})"
                self.logger.warning(f"第 {attempt + 1}/{max_retries} 次尝试失败：连接被拒绝")
            except Exception as e:
                last_error = f"通信错误：{e}"
                self.logger.warning(f"第 {attempt + 1}/{max_retries} 次尝试失败：{last_error}", exc_info=True)

            if attempt < max_retries - 1:
                wait_time = 0.5 * (2 ** attempt)
                time.sleep(wait_time)

        return {"success": False, "error": f"经过 {max_retries} 次尝试都失败：{last_error}"}

    def send_request(self, action: str, args: dict = None) -> dict:
        """发送请求到 Windows 服务（旧格式）"""
        request = {"action": action, "args": args or {}}
        return self._send_tcp_request(request)

    def execute(self, cmd: str, args: list = None, kwargs: dict = None,
                skip_policy: bool = False) -> dict:
        """
        通用命令执行 - 通过 win_proxy 代理转发到 Windows 执行

        自动将 args/kwargs 中的 WSL 路径转换为 Windows 路径
        """
        if cmd.startswith('/mnt/'):
            cmd = to_windows_path(cmd)

        converted_args = []
        if args:
            for arg in args:
                if isinstance(arg, str) and arg.startswith('/mnt/'):
                    converted_args.append(to_windows_path(arg))
                else:
                    converted_args.append(arg)

        converted_kwargs = {}
        if kwargs:
            for key, value in kwargs.items():
                if isinstance(value, str) and value.startswith('/mnt/'):
                    converted_kwargs[key] = to_windows_path(value)
                else:
                    converted_kwargs[key] = value

        request = {"cmd": cmd, "args": converted_args}
        if converted_kwargs:
            request.update(converted_kwargs)
        if skip_policy:
            request["_internal"] = True

        self.logger.debug(f"[EXECUTE] 发送请求：{json.dumps(request, ensure_ascii=False)}")
        response = self._send_tcp_request(request)
        self.logger.debug(f"[EXECUTE] 收到响应：{json.dumps(response, ensure_ascii=False)[:500]}")
        return response

    def compile(self, source_dir: str = None) -> dict:
        """编译地图"""
        proxy_check = self.require_proxy()
        if not proxy_check.get('success'):
            return {
                'success': False,
                'error': f'❌ 编译操作必须通过 win_proxy 代理执行\n\n{proxy_check.get("error", "")}'
            }

        # 先确定实际项目目录（地图源码目录）
        if source_dir:
            src_dir = to_windows_path(source_dir) if source_dir.startswith('/mnt/') else source_dir
        else:
            src_dir = to_windows_path(str(self.config.compile_source_dir))

        # w2l.exe 按实际项目目录的相对位置查找（每个项目自带 w3x2lni/），
        # 找不到再回退到 Config 初始化时算出的 w2l_path
        w2l_found = self.config.find_w2l_exe(src_dir) or self.config.w2l_path
        if not w2l_found:
            return {
                'success': False,
                'error': f'未找到 w2l.exe：已按项目目录的相对位置（w3x2lni/、tools/w3x2lni/）查找\n'
                         f'并在项目目录内递归搜索（深度≤6）。项目目录：{src_dir}\n'
                         f'建议：在该项目目录下放置 w3x2lni/w2l.exe，或设置环境变量 W2L_PATH'
            }
        w2l_path = str(w2l_found)
        if not w2l_path.startswith(('D:', 'C:', 'E:')):
            w2l_path = to_windows_path(w2l_path)

        output_file = Path(to_windows_path(str(self.config.compile_output_path))) / self.config.compile_output_name
        win_output_file = str(output_file)

        request = {
            'cmd': w2l_path,
            'args': ['slk', src_dir, win_output_file],
            'cwd': src_dir,
            'timeout': 120,
            'wait': True,
        }
        compile_result = self._send_tcp_request(request)

        if not compile_result.get('success'):
            return {'success': False, 'error': f'编译失败：{compile_result.get("error", "unknown")}'}

        returncode = compile_result.get('returncode', -1)
        if returncode != 0:
            return {
                'success': False,
                'error': f'编译失败 (returncode={returncode})\nstdout: {compile_result.get("stdout", "")}\nstderr: {compile_result.get("stderr", "")}',
            }

        time.sleep(1)
        return {
            'success': True,
            'message': f'地图编译成功\n地图路径：{win_output_file}',
            'map_path': win_output_file,
            'stdout': compile_result.get('stdout', ''),
        }

    def run_game(self, map_path: str = None, platform: str = None) -> dict:
        """运行游戏"""
        proxy_check = self.require_proxy()
        if not proxy_check.get('success'):
            return {
                'success': False,
                'error': f'❌ 游戏操作必须通过 win_proxy 代理执行\n\n{proxy_check.get("error", "")}'
            }

        if not platform:
            platform_info = self.config.find_war3_platform()
            if platform_info:
                platform_path, platform_name = platform_info
            else:
                return {'success': False, 'error': '未找到 YDWE 或 KKWE 安装'}
        else:
            platform_info = self.config.find_war3_platform(platform, fallback=False)
            if not platform_info:
                return {'success': False, 'error': f'未找到 {platform} 平台'}
            platform_path, platform_name = platform_info

        if not map_path:
            map_path = str(self.config.compile_output_path / self.config.compile_output_name)
        win_map_path = to_windows_path(map_path) if map_path.startswith('/mnt/') else map_path

        if platform_name == 'KKWE':
            game_exe = str(platform_path / 'KKWE.exe')
        else:
            game_exe = str(platform_path / 'YDWE.exe')

        kwargs = {'cwd': str(platform_path), 'timeout': 10, 'wait': False}
        print(f'[LAUNCH] {game_exe} -war3 -loadfile {win_map_path}', flush=True)
        result = self.execute(game_exe, ['-war3', '-loadfile', win_map_path], kwargs=kwargs)
        return result

    def stop_game(self) -> dict:
        """停止游戏进程"""
        proxy_check = self.require_proxy()
        if not proxy_check.get('success'):
            return {
                'success': False,
                'error': f'❌ 停止游戏必须通过 win_proxy 代理执行\n\n{proxy_check.get("error", "")}'
            }

        ps_cmd = (
            'Stop-Process -Name War3 -Force -ErrorAction SilentlyContinue; '
            'Stop-Process -Name War3Loader -Force -ErrorAction SilentlyContinue; '
            'Stop-Process -Name KKWE -Force -ErrorAction SilentlyContinue; '
            'Stop-Process -Name YDWE -Force -ErrorAction SilentlyContinue; '
            'Stop-Process -Name "Frozen Throne" -Force -ErrorAction SilentlyContinue; '
            'Stop-Process -Name "Warcraft III" -Force -ErrorAction SilentlyContinue; '
            'echo Done'
        )
        result = self.execute('powershell.exe', ['-NoProfile', '-Command', ps_cmd], kwargs={'timeout': 10})

        verify = self.execute('tasklist.exe', ['/FO', 'CSV'], kwargs={'timeout': 10})
        return _check_war3_remaining(verify.get('stdout', ''))

    # 完整 VK 映射表（Win32 Virtual-Key Codes）
    VK_MAP = {
        # 原有 10 键（向后兼容）
        'enter': 0x0D, 'space': 0x20, 'escape': 0x1B,
        '1': 0x31, '2': 0x32, '3': 0x33, '4': 0x34, '5': 0x35,
        '6': 0x36, '7': 0x37, '8': 0x38, '9': 0x39, '0': 0x30,
        # 字母 A-Z
        'a': 0x41, 'b': 0x42, 'c': 0x43, 'd': 0x44, 'e': 0x45,
        'f': 0x46, 'g': 0x47, 'h': 0x48, 'i': 0x49, 'j': 0x4A,
        'k': 0x4B, 'l': 0x4C, 'm': 0x4D, 'n': 0x4E, 'o': 0x4F,
        'p': 0x50, 'q': 0x51, 'r': 0x52, 's': 0x53, 't': 0x54,
        'u': 0x55, 'v': 0x56, 'w': 0x57, 'x': 0x58, 'y': 0x59,
        'z': 0x5A,
        # 功能键 F1-F12
        'f1': 0x70, 'f2': 0x71, 'f3': 0x72, 'f4': 0x73,
        'f5': 0x74, 'f6': 0x75, 'f7': 0x76, 'f8': 0x77,
        'f9': 0x78, 'f10': 0x79, 'f11': 0x7A, 'f12': 0x7B,
        # 方向键
        'up': 0x26, 'down': 0x28, 'left': 0x25, 'right': 0x27,
        # 修饰键
        'shift': 0x10, 'ctrl': 0x11, 'alt': 0x12,
        'lshift': 0xA0, 'rshift': 0xA1,
        'lctrl': 0xA2, 'rctrl': 0xA3,
        'lalt': 0xA4, 'ralt': 0xA5,
        # 控制键
        'tab': 0x09, 'backspace': 0x08, 'delete': 0x2E,
        'insert': 0x2D, 'home': 0x24, 'end': 0x23,
        'pageup': 0x21, 'pagedown': 0x22,
        'capslock': 0x14, 'numlock': 0x90, 'scrolllock': 0x91,
        'printscreen': 0x2C, 'pause': 0x13,
        # 小键盘 0-9 及运算符
        'numpad0': 0x60, 'numpad1': 0x61, 'numpad2': 0x62,
        'numpad3': 0x63, 'numpad4': 0x64, 'numpad5': 0x65,
        'numpad6': 0x66, 'numpad7': 0x67, 'numpad8': 0x68,
        'numpad9': 0x69,
        'multiply': 0x6A, 'add': 0x6B, 'separator': 0x6C,
        'subtract': 0x6D, 'decimal': 0x6E, 'divide': 0x6F,
        # 其他
        'semicolon': 0xBA, 'equal': 0xBB, 'comma': 0xBC,
        'minus': 0xBD, 'period': 0xBE, 'slash': 0xBF,
        'grave': 0xC0, 'lbracket': 0xDB, 'backslash': 0xDC,
        'rbracket': 0xDD, 'apostrophe': 0xDE,
    }

    # 修饰键集合（用于组合键时序判断）
    MODIFIER_KEYS = {'shift', 'ctrl', 'alt', 'lshift', 'rshift', 'lctrl', 'rctrl', 'lalt', 'ralt'}

    def send_key(self, key: str) -> dict:
        """
        向 War3 窗口发送键盘事件。

        支持单键和组合键：
        - 单键: "enter", "a", "f1", "up" 等
        - 组合键: "ctrl+c", "shift+a", "alt+f4", "ctrl+shift+s" 等
          格式: 修饰键+主键（+ 分隔），支持多修饰键
        """
        proxy_check = self.require_proxy()
        if not proxy_check.get('success'):
            return {
                'success': False,
                'error': f'❌ 键盘事件必须通过 win_proxy 代理执行\n\n{proxy_check.get("error", "")}'
            }

        key_lower = key.lower().strip()

        # 解析组合键（+ 分隔）
        if '+' in key_lower:
            parts = [p.strip() for p in key_lower.split('+') if p.strip()]
            if len(parts) < 2:
                return {'success': False, 'error': f'组合键格式错误：{key}'}

            # 分离修饰键和主键
            modifiers = []
            main_key = None
            for p in parts:
                if p in self.MODIFIER_KEYS:
                    modifiers.append(p)
                else:
                    if main_key is not None:
                        return {'success': False, 'error': f'组合键只能有一个主键：{key}'}
                    main_key = p

            if main_key is None:
                return {'success': False, 'error': f'组合键缺少主键：{key}'}

            # 解析所有 VK
            vk_list = []
            for m in modifiers:
                vk = self.VK_MAP.get(m)
                if vk is None:
                    return {'success': False, 'error': f'不支持的修饰键：{m}'}
                vk_list.append(vk)
            main_vk = self.VK_MAP.get(main_key)
            if main_vk is None:
                return {'success': False, 'error': f'不支持的按键：{main_key}'}
            vk_list.append(main_vk)

            # 传 VK 列表给 win_proxy（组合键模式）
            return self.execute('__send_key__', [vk_list], kwargs={'timeout': 5})
        else:
            # 单键模式（向后兼容）
            vk = self.VK_MAP.get(key_lower)
            if vk is None:
                return {'success': False, 'error': f'不支持的按键：{key}'}
            return self.execute('__send_key__', [vk], kwargs={'timeout': 5})

    def take_screenshot(self, test_name: str, filename: str = None, window_title: str = None) -> dict:
        """
        通过 Python + Win32 API 执行截图（WSL 模式经 win_proxy 转发）

        【F1 修复】从基线 take_screenshot_via_powershell 提取，改用 Python 脚本避免 PowerShell 命令行长度问题

        Args:
            test_name: 测试名称
            filename: 文件名（可选）
            window_title: 窗口标题关键词（可选，为 None 时截取全屏）

        Returns:
            执行结果字典，包含 path_wsl 字段
        """
        if not filename:
            filename = f"screenshot_{int(time.time())}.png"

        # Windows 侧截图保存路径（基于项目根目录动态构建）
        win_project_root = to_windows_path(str(self.config.project_root))
        win_screenshots_dir = rf"{win_project_root}\logs\screenshots\{test_name}"
        win_screenshot_path = rf"{win_screenshots_dir}\{filename}"

        # WSL 侧截图保存路径
        wsl_screenshots_dir = str(self.config.project_root / 'logs' / 'screenshots' / test_name)
        wsl_screenshot_path = f"{wsl_screenshots_dir}/{filename}"

        # 确保 WSL 侧目录存在
        from pathlib import Path
        Path(wsl_screenshots_dir).mkdir(parents=True, exist_ok=True)

        # 构建 Python 截图脚本（从基线提取）
        python_script = f'''
import ctypes
from ctypes import wintypes
import time
import os

# Win32 API
user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

# 查找窗口
keywords = ['{window_title or ""}', '魔兽', 'Warcraft', 'War3', 'YDWE', 'KK', '争霸']
found_hwnd = None
found_title = ""

# 回调函数类型
EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

class RECT(ctypes.Structure):
    _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG),
                ("right", wintypes.LONG), ("bottom", wintypes.LONG)]

def enum_callback(hwnd, lparam):
    global found_hwnd, found_title
    if user32.IsWindowVisible(hwnd):
        text = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, text, 256)
        title = text.value
        if title:
            for kw in keywords:
                if kw and kw.lower() in title.lower():
                    found_hwnd = hwnd
                    found_title = title
                    return False
    return True

# 枚举窗口
callback = EnumWindowsProc(enum_callback)
user32.EnumWindows(callback, 0)

if found_hwnd is None:
    print("未找到 War3 窗口")
    exit(1)

print(f"找到窗口: {{found_title}}")

# 获取窗口矩形
rect = RECT()
user32.GetWindowRect(found_hwnd, ctypes.byref(rect))
width = rect.right - rect.left
height = rect.bottom - rect.top

if width <= 0 or height <= 0:
    print("窗口尺寸无效")
    exit(1)

# 截图 - 使用 PrintWindow 捕获 DirectX 渲染窗口
# 创建目录
os.makedirs(r'{win_screenshots_dir}', exist_ok=True)

# 创建兼容 DC 和位图
hdc_screen = user32.GetDC(0)
hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
hbmp = gdi32.CreateCompatibleBitmap(hdc_screen, width, height)
gdi32.SelectObject(hdc_mem, hbmp)

# PrintWindow 可以捕获 DirectX/OpenGL 渲染的窗口
# PW_RENDERFULLCONTENT = 0x00000002
PW_RENDERFULLCONTENT = 0x00000002
result = user32.PrintWindow(found_hwnd, hdc_mem, PW_RENDERFULLCONTENT)
if result == 0:
    # 如果 PrintWindow 失败，回退到 BitBlt
    SRCCOPY = 0x00CC0020
    gdi32.BitBlt(hdc_mem, 0, 0, width, height, hdc_screen, rect.left, rect.top, SRCCOPY)

# 使用 GetDIBits 获取像素数据
class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD),
                ("biWidth", wintypes.LONG),
                ("biHeight", wintypes.LONG),
                ("biPlanes", wintypes.WORD),
                ("biBitCount", wintypes.WORD),
                ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD),
                ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG),
                ("biClrUsed", wintypes.DWORD),
                ("biClrImportant", wintypes.DWORD)]

class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER),
                ("bmiColors", wintypes.DWORD * 3)]

bmi = BITMAPINFO()
bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
bmi.bmiHeader.biWidth = width
bmi.bmiHeader.biHeight = -height
bmi.bmiHeader.biPlanes = 1
bmi.bmiHeader.biBitCount = 24
bmi.bmiHeader.biCompression = 0

pixels = (ctypes.c_byte * (width * height * 3))()
gdi32.GetDIBits(hdc_mem, hbmp, 0, height, pixels, ctypes.byref(bmi), 0)

# 保存为 PNG
from PIL import Image
img = Image.frombytes('RGB', (width, height), bytes(pixels))
img.save(r'{win_screenshot_path}')

# 清理
gdi32.DeleteObject(hbmp)
gdi32.DeleteDC(hdc_mem)
user32.ReleaseDC(0, hdc_screen)

print(f"截图已保存: {win_screenshot_path.replace(chr(92), '/')}")
'''

        # 将 Python 脚本写入临时文件（基于项目根目录动态构建）
        ts = int(time.time())
        win_project_root = to_windows_path(str(self.config.project_root))
        py_temp_path_win = rf"{win_project_root}\logs\screenshot_{ts}.py"
        py_temp_path_wsl = str(self.config.project_root / 'logs' / f"screenshot_{ts}.py")

        with open(py_temp_path_wsl, 'w', encoding='utf-8') as f:
            f.write(python_script)

        # 执行 Python 截图脚本
        screenshot_cmd = {
            'cmd': 'python.exe',
            'args': [py_temp_path_win],
            'timeout': 30,
            'wait': True,
        }
        result = self._send_tcp_request(screenshot_cmd)

        # 清理临时文件
        try:
            os.unlink(py_temp_path_wsl)
        except OSError:
            pass  # 临时文件可能已被清理

        if result.get('success'):
            # 验证文件是否生成（通过 PowerShell 检查，比 cmd.exe 更可靠）
            check_cmd = {
                'cmd': 'powershell.exe',
                'args': ['-NoProfile', '-Command', f'Test-Path "{win_screenshot_path}"'],
                'timeout': 5,
                'wait': True,
            }
            check_result = self._send_tcp_request(check_cmd)

            if 'True' in check_result.get('stdout', ''):
                return {
                    'success': True,
                    'message': '截图已保存',
                    'path': win_screenshot_path,
                    'path_wsl': wsl_screenshot_path,
                    'test_name': test_name,
                    'filename': filename,
                }
            else:
                return {
                    'success': False,
                    'error': f'截图文件未生成：{win_screenshot_path}',
                }
        else:
            error_msg = result.get('stderr', result.get('error', '截图失败'))
            self.logger.error(f"截图失败: {error_msg}, result={result}")
            return {
                'success': False,
                'error': error_msg,
            }


class LocalExecutor(ExecutorBase):
    """
    原生 Windows 模式执行器：直接 subprocess 跑 exe

    用于非 WSL 环境（纯 Windows 或其他可直接执行的平台）
    """

    def __init__(self, config: Config):
        self.config = config
        self.logger = setup_logger('local-executor')

    def require_proxy(self) -> dict:
        """本地执行器不需要代理"""
        return {'success': True}

    def check_connectivity(self) -> bool:
        """本地执行器始终可用"""
        return True

    def send_request(self, action: str, args: dict = None) -> dict:
        """本地执行器不支持旧格式请求（仅 win_proxy 协议需要）"""
        return {'success': False, 'error': '本地执行器不支持旧格式请求，请使用 execute()'}

    def execute(self, cmd: str, args: list = None, kwargs: dict = None,
                skip_policy: bool = False) -> dict:
        """直接 subprocess 执行命令"""
        full_cmd = [cmd] + (args or [])
        kwargs = kwargs or {}
        cwd = kwargs.get('cwd')
        timeout = kwargs.get('timeout', 300)
        wait = kwargs.get('wait', True)

        self.logger.debug(f"[EXECUTE] {full_cmd}, cwd={cwd}, wait={wait}")

        if wait:
            try:
                proc = subprocess.run(
                    full_cmd,
                    capture_output=True,
                    text=True,
                    cwd=cwd,
                    timeout=timeout,
                )
                return {
                    'success': proc.returncode == 0,
                    'returncode': proc.returncode,
                    # or '' 防御 stdout/stderr=None（Python 3.14 嫌疑），从源头保证调用者拿 str
                    'stdout': proc.stdout or '',
                    'stderr': proc.stderr or '',
                }
            except subprocess.TimeoutExpired:
                return {'success': False, 'error': f'命令超时 ({timeout}s)'}
            except Exception as e:
                return {'success': False, 'error': f'执行失败：{e}'}
        else:
            try:
                proc = subprocess.Popen(
                    full_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=cwd,
                )
                return {
                    'success': True,
                    'pid': proc.pid,
                    'message': f'进程已启动 (PID={proc.pid})',
                }
            except Exception as e:
                return {'success': False, 'error': f'启动失败：{e}'}

    def compile(self, source_dir: str = None) -> dict:
        """编译地图"""
        src_dir = str(source_dir or self.config.compile_source_dir)

        # w2l.exe 按实际项目目录的相对位置查找，找不到再回退到 Config 初始化值
        w2l_found = self.config.find_w2l_exe(src_dir) or self.config.w2l_path
        if not w2l_found:
            return {'success': False, 'error': f'未找到 w2l.exe（已按项目目录 {src_dir} 的相对位置查找）'}

        w2l_path = str(w2l_found)
        output_file = Path(self.config.compile_output_path) / self.config.compile_output_name

        result = self.execute(w2l_path, ['slk', src_dir, str(output_file)],
                              kwargs={'cwd': src_dir, 'timeout': 120, 'wait': True})
        if not result.get('success'):
            return {'success': False, 'error': f'编译失败：{result.get("error", "unknown")}'}

        returncode = result.get('returncode', -1)
        if returncode != 0:
            return {
                'success': False,
                'error': f'编译失败 (returncode={returncode})\nstdout: {result.get("stdout", "")}\nstderr: {result.get("stderr", "")}',
            }

        time.sleep(1)
        return {
            'success': True,
            'message': f'地图编译成功\n地图路径：{output_file}',
            'map_path': str(output_file),
            'stdout': result.get('stdout', ''),
        }

    def run_game(self, map_path: str = None, platform: str = None) -> dict:
        """运行游戏"""
        if not platform:
            platform_info = self.config.find_war3_platform()
            if platform_info:
                platform_path, platform_name = platform_info
            else:
                return {'success': False, 'error': '未找到 YDWE 或 KKWE 安装'}
        else:
            platform_info = self.config.find_war3_platform(platform, fallback=False)
            if not platform_info:
                return {'success': False, 'error': f'未找到 {platform} 平台'}
            platform_path, platform_name = platform_info

        if not map_path:
            map_path = str(self.config.compile_output_path / self.config.compile_output_name)

        if platform_name == 'KKWE':
            game_exe = str(platform_path / 'KKWE.exe')
        else:
            game_exe = str(platform_path / 'YDWE.exe')

        return self.execute(game_exe, ['-war3', '-loadfile', map_path],
                            kwargs={'cwd': str(platform_path), 'timeout': 10, 'wait': False})

    def stop_game(self) -> dict:
        """停止游戏进程"""
        try:
            if self.config.is_windows:
                ps_cmd = (
                    'Stop-Process -Name War3 -Force -ErrorAction SilentlyContinue; '
                    'Stop-Process -Name War3Loader -Force -ErrorAction SilentlyContinue; '
                    'Stop-Process -Name KKWE -Force -ErrorAction SilentlyContinue; '
                    'Stop-Process -Name YDWE -Force -ErrorAction SilentlyContinue; '
                    'Stop-Process -Name "Frozen Throne" -Force -ErrorAction SilentlyContinue; '
                    'Stop-Process -Name "Warcraft III" -Force -ErrorAction SilentlyContinue; '
                    'echo Done'
                )
                result = self.execute('powershell.exe', ['-NoProfile', '-Command', ps_cmd],
                                      kwargs={'timeout': 10})

                # 杀后验证：tasklist 复查残留（对齐 WinProxy 行为）
                verify = self.execute('tasklist.exe', ['/FO', 'CSV'], kwargs={'timeout': 10})
                return _check_war3_remaining(verify.get('stdout', ''))
            else:
                # Linux/Mac 下尝试 pkill
                result = self.execute('pkill', ['-f', 'war3|KKWE|YDWE'], kwargs={'timeout': 10})

            return {'success': True, 'message': '游戏进程清理完成'}
        except Exception as e:
            return {'success': False, 'error': f'停止游戏失败：{e}'}

    def send_key(self, key: str) -> dict:
        """
        本地执行器 send_key（Windows 原生模式，ctypes 直接调 Win32 API）

        支持单键和组合键：
        - 单键: "enter", "a", "f1", "up" 等
        - 组合键: "ctrl+c", "shift+a", "alt+f4", "ctrl+shift+s" 等

        VK_MAP / MODIFIER_KEYS 复用 WinProxyExecutor（单一来源，不重复定义）
        """
        try:
            import ctypes
            from ctypes import wintypes
        except ImportError:
            return {'success': False, 'error': 'ctypes 不可用（非 Windows 环境？）'}

        # 复用 WinProxyExecutor 的 VK 表（单一来源）
        VK_MAP = WinProxyExecutor.VK_MAP
        MODIFIER_KEYS = WinProxyExecutor.MODIFIER_KEYS

        WM_KEYDOWN = 0x0100
        WM_KEYUP = 0x0101

        key_lower = key.lower().strip()

        # 解析组合键（+ 分隔）
        if '+' in key_lower:
            parts = [p.strip() for p in key_lower.split('+') if p.strip()]
            if len(parts) < 2:
                return {'success': False, 'error': f'组合键格式错误：{key}'}

            # 分离修饰键和主键
            modifiers = []
            main_key = None
            for p in parts:
                if p in MODIFIER_KEYS:
                    modifiers.append(p)
                else:
                    if main_key is not None:
                        return {'success': False, 'error': f'组合键只能有一个主键：{key}'}
                    main_key = p

            if main_key is None:
                return {'success': False, 'error': f'组合键缺少主键：{key}'}

            # 解析所有 VK
            vk_list = []
            for m in modifiers:
                vk = VK_MAP.get(m)
                if vk is None:
                    return {'success': False, 'error': f'不支持的修饰键：{m}'}
                vk_list.append(vk)
            main_vk = VK_MAP.get(main_key)
            if main_vk is None:
                return {'success': False, 'error': f'不支持的按键：{main_key}'}
            vk_list.append(main_vk)
        else:
            # 单键模式
            vk = VK_MAP.get(key_lower)
            if vk is None:
                return {'success': False, 'error': f'不支持的按键：{key}'}
            vk_list = None  # 标记为单键
            main_vk = vk

        # 查找 War3 窗口
        try:
            user32 = ctypes.windll.user32
        except Exception as e:
            return {'success': False, 'error': f'无法加载 user32.dll: {e}'}

        EnumWindowsProc = ctypes.WINFUNCTYPE(
            wintypes.BOOL, wintypes.HWND, wintypes.LPARAM
        )

        keywords = ['魔兽', 'Warcraft', 'War3', 'YDWE', 'KK', '争霸']
        found_hwnd = None

        def enum_callback(hwnd, lparam):
            nonlocal found_hwnd
            if user32.IsWindowVisible(hwnd):
                text = ctypes.create_unicode_buffer(256)
                user32.GetWindowTextW(hwnd, text, 256)
                title = text.value
                if title:
                    for kw in keywords:
                        if kw.lower() in title.lower():
                            found_hwnd = hwnd
                            return False
            return True

        callback = EnumWindowsProc(enum_callback)
        user32.EnumWindows(callback, 0)

        if found_hwnd is None:
            return {'success': False, 'error': '未找到 War3 窗口'}

        # 激活窗口
        try:
            user32.ShowWindow(found_hwnd, 9)  # SW_RESTORE
            user32.SetForegroundWindow(found_hwnd)
            time.sleep(0.1)
        except Exception:
            pass  # 窗口激活失败不致命，继续尝试发送

        try:
            if vk_list is not None:
                # 组合键模式：修饰键 DOWN(正序) → 主键 DOWN → 主键 UP → 修饰键 UP(反序)
                modifiers_vk = vk_list[:-1]
                main_vk_val = vk_list[-1]

                for vk in modifiers_vk:
                    user32.PostMessageA(found_hwnd, WM_KEYDOWN, vk, 0)
                    time.sleep(0.02)
                user32.PostMessageA(found_hwnd, WM_KEYDOWN, main_vk_val, 0)
                time.sleep(0.02)
                user32.PostMessageA(found_hwnd, WM_KEYUP, main_vk_val, 0)
                time.sleep(0.02)
                for vk in reversed(modifiers_vk):
                    user32.PostMessageA(found_hwnd, WM_KEYUP, vk, 0)
                    time.sleep(0.02)

                return {'success': True, 'message': f'已发送组合键 VK={vk_list}'}
            else:
                # 单键模式（向后兼容）
                user32.PostMessageA(found_hwnd, WM_KEYDOWN, main_vk, 0)
                time.sleep(0.05)
                user32.PostMessageA(found_hwnd, WM_KEYUP, main_vk, 0)
                return {'success': True, 'message': f'已发送按键 VK={main_vk}'}
        except Exception as e:
            return {'success': False, 'error': f'按键发送异常: {e}'}

    def take_screenshot(self, test_name: str, filename: str = None, window_title: str = None) -> dict:
        """
        本地执行器截图（原生 Windows 模式，直接 subprocess 跑 Python 脚本）

        Args:
            test_name: 测试名称
            filename: 文件名（可选）
            window_title: 窗口标题关键词（可选）

        Returns:
            执行结果字典
        """
        if not filename:
            filename = f"screenshot_{int(time.time())}.png"

        # 截图保存路径
        screenshots_dir = self.config.project_root / 'logs' / 'screenshots' / test_name
        screenshots_dir.mkdir(parents=True, exist_ok=True)
        screenshot_path = screenshots_dir / filename

        # 构建 Python 截图脚本（从基线提取，简化版）
        python_script = f'''
import ctypes
from ctypes import wintypes
import os

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

keywords = ['{window_title or ""}', '魔兽', 'Warcraft', 'War3', 'YDWE', 'KK', '争霸']
found_hwnd = None
found_title = ""

EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

class RECT(ctypes.Structure):
    _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG),
                ("right", wintypes.LONG), ("bottom", wintypes.LONG)]

def enum_callback(hwnd, lparam):
    global found_hwnd, found_title
    if user32.IsWindowVisible(hwnd):
        text = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, text, 256)
        title = text.value
        if title:
            for kw in keywords:
                if kw and kw.lower() in title.lower():
                    found_hwnd = hwnd
                    found_title = title
                    return False
    return True

callback = EnumWindowsProc(enum_callback)
user32.EnumWindows(callback, 0)

if found_hwnd is None:
    print("未找到 War3 窗口")
    exit(1)

rect = RECT()
user32.GetWindowRect(found_hwnd, ctypes.byref(rect))
width = rect.right - rect.left
height = rect.bottom - rect.top

if width <= 0 or height <= 0:
    print("窗口尺寸无效")
    exit(1)

os.makedirs(r'{str(screenshots_dir)}', exist_ok=True)

hdc_screen = user32.GetDC(0)
hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
hbmp = gdi32.CreateCompatibleBitmap(hdc_screen, width, height)
gdi32.SelectObject(hdc_mem, hbmp)

PW_RENDERFULLCONTENT = 0x00000002
result = user32.PrintWindow(found_hwnd, hdc_mem, PW_RENDERFULLCONTENT)
if result == 0:
    SRCCOPY = 0x00CC0020
    gdi32.BitBlt(hdc_mem, 0, 0, width, height, hdc_screen, rect.left, rect.top, SRCCOPY)

class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG), ("biYPelsPerMeter", wintypes.LONG),
                ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]

class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]

bmi = BITMAPINFO()
bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
bmi.bmiHeader.biWidth = width
bmi.bmiHeader.biHeight = -height
bmi.bmiHeader.biPlanes = 1
bmi.bmiHeader.biBitCount = 24
bmi.bmiHeader.biCompression = 0

pixels = (ctypes.c_byte * (width * height * 3))()
gdi32.GetDIBits(hdc_mem, hbmp, 0, height, pixels, ctypes.byref(bmi), 0)

from PIL import Image
img = Image.frombytes('RGB', (width, height), bytes(pixels))
img.save(r'{str(screenshot_path)}')

gdi32.DeleteObject(hbmp)
gdi32.DeleteDC(hdc_mem)
user32.ReleaseDC(0, hdc_screen)

print(f"截图已保存: {str(screenshot_path).replace(chr(92), '/')}")
'''

        # 写入临时文件并执行
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write(python_script)
            py_temp_path = f.name

        try:
            result = self.execute('python.exe', [py_temp_path], kwargs={'timeout': 30, 'wait': True})

            if result.get('success') and screenshot_path.exists():
                return {
                    'success': True,
                    'message': '截图已保存',
                    'path': str(screenshot_path),
                    'path_wsl': str(screenshot_path),
                    'test_name': test_name,
                    'filename': filename,
                }
            else:
                error_msg = result.get('stderr', result.get('error', '截图失败'))
                return {'success': False, 'error': error_msg}
        finally:
            try:
                os.unlink(py_temp_path)
            except OSError:
                pass


def create_executor(config: Config) -> ExecutorBase:
    """
    工厂函数：根据 config.is_wsl() 创建对应的执行器

    Returns:
        WinProxyExecutor (WSL 模式) 或 LocalExecutor (原生 Windows 模式)
    """
    if config.is_wsl:
        return WinProxyExecutor(config)
    else:
        return LocalExecutor(config)
