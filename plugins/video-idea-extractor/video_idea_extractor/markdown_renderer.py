"""07 票:Markdown 渲染层。把 AnalysisResult 渲染成速览 Markdown。

复用同一份 JSON 数据(AnalysisResult),渲染层独立于核心管线(spec L101)。
纯函数:不改输入,无副作用。
"""
from __future__ import annotations

from pathlib import Path

from video_idea_extractor.types import AnalysisResult

_TYPE_LABELS = {
    "insight": "观点",
    "step": "步骤",
    "visual": "视觉",
    "turn": "转折",
    "other": "其他",
}


def render_markdown(result: AnalysisResult) -> str:
    """渲染 AnalysisResult 为 Markdown 速览:标题 + 元信息 + 每条创意(类型·时间戳 / 标题 / 详情)。"""
    lines: list[str] = [
        f"# 创意速览:{Path(result.video).name}",
        "",
        f"- 路径:{result.path}",
        f"- 创意数:{len(result.ideas)}",
    ]
    lines.append("")

    for idea in result.ideas:
        label = _TYPE_LABELS.get(idea.type, idea.type)
        lines.append(f"## {label} · {_fmt_ts(idea.timestamp)}")
        lines.append("")
        lines.append(f"**{idea.title}**")
        lines.append("")
        lines.append(idea.detail)
        lines.append("")

    return "\n".join(lines)


def _fmt_ts(seconds: float) -> str:
    """秒 -> M:SS(>=1h 则 H:MM:SS)。"""
    s = int(round(seconds))
    if s >= 3600:
        return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}"
    return f"{s // 60}:{s % 60:02d}"
