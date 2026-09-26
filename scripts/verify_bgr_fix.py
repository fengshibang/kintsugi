# -*- coding: utf-8 -*-
"""
verify_bgr_fix.py -- take_screenshot R/B swap 反馈环 (diagnosing-bugs Phase 1-2)

红/绿信号 = 采样像素是否等于源色:
  红 (bug 在):  frombytes('RGB', ...) 直接解释 GDI BGR 字节流 -> (74,141,176)
  绿 (bug 修):  frombytes('RGB', ..., 'raw', 'BGR')       -> (176,141,74)

两层检查:
  A. 语义层: 报告中的字节流 (B=176,G=141,R=74) 进 PIL, 断言解释结果。
  B. 调用点层: 断言上游 env_bridge.py 生成的两处截图脚本都已带 'raw','BGR'。
"""
import io
import re
import sys
from pathlib import Path

from PIL import Image

# Windows 控制台 GBK 输出中文会花，统一强制 UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

REPO = Path(r"D:\kintsugi-dev")
BRIDGE = REPO / "plugins" / "war3-tester" / "server" / "env_bridge.py"

def check_a_bgr_semantics() -> bool:
    """A: GDI BGR 字节流必须被解释回源色 (176,141,74); 裸 RGB 解释必得互补色。"""
    # 屏幕上金色 #b08d4a = (R176, G141, B74); GDI 24bpp BI_RGB 内存序 = B,G,R
    gdi_bytes = bytes([74, 141, 176])
    ok = True

    buggy = Image.frombytes("RGB", (1, 1), gdi_bytes).getpixel((0, 0))
    good = Image.frombytes("RGB", (1, 1), gdi_bytes, "raw", "BGR").getpixel((0, 0))
    print(f"  裸 RGB 解释 : {buggy}  (期望互补色 (74,141,176) => bug 在时截图像素)")
    print(f"  raw BGR 解释: {good}  (期望源色 (176,141,74))")

    if buggy != (74, 141, 176):
        print("  !! 语义前提失效: 裸 RGB 未复现互补色, 环不再红")
        ok = False
    if good != (176, 141, 74):
        print("  !! 修复语义失效: raw BGR 未还原源色")
        ok = False
    return ok

def check_b_call_sites() -> bool:
    """B: env_bridge.py 两处截图脚本的 frombytes 都必须声明 BGR。"""
    text = BRIDGE.read_text(encoding="utf-8")
    # 逐行匹配整行（frombytes 参数列表含嵌套括号，[^)] 会在 (width, height) 处截断）
    calls = re.findall(r"Image\.frombytes\(.*", text)
    print(f"  env_bridge.py 中 frombytes 调用点: {len(calls)} 处")
    ok = len(calls) == 2
    if not ok:
        print("  !! 调用点数量异常 (期望 2)")
    for i, c in enumerate(calls, 1):
        has_bgr = "'BGR'" in c or '"BGR"' in c
        print(f"  [{i}] {'OK ' if has_bgr else 'RED'} {c.strip()}")
        ok = ok and has_bgr
    return ok

def main() -> int:
    print("[A] BGR 字节流解释语义 (纯 PIL, 无窗口依赖)")
    a = check_a_bgr_semantics()
    print("[B] 上游调用点静态检查")
    b = check_b_call_sites()
    verdict = "GREEN (修复在位)" if (a and b) else "RED (bug 在)"
    print(f"verdict: {verdict}")
    return 0 if (a and b) else 1

if __name__ == "__main__":
    sys.exit(main())
