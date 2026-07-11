# -*- coding: utf-8 -*-
# VERSION: 2025-06-10-v7  # 使用 Popen + text=True
"""
Windows 命令代理 - 极简 TCP 命令转发器

接收 WSL 发来的命令，在 Windows 原生环境执行，返回结果。
无任何硬编码业务逻辑，纯粹的执行器。

启动（Windows CMD/PowerShell）:
    python win_proxy.py start

停止:
    python win_proxy.py stop
"""

import sys
import os
import json
import socket
import struct
import time
import subprocess
import threading
from pathlib import Path

HOST = '0.0.0.0'  # 监听所有网卡，允许 WSL 连接
PORT = 8767  # 使用 8767 避免与 Trae IDE 等工具的 8765 端口冲突
PID_FILE = Path(__file__).parent / '.win_proxy.pid'


def _kill_process_tree(pid: int) -> None:
    """在 Windows 上杀死进程树（包括所有子进程）。"""
    try:
        subprocess.run(
            ['taskkill', '/F', '/T', '/PID', str(pid)],
            capture_output=True,
            timeout=10,
        )
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, OSError):
        pass  # 进程可能已退出


def handle_client(conn, addr):
    """处理单个客户端连接"""
    try:
        # 读取命令长度 (4 字节大端)
        length_data = b''
        while len(length_data) < 4:
            chunk = conn.recv(4 - len(length_data))
            if not chunk:
                return
            length_data += chunk

        data_length = struct.unpack('>I', length_data)[0]

        # 读取命令数据
        data = b''
        while len(data) < data_length:
            chunk = conn.recv(min(8192, data_length - len(data)))
            if not chunk:
                return
            data += chunk

        cmd = json.loads(data.decode('utf-8'))

        # 执行命令
        executable = cmd['cmd']
        args = cmd.get('args', [])
        cwd = cmd.get('cwd')
        timeout = cmd.get('timeout', 300)
        wait = cmd.get('wait', True)

        # 简化日志：只显示关键信息
        cmd_short = executable.split('\\')[-1].split('/')[-1]  # 只显示文件名
        print(f'> [{time.strftime("%H:%M:%S")}] {cmd_short} {"(async)" if not wait else "(sync)"}', flush=True)
        print(f'  cmd: {executable}', flush=True)
        print(f'  args: {args}', flush=True)
        print(f'  cwd: {cwd}', flush=True)
        print(f'  timeout: {timeout}, wait: {wait}', flush=True)

        # 内置命令：send_key（用 ctypes 直接调用 Win32 API，不需要 PowerShell）
        # 支持单键（args=[vk_int]）和组合键（args=[[vk1, vk2, ...]]）
        # 组合键时序：修饰键 DOWN → 主键 DOWN → 主键 UP → 修饰键 UP（反序）
        if executable == '__send_key__':
            import ctypes
            from ctypes import wintypes
            vk_arg = args[0] if args else 0
            WM_KEYDOWN = 0x0100
            WM_KEYUP = 0x0101
            user32 = ctypes.windll.user32

            # EnumWindows 回调类型
            EnumWindowsProc = ctypes.WINFUNCTYPE(
                wintypes.BOOL, wintypes.HWND, wintypes.LPARAM
            )

            # 关键词匹配 War3 窗口（与截图逻辑一致）
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
                response = {'success': False, 'error': '未找到 War3 窗口'}
            elif isinstance(vk_arg, list):
                # 组合键模式：args = [[vk_modifier1, vk_modifier2, ..., vk_main]]
                try:
                    vk_list = [int(v) for v in vk_arg]
                    if len(vk_list) < 2:
                        response = {'success': False, 'error': f'组合键至少需要 2 个 VK，实际 {len(vk_list)}'}
                    else:
                        user32.ShowWindow(found_hwnd, 9)
                        user32.SetForegroundWindow(found_hwnd)
                        time.sleep(0.1)
                        modifiers = vk_list[:-1]
                        main_vk = vk_list[-1]
                        # 修饰键按下（正序）
                        for vk in modifiers:
                            user32.PostMessageA(found_hwnd, WM_KEYDOWN, vk, 0)
                            time.sleep(0.02)
                        # 主键按下
                        user32.PostMessageA(found_hwnd, WM_KEYDOWN, main_vk, 0)
                        time.sleep(0.02)
                        # 主键抬起
                        user32.PostMessageA(found_hwnd, WM_KEYUP, main_vk, 0)
                        time.sleep(0.02)
                        # 修饰键抬起（反序）
                        for vk in reversed(modifiers):
                            user32.PostMessageA(found_hwnd, WM_KEYUP, vk, 0)
                            time.sleep(0.02)
                        response = {'success': True, 'message': f'已发送组合键 VK={vk_list}'}
                except Exception as e:
                    response = {'success': False, 'error': f'组合键发送异常: {e}'}
            else:
                # 单键模式（向后兼容，与 0.7.0 行为完全一致）
                vk = int(vk_arg)
                user32.ShowWindow(found_hwnd, 9)
                user32.SetForegroundWindow(found_hwnd)
                time.sleep(0.1)
                user32.PostMessageA(found_hwnd, WM_KEYDOWN, vk, 0)
                time.sleep(0.05)
                user32.PostMessageA(found_hwnd, WM_KEYUP, vk, 0)
                response = {'success': True, 'message': f'已发送按键 VK={vk}'}
        else:
            full_cmd = [executable] + args

            if wait:
                try:
                    print(f'  [DEBUG] run: {full_cmd}, cwd={cwd}', flush=True)

                    # 使用 PIPE 但要正确处理
                    proc = subprocess.Popen(
                        full_cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        cwd=cwd,
                        shell=False,  # 禁止 shell=True，避免命令注入
                        text=True,  # 直接返回字符串
                    )
                    print(f'  [DEBUG] Popen created, pid={proc.pid}', flush=True)

                    try:
                        stdout, stderr = proc.communicate(timeout=timeout)
                        print(f'  [DEBUG] communicate done', flush=True)
                        response = {
                            'success': proc.returncode == 0,
                            'returncode': proc.returncode,
                            'stdout': stdout,
                            'stderr': stderr,
                        }
                    except subprocess.TimeoutExpired:
                        _kill_process_tree(proc.pid)
                        proc.communicate()
                        response = {
                            'success': False,
                            'error': f'命令超时 ({timeout}s)',
                        }
                except Exception as e:
                    import traceback
                    error_msg = f'{type(e).__name__}: {e}\n{traceback.format_exc()}'
                    print(f'  [ERROR] {error_msg}', flush=True)
                    response = {
                        'success': False,
                        'error': error_msg,
                    }
            else:
                # 异步启动，不等待（与原服务完全一致）
                print(f'  [DEBUG] 异步启动模式', flush=True)
                kwargs_popen = {}
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 1  # SW_SHOWNORMAL - 显示窗口
                kwargs_popen['startupinfo'] = startupinfo
                kwargs_popen['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP

                # 不设置自定义 env，让子进程继承完整的默认环境
                # 修复：使用自定义 env 可能导致 DirectX 初始化失败
                # （缺少交互式会话中的某些环境变量）
                # if cwd:
                #     env = os.environ.copy()
                #     env['PATH'] = cwd + ';' + env.get('PATH', '')
                #     kwargs_popen['env'] = env
                #     print(f'  [DEBUG] 已设置 PATH: {cwd} 添加到 PATH', flush=True)

                try:
                    proc = subprocess.Popen(full_cmd, cwd=cwd, shell=False, **kwargs_popen)
                    print(f'  [DEBUG] 进程已启动 PID={proc.pid}', flush=True)
                    response = {
                        'success': True,
                        'pid': proc.pid,
                        'message': f'异步启动成功 PID={proc.pid}',
                    }
                except Exception as e:
                    print(f'  [ERROR] 启动失败: {e}', flush=True)
                    response = {
                        'success': False,
                        'error': f'启动失败: {e}',
                    }

        # 发送响应
        resp_data = json.dumps(response, ensure_ascii=False).encode('utf-8')
        print(f'  [DEBUG] 返回响应: {resp_data.decode("utf-8", errors="replace")[:200]}', flush=True)
        conn.sendall(struct.pack('>I', len(resp_data)) + resp_data)

    except Exception as e:
        resp = json.dumps({'success': False, 'error': str(e)})
        conn.sendall(struct.pack('>I', len(resp)) + resp.encode())
    finally:
        conn.close()


def start_server():
    """启动 TCP 服务"""
    # 先检查是否有残留进程
    if PID_FILE.exists():
        old_pid = int(PID_FILE.read_text().strip())
        try:
            # Windows: os.kill(pid, 0) 可以检测进程是否存在
            os.kill(old_pid, 0)
            print(f'[ERROR] 代理已在运行 (PID={old_pid})，请先执行 stop')
            sys.exit(1)
        except OSError:
            # 进程已不存在，清理残留 PID 文件
            print(f'[INFO] 清理残留 PID 文件 (旧进程 {old_pid} 已退出)')
            PID_FILE.unlink(missing_ok=True)

    # 先绑定端口，成功后再写 PID 文件（避免绑定失败留下脏文件）
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server.bind((HOST, PORT))
    except OSError as e:
        server.close()
        print(f'[ERROR] 端口 {PORT} 绑定失败: {e}')
        print(f'        可能原因: 端口被占用或被 Windows 保留')
        print(f'        排查: netstat -ano | findstr :{PORT}')
        sys.exit(1)
    server.listen(5)

    # 绑定成功后才写 PID 文件
    PID_FILE.write_text(str(os.getpid()))
    print(f'Windows 代理已启动，监听 {HOST}:{PORT}, PID={os.getpid()}')

    try:
        while True:
            conn, addr = server.accept()
            t = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
            t.start()
    except KeyboardInterrupt:
        pass
    finally:
        server.close()
        PID_FILE.unlink(missing_ok=True)
        print('代理已停止')


def stop_server():
    """停止服务"""
    if PID_FILE.exists():
        pid = int(PID_FILE.read_text())
        try:
            os.kill(pid, 0)
            os.kill(pid, 9)
            print(f'已停止进程 {pid}')
        except OSError:
            print(f'进程 {pid} 不存在')
        PID_FILE.unlink(missing_ok=True)
    else:
        print('未找到 PID 文件')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('用法: python win_proxy.py [start|stop]')
        sys.exit(1)

    if sys.argv[1] == 'start':
        start_server()
    elif sys.argv[1] == 'stop':
        stop_server()
    else:
        print(f'未知命令: {sys.argv[1]}')
        sys.exit(1)
