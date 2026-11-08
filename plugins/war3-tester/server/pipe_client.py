#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
pipe_client.py - Windows 命名管道 (\\.\pipe\war3_agent / \\.\pipe\war3_agent_<pid>) 客户端

职责：
- 通过 Windows Named Pipe 与 War3.exe 进程内的 agent_bridge.dll 通信
- 支持 PIPE_UNLIMITED_INSTANCES 多客户端并发（多个 MCP 实例同时连接不冲突，彻底替代 HTTP 轮询 inspect 队列）
- 支持跨权限连接（管理员 War3.exe <-> 普通用户 MCP 进程）
- 零外部依赖（仅用 Python 标准库 ctypes）
"""

import ctypes
from ctypes import wintypes
import json
import os
import struct
import sys
import threading
import time
import uuid
from typing import Optional

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
OPEN_EXISTING = 3
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
ERROR_PIPE_BUSY = 231
ERROR_FILE_NOT_FOUND = 2

if sys.platform == "win32":
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    kernel32.CreateFileW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
        wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE
    ]
    kernel32.CreateFileW.restype = wintypes.HANDLE

    kernel32.ReadFile.argtypes = [
        wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID
    ]
    kernel32.ReadFile.restype = wintypes.BOOL

    kernel32.WriteFile.argtypes = [
        wintypes.HANDLE, wintypes.LPCVOID, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID
    ]
    kernel32.WriteFile.restype = wintypes.BOOL

    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    kernel32.WaitNamedPipeW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD]
    kernel32.WaitNamedPipeW.restype = wintypes.BOOL
else:
    kernel32 = None


class PipeClientError(Exception):
    """命名管道客户端异常"""
    pass


class PipeClient:
    """War3 Agent 命名管道客户端"""

    def __init__(self, pipe_name: Optional[str] = None, pid: Optional[int] = None):
        if pipe_name:
            self.pipe_name = pipe_name
        elif pid:
            self.pipe_name = fr"\\.\pipe\war3_agent_{pid}"
        else:
            self.pipe_name = os.environ.get("WAR3_AGENT_PIPE", r"\\.\pipe\war3_agent")
        self.handle = None
        self._lock = threading.RLock()

    def set_target(self, pipe_name: Optional[str] = None, pid: Optional[int] = None):
        """动态切换目标管道名或指定 War3 PID"""
        with self._lock:
            new_name = (
                pipe_name if pipe_name
                else (fr"\\.\pipe\war3_agent_{pid}" if pid else os.environ.get("WAR3_AGENT_PIPE", r"\\.\pipe\war3_agent"))
            )
            if new_name != self.pipe_name:
                self.close()
                self.pipe_name = new_name

    def connect(self, timeout_sec: float = 3.0) -> bool:
        if kernel32 is None:
            return False
        start_time = time.time()
        while time.time() - start_time < timeout_sec:
            h = kernel32.CreateFileW(
                self.pipe_name,
                GENERIC_READ | GENERIC_WRITE,
                0,
                None,
                OPEN_EXISTING,
                0,
                None
            )
            if h is not None and h != INVALID_HANDLE_VALUE and h != -1:
                self.handle = h
                return True

            err = ctypes.get_last_error()
            if err == ERROR_PIPE_BUSY:
                kernel32.WaitNamedPipeW(self.pipe_name, 500)
            else:
                time.sleep(0.1)

        return False

    def close(self):
        with self._lock:
            if kernel32 is not None and self.handle is not None and self.handle != INVALID_HANDLE_VALUE and self.handle != -1:
                kernel32.CloseHandle(self.handle)
                self.handle = None

    def is_connected(self) -> bool:
        return self.handle is not None and self.handle != INVALID_HANDLE_VALUE and self.handle != -1

    def _write_exact(self, data: bytes):
        total = len(data)
        offset = 0
        buf = ctypes.create_string_buffer(data, total)
        written = wintypes.DWORD(0)

        while offset < total:
            ptr = ctypes.byref(buf, offset)
            ok = kernel32.WriteFile(
                self.handle,
                ptr,
                total - offset,
                ctypes.byref(written),
                None
            )
            if not ok or written.value == 0:
                err = ctypes.get_last_error()
                raise PipeClientError(f"WriteFile 失败，错误码: {err}")
            offset += written.value

    def _read_exact(self, size: int) -> bytes:
        buf = ctypes.create_string_buffer(size)
        offset = 0
        read_now = wintypes.DWORD(0)

        while offset < size:
            ptr = ctypes.byref(buf, offset)
            ok = kernel32.ReadFile(
                self.handle,
                ptr,
                size - offset,
                ctypes.byref(read_now),
                None
            )
            if not ok or read_now.value == 0:
                err = ctypes.get_last_error()
                raise PipeClientError(f"ReadFile 失败，管道可能已断开，错误码: {err}")
            offset += read_now.value

        return buf.raw[:size]

    def send_frame(self, msg_str: str):
        raw = msg_str.encode("utf-8")
        header = struct.pack("<I", len(raw))
        self._write_exact(header)
        if len(raw) > 0:
            self._write_exact(raw)

    def recv_frame(self) -> str:
        header = self._read_exact(4)
        (length,) = struct.unpack("<I", header)
        if length == 0:
            return ""
        if length > 8 * 1024 * 1024:
            raise PipeClientError(f"响应帧过大: {length} 字节")
        payload = self._read_exact(length)
        return payload.decode("utf-8", errors="replace")

    def request(self, req_type: str, payload: Optional[dict] = None, timeout_ms: int = 10000, pid: Optional[int] = None) -> dict:
        with self._lock:
            if pid is not None:
                self.set_target(pid=pid)
            if not self.is_connected():
                connect_wait = min(max(timeout_ms / 1000.0, 0.5), 3.0)
                if not self.connect(timeout_sec=connect_wait):
                    raise PipeClientError(
                        f"未连接到游戏命名管道 ({self.pipe_name})。请确认游戏已启动且已开启 Agent 桥接（输入 '-test on' 或由 run_game 自动注入）。"
                    )

            req_id = str(uuid.uuid4())
            req_obj = {
                "id": req_id,
                "type": req_type,
                "timeout_ms": timeout_ms,
                "payload": payload or {}
            }
            req_json = json.dumps(req_obj, ensure_ascii=False)

            try:
                self.send_frame(req_json)
                resp_str = self.recv_frame()
            except PipeClientError:
                self.close()
                raise

            try:
                resp_obj = json.loads(resp_str)
            except Exception as e:
                raise PipeClientError(f"响应 JSON 解析失败: {e}, 原始数据: {resp_str}")

            return resp_obj
