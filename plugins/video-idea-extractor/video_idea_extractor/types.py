"""输出 schema:AnalysisResult 信封及其组成部分;以及模型输入类型。"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

# 创意类型枚举:观点 / 步骤 / 视觉 / 转折 / 其他
IdeaType = Literal["insight", "step", "visual", "turn", "other"]

# 提取路径:B=原生视频输入,C=抽帧/ASR 降级(C1 抽帧+ASR / C2 纯 ASR)
Path = Literal["B", "C"]


@dataclass
class Idea:
    """一条创意条目。timestamp 相对于原视频(秒)。"""

    timestamp: float
    type: IdeaType
    title: str
    detail: str


@dataclass
class ErrorEntry:
    """段级失败标记。segment 为段号(整体性错误可省),offset 为原视频内秒数。"""

    segment: int | None = None
    offset: float = 0.0
    message: str = ""


@dataclass
class Artifacts:
    """中间产物位置。实现期可扩展。"""

    segments_dir: str
    transcript: str | None = None


@dataclass
class AnalysisResult:
    """analyze 的信封输出:创意 + 路径 + 段级错误 + 可选中间产物。"""

    video: str
    path: Path
    ideas: list[Idea] = field(default_factory=list)
    errors: list[ErrorEntry] = field(default_factory=list)
    artifacts: Artifacts | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "video": self.video,
            "path": self.path,
            "ideas": [asdict(i) for i in self.ideas],
            "errors": [asdict(e) for e in self.errors],
            "artifacts": asdict(self.artifacts) if self.artifacts is not None else None,
        }


@dataclass
class VideoInput:
    """B 路径模型输入:原生视频(路径或 URL)。放此避免与 model_client/input_adapter 循环 import。"""

    video: str


@dataclass
class FramesInput:
    """C1 路径模型输入:抽帧图片 + 可选 ASR 文本。

    有音频轨时 asr_text 为转写文本;无音频轨(纯画面)时为 None(US17 的落点)。
    """

    frames: list[str]
    asr_text: str | None = None


@dataclass
class AsrInput:
    """C2 路径模型输入:无视频轨(纯音频/播客),仅 ASR 文本(US18 的落点)。"""

    asr_text: str


# InputAdapter 产出的模型输入:B / C1 / C2 三种形状的联合
ModelInput = VideoInput | FramesInput | AsrInput
