"""切片器:按时长切,返回 [(segment_path, offset)]。短视频返回单段。"""
from __future__ import annotations

import math
import os

from video_idea_extractor.ffmpeg_wrapper import FfmpegWrapper


def slice_video(
    video_path: str,
    ffmpeg_wrapper: FfmpegWrapper,
    segment_minutes: float = 10.0,
    work_dir: str | None = None,
) -> list[tuple[str, float]]:
    """按时长切。每段 = (片段路径, 在原视频中的起始秒数)。

    短视频(duration <= segment_minutes)返回单段 [(video_path, 0.0)],不切文件。
    长视频切成多段,片段文件写入 work_dir(多段时必须提供);offset 为片段起始秒。
    """
    duration = ffmpeg_wrapper.get_duration(video_path)
    seg_seconds = segment_minutes * 60.0
    if duration <= seg_seconds:
        return [(video_path, 0.0)]

    if work_dir is None:
        raise ValueError("多段切片需要 work_dir")

    # 段数:ceil 加小 epsilon 抵消浮点误差,避免整除时多出一个零碎尾段
    n = max(1, math.ceil(duration / seg_seconds - 1e-9))
    segments: list[tuple[str, float]] = []
    for i in range(n):
        start = i * seg_seconds
        seg_duration = min(seg_seconds, duration - start)
        if seg_duration <= 0.0:
            break
        out_path = os.path.join(work_dir, f"seg_{i:03d}.mp4")
        ffmpeg_wrapper.slice_segment(video_path, start, seg_duration, out_path)
        segments.append((out_path, start))
    return segments
