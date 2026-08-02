"""依赖容器:所有外部依赖经 deps 注入,便于测试 mock。"""
from __future__ import annotations

from dataclasses import dataclass

from video_idea_extractor.asr_client import AsrClient
from video_idea_extractor.ffmpeg_wrapper import FfmpegWrapper
from video_idea_extractor.model_client import ModelClient
from video_idea_extractor.types import Path


@dataclass
class Deps:
    """注入的外部依赖。asr_client 仅 C 路线用(03 票),B 路径可为 None。"""

    model_client: ModelClient
    ffmpeg_wrapper: FfmpegWrapper
    asr_client: AsrClient | None = None

    def default_path(self) -> Path:
        """无成功段定路径时的回填:05 全段 build_input 失败 / 06 整视频失败。

        此时无段真正跑过,但 Path 字段(Literal["B","C"],无 null,spec L58)需有值,
        故依模型能力标记(supports_video)给 B/C 占位--非"实际走了该路径",message
        与 errors 已表达失败。集中此处避免回填表达式散落多处。
        """
        return "B" if self.model_client.supports_video else "C"
