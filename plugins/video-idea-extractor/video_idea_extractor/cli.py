"""CLI 外壳:解析参数 -> 调 analyze / run_batch -> 写 JSON/Markdown。薄层。

06 票:analyze 子命令的 video 参数支持目录(批量)。
07 票:--keep-artifacts 保留切片/转写、--format md 渲染 Markdown 速览、逐段打印进度。
批量编排逻辑落在 run_batch(可测),本外壳只解析参数与写文件、不测(spec)。
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from video_idea_extractor.analyze import analyze
from video_idea_extractor.batch import run_batch
from video_idea_extractor.deps import Deps
from video_idea_extractor.markdown_renderer import render_markdown
from video_idea_extractor.types import AnalysisResult
from video_idea_extractor.url_downloader import is_video_url, download_video

# 目录批量扫描的音视频扩展名(含纯音频:C2 路径支持播客等纯音频文件)
_MEDIA_EXTS = {
    ".mp4", ".mov", ".avi", ".mkv", ".webm", ".flv", ".wmv", ".m4v",
    ".mp3", ".wav", ".m4a", ".aac", ".flac",
}


def main(argv: list[str] | None = None, deps: Deps | None = None) -> int:
    parser = argparse.ArgumentParser(prog="vie", description="视频创意提取器")
    sub = parser.add_subparsers(dest="command", required=True)

    p_analyze = sub.add_parser("analyze", help="分析单个视频或目录(批量)")
    p_analyze.add_argument("video", help="视频文件路径,或目录(批量处理其下音视频)")
    p_analyze.add_argument(
        "-o", "--output",
        help="单文件:输出路径(默认 <video>.ideas.<json|md>);"
        "目录:输出目录(默认当前目录,每视频写 <stem>.ideas.<json|md>)",
    )
    p_analyze.add_argument(
        "--model", help="模型名(默认 env MODEL 或 qwen3.7-plus)"
    )
    p_analyze.add_argument(
        "--keep-artifacts", action="store_true",
        help="保留切片与转写,路径写入 artifacts(默认不保留)",
    )
    p_analyze.add_argument(
        "--format", choices=["json", "md"], default="json",
        help="输出格式:json(默认)或 md(Markdown 速览)",
    )

    args = parser.parse_args(argv)

    if deps is None:
        _load_env_file()
        deps = _default_deps(model=getattr(args, "model", None))

    if args.command == "analyze":
        video_arg = args.video

        # URL 自动下载
        if is_video_url(video_arg):
            print(f"检测到视频 URL，正在下载: {video_arg}")
            try:
                local_path = download_video(video_arg)
                print(f"下载完成: {local_path}")
                video_arg = local_path
            except Exception as e:
                print(f"下载失败: {e}")
                return 1

        if Path(video_arg).is_dir():
            return _run_batch_cli(
                Path(video_arg), args.output, deps,
                args.keep_artifacts, args.format,
            )
        return _run_single_cli(
            video_arg, args.output, deps,
            args.keep_artifacts, args.format,
        )

    return 1  # 未识别命令(不应到达)


def _print_progress(segment: int, total: int, video_path: str) -> None:
    """逐段进度(US20):段号/总数 + 视频名。"""
    print(f"  [{segment + 1}/{total}] {Path(video_path).name}")


def _write_output(out_path: Path, result: AnalysisResult, fmt: str) -> None:
    """写出单个结果为 JSON 或 Markdown 并打印摘要(单文件/批量共用,announce 一致)。"""
    if fmt == "md":
        content = render_markdown(result)
    else:
        content = json.dumps(result.to_dict(), ensure_ascii=False, indent=2)
    out_path.write_text(content, encoding="utf-8")
    errs = f", errors={len(result.errors)}" if result.errors else ""
    print(f"已写出 {out_path}: {len(result.ideas)} 条创意 (path={result.path}{errs})")


def _default_out_path(video: str, fmt: str) -> Path:
    return Path(f"{Path(video).stem}.ideas.{fmt}")


def _run_single_cli(
    video: str, output: str | None, deps: Deps, keep_artifacts: bool, fmt: str,
) -> int:
    result = analyze(
        video, deps, keep_artifacts=keep_artifacts, on_progress=_print_progress,
    )
    out_path = Path(output) if output else _default_out_path(video, fmt)
    _write_output(out_path, result, fmt)
    return 0


def _run_batch_cli(
    dir_path: Path, output: str | None, deps: Deps, keep_artifacts: bool, fmt: str,
) -> int:
    paths = sorted(
        str(p)
        for p in dir_path.iterdir()
        if p.is_file() and p.suffix.lower() in _MEDIA_EXTS
    )
    if not paths:
        print(f"目录 {dir_path} 下无可处理的音视频文件")
        return 1

    results = run_batch(
        paths, deps, keep_artifacts=keep_artifacts, on_progress=_print_progress,
    )
    out_dir = Path(output) if output else Path.cwd()
    out_dir.mkdir(parents=True, exist_ok=True)

    for video, result in zip(paths, results):
        _write_output(out_dir / _default_out_path(video, fmt).name, result, fmt)
    return 0


def _load_env_file() -> None:
    """从项目根 .env 加载环境变量(若存在;不覆盖已设的)。供真实 CLI 自动配置,免手动 source。"""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.is_file():
        return
    for ln in env_path.read_text(encoding="utf-8-sig").splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#") or "=" not in ln:
            continue
        k, v = ln.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _default_deps(model: str | None = None) -> Deps:
    """构造真实 deps:QwenModelClient(经 env 配置)+ FfmpegCliWrapper。

    模型配置走环境变量:DASHSCOPE_API_KEY / DASHSCOPE_BASE_URL / MODEL /
    VIE_SUPPORTS_VIDEO(见 QwenModelClient);model 参数(来自 --model)覆盖 MODEL。
    ffmpeg 经 VIE_FFMPEG_BIN 或 PATH。
    """
    from video_idea_extractor.ffmpeg_wrapper import FfmpegCliWrapper
    from video_idea_extractor.model_client import QwenModelClient

    return Deps(
        model_client=QwenModelClient(model=model),
        ffmpeg_wrapper=FfmpegCliWrapper(),
    )


if __name__ == "__main__":
    import sys

    sys.exit(main())
