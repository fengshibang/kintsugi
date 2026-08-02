"""合并器:多段 Idea[] 合并,时间戳换算(段内 timestamp + offset)+ 跨段去重。"""
from __future__ import annotations

from dataclasses import replace

from video_idea_extractor.types import Idea


def merge(segments: list[tuple[list[Idea], float]]) -> list[Idea]:
    """合并多段。segments = [(ideas, offset)]。

    时间戳换算:段内 timestamp + offset = 原视频 timestamp。
    跨段去重:某 title 若已在前面的段出现过则跳过(保留最早段那条;段顺序即时间顺序)。
    去重仅跨段--段内同 title 的 Idea 保留(不归并)。
    """
    seen_titles: set[str] = set()  # 前面段已出现过的 title
    result: list[Idea] = []
    for ideas, offset in segments:
        for idea in ideas:
            converted = replace(idea, timestamp=idea.timestamp + offset)
            if converted.title in seen_titles:
                continue  # 跨段重复,前面段已保留最早那条
            result.append(converted)
        # 本段处理完后,把本段 title 计入 seen(后续段起视为跨段重复)
        seen_titles.update(idea.title for idea in ideas)
    return result
