"""主管线:analyze(video_path, deps) -> AnalysisResult。编排 切片 -> 逐段提取 -> 合并。"""
from __future__ import annotations

import contextlib
import os
import tempfile
from typing import Callable, Iterator

from video_idea_extractor.deps import Deps
from video_idea_extractor.input_adapter import build_input
from video_idea_extractor.merger import merge
from video_idea_extractor.slicer import slice_video
from video_idea_extractor.types import (
    AnalysisResult,
    Artifacts,
    AsrInput,
    ErrorEntry,
    FramesInput,
    Idea,
    ModelInput,
    Path,
)


def analyze(
    video_path: str,
    deps: Deps,
    segment_minutes: float = 10.0,
    keep_artifacts: bool = False,
    on_progress: Callable[[int, int, str], None] | None = None,
) -> AnalysisResult:
    """端到端:切片 -> 逐段提取(经 InputAdapter) -> 合并 -> 信封输出。

    路径(B/C)由 build_input 依 supports_video + 轨有无决定,同视频所有段同路径。
    切片产物放 work_dir,段在其生命周内消费(02 票:多段切片 + 合并)。
    段失败不中断(05 票):build_input/extract 抛错记入 errors、跳过该段、其余段照常合并。
    07 票:keep_artifacts=True 时 work_dir 不清理、ASR 文本合并写 transcript.txt、路径入
    artifacts(默认 None);on_progress 每段调一次(段号/总数/视频路径),供 CLI 打印进度。
    """
    asr_texts: list[str] = []
    with _work_dir(keep_artifacts) as work_dir:
        segments = slice_video(video_path, deps.ffmpeg_wrapper, segment_minutes, work_dir=work_dir)
        total = len(segments)

        path: Path | None = None  # 取首个成功段的路径;全失败则 fallback
        extracted: list[tuple[list[Idea], float]] = []
        errors: list[ErrorEntry] = []
        for i, (segment_path, offset) in enumerate(segments):
            if on_progress is not None:
                on_progress(i, total, video_path)
            try:
                model_input, seg_path = build_input(segment_path, deps)
                if path is None:
                    path = seg_path
                _collect_asr(model_input, asr_texts)
                ideas = deps.model_client.extract(model_input)
                extracted.append((ideas, offset))
            except Exception as e:
                # 含异常类型,便于辨识 bug vs 业务失败(US13 清晰错误)
                errors.append(
                    ErrorEntry(segment=i, offset=offset, message=f"{type(e).__name__}: {e}")
                )

        merged = merge(extracted)
        artifacts = _build_artifacts(work_dir, asr_texts) if keep_artifacts else None

    if path is None:
        # 所有段都在 build_input 阶段失败(如 C 路径 ASR/抽帧全炸):依能力标记回填路径
        path = deps.default_path()

    return AnalysisResult(
        video=video_path,
        path=path,
        ideas=merged,
        errors=errors,
        artifacts=artifacts,
    )


@contextlib.contextmanager
def _work_dir(keep: bool) -> Iterator[str]:
    """keep=False:临时目录,退出即清理(默认);keep=True:持久目录,退出不清理(保留产物)。"""
    if keep:
        yield tempfile.mkdtemp(prefix="vie_artifacts_")
    else:
        with tempfile.TemporaryDirectory(prefix="vie_") as d:
            yield d


def _collect_asr(model_input: ModelInput, out: list[str]) -> None:
    """从 C 路径模型输入取 asr_text(AsrInput 必有;FramesInput 可能为 None;VideoInput 无,跳过)。"""
    if isinstance(model_input, AsrInput):
        out.append(model_input.asr_text)
    elif isinstance(model_input, FramesInput) and model_input.asr_text is not None:
        out.append(model_input.asr_text)


def _build_artifacts(work_dir: str, asr_texts: list[str]) -> Artifacts:
    """构造 artifacts:segments_dir=work_dir;有 ASR 文本时合并写 transcript.txt。"""
    transcript: str | None = None
    if asr_texts:
        transcript = os.path.join(work_dir, "transcript.txt")
        with open(transcript, "w", encoding="utf-8") as f:
            f.write("\n\n".join(asr_texts))
    return Artifacts(segments_dir=work_dir, transcript=transcript)
