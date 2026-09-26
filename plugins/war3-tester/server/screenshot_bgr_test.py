#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
take_screenshot R/B 互换回归测试（GDI BGR 字节序）

bug（issue #01, war3-tester 0.20.0）：
    env_bridge.py 截图脚本用 Image.frombytes('RGB', ...) 直接解释
    GDI GetDIBits 24bpp BI_RGB 的像素缓冲，而该缓冲字节序是 BGR，
    导致截图像素 R/B 就地互换（金色 #b08d4a 抓成互补蓝 (74,141,176)），
    所有依赖截图做颜色判读的验收结论不可信。

覆盖：
- _assert_screenshot_pipeline_consistency: 从 env_bridge.py 源码抽出的
  frombytes 调用必须声明 raw decoder 'BGR'（防两处调用点回退）
- take_screenshot_bgr_semantics: GDI BGR 字节流经 raw decoder 'BGR'
  必须还原源色；裸 RGB 解释必然得到互补色（锁定 bug 语义本身）

全部纯内存/静态，不依赖真实 War3 窗口。
"""

import io
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PIL import Image

BRIDGE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "env_bridge.py")

# 报告复现场景：屏幕金色 #b08d4a = (R176, G141, B74)
SRC_RGB = (176, 141, 74)
# GDI 24bpp BI_RGB 内存序 = B,G,R
GDI_BYTES = bytes([74, 141, 176])
# 裸 RGB 解释 = 互补色（bug 的可观测症状）
SWAPPED_RGB = (74, 141, 176)


class TestScreenshotBgr(unittest.TestCase):
    """截图管线 BGR 字节序回归"""

    def _frombytes_calls(self):
        with open(BRIDGE_PATH, encoding="utf-8") as f:
            text = f.read()
        # 整行匹配（参数列表含嵌套括号，[^)] 会在 (width, height) 处截断）
        return re.findall(r"Image\.frombytes\(.*", text)

    def test_frombytes_call_sites_declare_bgr(self):
        """env_bridge.py 全部 frombytes 调用点都必须声明 raw decoder 'BGR'"""
        calls = self._frombytes_calls()
        self.assertEqual(len(calls), 2, f"frombytes 调用点应为 2 处，实际 {len(calls)}")
        for i, call in enumerate(calls, 1):
            self.assertIn("BGR", call, f"第 {i} 处调用未声明 BGR: {call.strip()}")

    def test_take_screenshot_bgr_semantics(self):
        """GDI BGR 字节流经 'raw','BGR' 还原源色；裸 RGB 必得互补色（锁定 bug 语义）"""
        buggy = Image.frombytes("RGB", (1, 1), GDI_BYTES).getpixel((0, 0))
        self.assertEqual(
            buggy, SWAPPED_RGB,
            "前提失效：裸 RGB 解释未复现互补色，本测试锁定的 bug 语义已变化",
        )
        fixed = Image.frombytes("RGB", (1, 1), GDI_BYTES, "raw", "BGR").getpixel((0, 0))
        self.assertEqual(fixed, SRC_RGB, "raw 'BGR' 解释应还原屏幕源色")


if __name__ == "__main__":
    unittest.main(verbosity=2)
