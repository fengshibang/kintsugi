"""06 票:批量编排 run_batch(paths, deps) -> list[AnalysisResult]。

逐个调 analyze,单视频整体失败(如切片/探测抛错,在 analyze 的段级 try 之外)被捕获
不传染其余;失败视频返回错误信封(segment=None 表整体性错误),保持结果与输入一一对应。
07 票:透传 keep_artifacts / on_progress 给 analyze(保留产物 / 段级进度回调)。
写文件由 CLI 外壳负责,本模块不触及文件系统(spec:批量逻辑落此可测)。
"""
from __future__ import annotations

from typing import Callable

from video_idea_extractor.analyze import analyze
from video_idea_extractor.deps import Deps
from video_idea_extractor.types import AnalysisResult, ErrorEntry


def run_batch(
    paths: list[str],
    deps: Deps,
    segment_minutes: float = 10.0,
    keep_artifacts: bool = False,
    on_progress: Callable[[int, int, str], None] | None = None,
) -> list[AnalysisResult]:
    """逐个分析 paths 中的视频,返回与输入一一对应的 AnalysisResult 列表。

    透传 keep_artifacts / on_progress 给 analyze(07 票)。单视频整体失败(analyze 抛出
    未预期异常,如 slice_video 阶段的探测/切片错误)被捕获:该视频得到一个错误信封
    (ideas 空、errors 记整体异常),其余视频照常处理。段级失败已由 analyze 内部记入
    errors(05 票),不会抛到这里。
    """
    results: list[AnalysisResult] = []
    for path in paths:
        try:
            results.append(
                analyze(
                    path,
                    deps,
                    segment_minutes=segment_minutes,
                    keep_artifacts=keep_artifacts,
                    on_progress=on_progress,
                )
            )
        except Exception as e:
            results.append(
                AnalysisResult(
                    video=path,
                    path=deps.default_path(),
                    ideas=[],
                    errors=[
                        ErrorEntry(
                            segment=None,
                            message=f"{type(e).__name__}: {e}",
                        )
                    ],
                    artifacts=None,
                )
            )
    return results
