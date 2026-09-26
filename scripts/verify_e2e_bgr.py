# -*- coding: utf-8 -*-
"""
verify_e2e_bgr.py -- 端到端反馈环 (diagnosing-bugs Phase 5 收尾验证)

不依赖 War3：自建一个纯色 #b08d4a 的 tkinter 窗口，
用与 env_bridge.py 修复后完全相同的 GDI 管线
(PrintWindow -> GetDIBits 24bpp -> PIL raw BGR -> PNG) 抓图，
采样中心像素断言 == 源色。

红: 裸 RGB 解释 -> (74,141,176)；绿: raw BGR -> (176,141,74)。
"""
import ctypes
import io
import sys
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import tkinter as tk
from PIL import Image

SRC_RGB = (176, 141, 74)  # 金色 #b08d4a，与报告复现场景同色
SHOT = Path(__file__).with_name("_e2e_shot.png")

# ---------- 1. 造一个已知纯色窗口 ----------
root = tk.Tk()
root.geometry("320x240+80+80")
root.configure(background="#b08d4a")
root.attributes("-topmost", True)
root.update()
time.sleep(0.6)  # 等合成器把首帧画完
root.update()

hwnd = ctypes.windll.user32.GetParent(root.winfo_id()) or root.winfo_id()

# ---------- 2. 与 env_bridge.py 相同的 GDI 管线（修复后版本） ----------
user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32


class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", ctypes.c_uint32), ("biWidth", ctypes.c_long),
                ("biHeight", ctypes.c_long), ("biPlanes", ctypes.c_uint16),
                ("biBitCount", ctypes.c_uint16), ("biCompression", ctypes.c_uint32),
                ("biSizeImage", ctypes.c_uint32), ("biXPelsPerMeter", ctypes.c_long),
                ("biYPelsPerMeter", ctypes.c_long), ("biClrUsed", ctypes.c_uint32),
                ("biClrImportant", ctypes.c_uint32)]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", ctypes.c_uint32 * 3)]


rect = RECT()
user32.GetWindowRect(hwnd, ctypes.byref(rect))
width, height = rect.right - rect.left, rect.bottom - rect.top
assert width > 0 and height > 0, "窗口尺寸无效"

hdc_screen = user32.GetDC(0)
hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
hbmp = gdi32.CreateCompatibleBitmap(hdc_screen, width, height)
gdi32.SelectObject(hdc_mem, hbmp)

PW_RENDERFULLCONTENT = 0x00000002
if user32.PrintWindow(hwnd, hdc_mem, PW_RENDERFULLCONTENT) == 0:
    gdi32.BitBlt(hdc_mem, 0, 0, width, height, hdc_screen, rect.left, rect.top, 0x00CC0020)

bmi = BITMAPINFO()
bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
bmi.bmiHeader.biWidth = width
bmi.bmiHeader.biHeight = -height
bmi.bmiHeader.biPlanes = 1
bmi.bmiHeader.biBitCount = 24
bmi.bmiHeader.biCompression = 0

pixels = (ctypes.c_byte * (width * height * 3))()
gdi32.GetDIBits(hdc_mem, hbmp, 0, height, pixels, ctypes.byref(bmi), 0)

img = Image.frombytes("RGB", (width, height), bytes(pixels), "raw", "BGR")
img.save(SHOT)

gdi32.DeleteObject(hbmp)
gdi32.DeleteDC(hdc_mem)
user32.ReleaseDC(0, hdc_screen)
root.destroy()

# ---------- 3. 采样断言 ----------
got = Image.open(SHOT).convert("RGB")
center = got.getpixel((width // 2, height // 2))
# 再采样 4 个偏心点，确认整幅一致（不只是中心一像素蒙对）
pts = [(width // 4, height // 4), (3 * width // 4, height // 4),
       (width // 4, 3 * height // 4), (3 * width // 4, 3 * height // 4)]
samples = [got.getpixel(p) for p in pts]

print(f"源色        : {SRC_RGB}")
print(f"中心像素    : {center}")
print(f"四角采样    : {samples}")
ok = all(all(abs(c - s) <= 6 for c, s in zip(SRC_RGB, px)) for px in [center] + samples)
print("verdict:", "GREEN (截图像素 == 屏幕源色)" if ok else "RED (颜色仍被互换/污染)")
sys.exit(0 if ok else 1)
