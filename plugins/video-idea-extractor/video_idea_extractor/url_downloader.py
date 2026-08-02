"""URL 视频下载器：支持抖音（Playwright）和其他站点（yt-dlp）。

首次使用抖音需扫码登录，cookies 保存到 storage_state 文件，后续自动复用。
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse


# 抖音 storage state 存放位置
_DOUYIN_STATE_FILE = Path.home() / ".video_idea_extractor" / "douyin_state.json"


def is_video_url(arg: str) -> bool:
    """判断参数是否为视频 URL（http/https 开头）。"""
    return arg.startswith(("http://", "https://"))


def download_video(url: str, output_dir: str | None = None) -> str:
    """下载视频到本地，返回本地文件路径。

    Args:
        url: 视频页面 URL
        output_dir: 输出目录，默认临时目录

    Returns:
        本地视频文件路径
    """
    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="vie_url_")
    else:
        Path(output_dir).mkdir(parents=True, exist_ok=True)

    domain = urlparse(url).netloc.lower()

    # 抖音专用下载器
    if "douyin.com" in domain:
        return _douyin_download(url, output_dir)

    # 其他站点走 yt-dlp
    return _yt_dlp_download(url, output_dir)


def _yt_dlp_download(url: str, output_dir: str) -> str:
    """用 yt-dlp 下载视频。"""
    output_template = os.path.join(output_dir, "%(title)s.%(ext)s")
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--no-check-certificates",
        "-o", output_template,
        url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp 下载失败: {result.stderr}")

    # 找下载的文件
    for f in Path(output_dir).iterdir():
        if f.is_file() and f.suffix in {".mp4", ".mkv", ".webm", ".flv"}:
            return str(f)

    raise RuntimeError("下载完成但未找到视频文件")


def _douyin_download(url: str, output_dir: str) -> str:
    """用 Playwright 下载抖音视频。首次需扫码登录。"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise RuntimeError(
            "抖音下载需要 playwright。请运行: pip install playwright && playwright install chromium"
        )

    # 提取视频 ID
    video_id = _extract_douyin_video_id(url)
    if not video_id:
        raise RuntimeError(f"无法从 URL 提取视频 ID: {url}")

    # 检查是否需要登录
    need_login = not _DOUYIN_STATE_FILE.exists()

    with sync_playwright() as p:
        # 启动浏览器
        launch_args = {"headless": not need_login}
        browser = p.chromium.launch(**launch_args)

        # 加载或创建 context
        if _DOUYIN_STATE_FILE.exists():
            context = browser.new_context(storage_state=str(_DOUYIN_STATE_FILE))
        else:
            context = browser.new_context()

        page = context.new_page()

        # 访问视频页面
        video_url = f"https://www.douyin.com/video/{video_id}"
        page.goto(video_url, wait_until="networkidle")

        # 首次使用需要登录
        if need_login:
            print("\n" + "=" * 60)
            print("首次使用抖音下载，请在浏览器中扫码登录")
            print("登录完成后会自动保存 cookies，后续无需重复登录")
            print("=" * 60 + "\n")

            # 等待用户登录（检测登录状态）
            try:
                page.wait_for_selector(
                    '[class*="avatar"], [class*="user-info"]',
                    timeout=120000  # 2 分钟超时
                )
                print("登录成功！保存 cookies...")
                # 保存 storage state
                _DOUYIN_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
                context.storage_state(path=str(_DOUYIN_STATE_FILE))
            except Exception as e:
                browser.close()
                raise RuntimeError(f"登录超时或失败: {e}")

        # 等待视频加载
        page.wait_for_timeout(3000)

        # 从页面提取视频 URL
        video_src = _extract_video_url_from_page(page)
        if not video_src:
            browser.close()
            raise RuntimeError("无法从页面提取视频 URL")

        # 下载视频
        output_path = os.path.join(output_dir, f"douyin_{video_id}.mp4")
        _download_file(video_src, output_path)

        browser.close()

    return output_path


def _extract_douyin_video_id(url: str) -> str | None:
    """从抖音 URL 提取视频 ID。"""
    # 匹配 /video/1234567890 或 modal_id=1234567890
    patterns = [
        r"/video/(\d+)",
        r"modal_id=(\d+)",
        r"/(\d{15,})",  # 纯数字 ID
    ]
    for pattern in patterns:
        m = re.search(pattern, url)
        if m:
            return m.group(1)
    return None


def _extract_video_url_from_page(page) -> str | None:
    """从页面提取视频直链。"""
    # 方法 1：从 video 标签获取
    video_el = page.query_selector("video source")
    if video_el:
        src = video_el.get_attribute("src")
        if src and src.startswith("http"):
            return src

    # 方法 2：从 RENDER_DATA 提取
    try:
        render_data = page.evaluate("""
            () => {
                const el = document.getElementById('RENDER_DATA');
                if (!el) return null;
                try {
                    return JSON.parse(decodeURIComponent(el.textContent));
                } catch {
                    return null;
                }
            }
        """)
        if render_data:
            # 递归查找视频 URL
            video_url = _find_video_url_in_data(render_data)
            if video_url:
                return video_url
    except Exception:
        pass

    # 方法 3：从 network 请求获取
    # 监听视频请求
    video_urls = []
    def handle_response(response):
        url = response.url
        if "video" in url and url.endswith((".mp4", ".m3u8")):
            video_urls.append(url)

    page.on("response", handle_response)
    page.reload(wait_until="networkidle")
    page.wait_for_timeout(2000)

    if video_urls:
        return video_urls[0]

    return None


def _find_video_url_in_data(data, depth=0) -> str | None:
    """递归查找视频 URL。"""
    if depth > 10:
        return None
    if isinstance(data, dict):
        # 检查常见视频 URL 字段
        for key in ("play_addr", "playAddr", "video_url", "src"):
            if key in data:
                val = data[key]
                if isinstance(val, str) and val.startswith("http") and "video" in val:
                    return val
                if isinstance(val, dict) and "url_list" in val:
                    urls = val["url_list"]
                    if urls and isinstance(urls[0], str):
                        return urls[0]
        # 递归
        for v in data.values():
            result = _find_video_url_in_data(v, depth + 1)
            if result:
                return result
    elif isinstance(data, list):
        for item in data:
            result = _find_video_url_in_data(item, depth + 1)
            if result:
                return result
    return None


def _download_file(url: str, output_path: str) -> None:
    """下载文件到本地。"""
    import urllib.request
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    )
    with urllib.request.urlopen(req) as response:
        with open(output_path, "wb") as f:
            while True:
                chunk = response.read(8192)
                if not chunk:
                    break
                f.write(chunk)
