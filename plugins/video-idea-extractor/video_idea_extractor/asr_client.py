"""ASR 客户端接口与 mock 实现。仅 C 路线用:把片段音频转文本。"""
from __future__ import annotations

from typing import Protocol


class AsrClient(Protocol):
    """ASR 接口:把片段(含音频轨)转成文本。仅在有音频轨时调用。"""

    def transcribe(self, audio_path: str) -> str: ...


class MockAsrClient:
    """mock ASR:返回预设文本,记录每次 transcribe 收到的路径(供测试断言调用与否)。"""

    def __init__(self, *, transcript: str) -> None:
        self._transcript = transcript
        self.calls: list[str] = []

    def transcribe(self, audio_path: str) -> str:
        self.calls.append(audio_path)
        return self._transcript
