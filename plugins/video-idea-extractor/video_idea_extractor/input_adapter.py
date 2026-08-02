"""输入适配层:把片段构造成模型输入,屏蔽 B/C 差异。

路径选择集中在此(不在 analyze 重复判断):
- supports_video=True                              -> B   (原生视频)
- supports_video=False + 有视频轨                  -> C1  (抽帧图片 + 可选 ASR 文本)
- supports_video=False + 无视频轨(纯音频/播客)     -> C2  (仅 ASR 文本,无抽帧)
无音频轨时 C1 的 asr_text=None(US17 纯画面),且 AsrClient 不被调用。
"""
from __future__ import annotations

from video_idea_extractor.deps import Deps
from video_idea_extractor.types import AsrInput, FramesInput, ModelInput, Path, VideoInput


def build_input(segment_path: str, deps: Deps) -> tuple[ModelInput, Path]:
    """依 model_client.supports_video + 片段视频/音频轨有无选 B/C1/C2,返回 (模型输入, 路径)。"""
    if deps.model_client.supports_video:
        return VideoInput(video=segment_path), "B"

    has_video = deps.ffmpeg_wrapper.has_video_track(segment_path)
    has_audio = deps.ffmpeg_wrapper.has_audio_track(segment_path)
    asr_text = _asr_text(segment_path, deps, has_audio)

    if has_video:
        # C1:抽帧图片 + (有音频轨时)ASR 文本
        frames = deps.ffmpeg_wrapper.extract_frames(segment_path)
        return FramesInput(frames=frames, asr_text=asr_text), "C"

    # C2:无视频轨,仅 ASR 文本;既无视频轨又无音频轨则无可提取内容
    if asr_text is None:
        raise RuntimeError("片段既无视频轨也无音频轨,无可提取内容")
    return AsrInput(asr_text=asr_text), "C"


def _asr_text(segment_path: str, deps: Deps, has_audio: bool) -> str | None:
    """有音频轨才转写;无音频轨返回 None(不调 AsrClient)。"""
    if not has_audio:
        return None
    if deps.asr_client is None:
        raise RuntimeError("C 路径需 ASR 转写,但 deps.asr_client 为 None;请注入 asr_client")
    return deps.asr_client.transcribe(segment_path)
