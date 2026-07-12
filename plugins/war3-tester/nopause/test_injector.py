#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_injector.py - 独立 WFE 注入器（阶段1 go/no-go 验证）

⚠️ 必须用 32 位 Python 跑！
   原理：同一 boot 内所有 32 位进程共享 kernel32.dll 基址（ASLR per-boot 一致），
   故 32 位 Python 的 LoadLibraryA 地址 = 32 位 war3 的 LoadLibraryA 地址。
   64 位 Python 的 kernel32 是 64 位版本，地址不匹配，注入必崩。
   MSYS2 32 位 Python: /c/msys64/mingw32/bin/python3.exe

用法:
    /c/msys64/mingw32/bin/python3.exe test_injector.py [dll_path]
    # 默认 dll_path = D:/WFE/WFEDll.dll

流程: 找 war3.exe PID → OpenProcess → VirtualAllocEx 写 dll 路径 →
      CreateRemoteThread(LoadLibraryA) → WaitForSingleObject → 报告
"""
import ctypes
from ctypes import wintypes
import struct
import subprocess
import sys
import time

# use_last_error=True 才能用 ctypes.get_last_error()
k32 = ctypes.WinDLL('kernel32', use_last_error=True)

PROCESS_ALL_ACCESS = 0x1F0FFF
MEM_COMMIT = 0x1000
MEM_RESERVE = 0x2000
PAGE_READWRITE = 0x04

# --- 函数原型 ---
k32.OpenProcess.restype = wintypes.HANDLE
k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
k32.VirtualAllocEx.restype = wintypes.LPVOID
k32.VirtualAllocEx.argtypes = [wintypes.HANDLE, wintypes.LPVOID, ctypes.c_size_t, wintypes.DWORD, wintypes.DWORD]
k32.WriteProcessMemory.restype = wintypes.BOOL
k32.WriteProcessMemory.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.LPCVOID, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
k32.GetModuleHandleW.restype = wintypes.HMODULE
k32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
k32.GetProcAddress.restype = wintypes.LPVOID
k32.GetProcAddress.argtypes = [wintypes.HMODULE, wintypes.LPCSTR]
k32.CreateRemoteThread.restype = wintypes.HANDLE
k32.CreateRemoteThread.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD, wintypes.LPVOID, wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
k32.WaitForSingleObject.restype = wintypes.DWORD
k32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
k32.CloseHandle.restype = wintypes.BOOL
k32.CloseHandle.argtypes = [wintypes.HANDLE]


def find_war3_pid(timeout=20):
    """轮询 tasklist 找 war3.exe PID"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            out = subprocess.check_output(
                ['tasklist.exe', '/FO', 'CSV', '/NH'],
                text=True, encoding='gbk', errors='ignore'
            )
            for line in out.splitlines():
                if 'war3.exe' in line.lower():
                    # 格式: "war3.exe","1234","Console","1","12,345 K"
                    parts = line.split('","')
                    if len(parts) >= 2:
                        pid = int(parts[1].strip('"'))
                        print(f'[+] 找到 war3.exe  PID={pid}')
                        return pid
        except Exception as e:
            print(f'[!] tasklist 异常: {e}')
        time.sleep(0.5)
    print('[-] 超时未找到 war3.exe')
    return None


def inject_dll(pid, dll_path):
    """CreateRemoteThread + LoadLibraryA 标准注入"""
    path_bytes = dll_path.encode('ansi') + b'\x00'
    path_len = len(path_bytes)

    h = k32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
    if not h:
        print(f'[-] OpenProcess 失败 err={ctypes.get_last_error()}')
        return False
    print(f'[+] OpenProcess  h={h}')
    try:
        addr = k32.VirtualAllocEx(h, None, path_len, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE)
        if not addr:
            print(f'[-] VirtualAllocEx 失败 err={ctypes.get_last_error()}')
            return False
        print(f'[+] VirtualAllocEx  addr=0x{addr:x}')

        written = ctypes.c_size_t(0)
        if not k32.WriteProcessMemory(h, addr, path_bytes, path_len, ctypes.byref(written)):
            print(f'[-] WriteProcessMemory 失败 err={ctypes.get_last_error()}')
            return False
        print(f'[+] WriteProcessMemory  {written.value} bytes')

        # 32 位 Python 的 kernel32 LoadLibraryA = 32 位 war3 的（同 boot 共享基址）
        h_k32 = k32.GetModuleHandleW('kernel32.dll')
        load_lib = k32.GetProcAddress(h_k32, b'LoadLibraryA')
        if not load_lib:
            print('[-] GetProcAddress(LoadLibraryA) 失败')
            return False
        print(f'[+] LoadLibraryA  addr=0x{load_lib:x}')

        tid = wintypes.DWORD(0)
        ht = k32.CreateRemoteThread(h, None, 0, load_lib, addr, 0, ctypes.byref(tid))
        if not ht:
            print(f'[-] CreateRemoteThread 失败 err={ctypes.get_last_error()}')
            return False
        print(f'[+] CreateRemoteThread  tid={tid.value}')

        k32.WaitForSingleObject(ht, 10000)
        k32.CloseHandle(ht)
        print('[+] 注入流程完成')
        return True
    finally:
        k32.CloseHandle(h)


def main():
    dll = sys.argv[1] if len(sys.argv) > 1 else 'D:/WFE/WFEDll.dll'
    bits = struct.calcsize('P') * 8
    print('=== WFE 注入器（go/no-go 验证）===')
    print(f'Python bits: {bits}  {"[OK]" if bits == 32 else "[FAIL] 必须 32 位 Python！"}')
    print(f'目标 DLL: {dll}')
    if bits != 32:
        print('请用 32 位 Python: /c/msys64/mingw32/bin/python3.exe test_injector.py')
        return 2

    pid = find_war3_pid()
    if not pid:
        print('请先 run_game 启动 war3')
        return 1
    ok = inject_dll(pid, dll)
    if ok:
        print('\n=== 注入成功。现在测试：===')
        print('1) Alt+Tab 切到别的窗口 / 最小化 war3')
        print('2) 用 inspect_game 跑 1+1 确认 Lua 持续响应（不暂停则秒回）')
        print('3) 观察 war3 画面是否继续推进')
        return 0
    print('\n=== 注入失败 ===')
    return 1


if __name__ == '__main__':
    sys.exit(main())
