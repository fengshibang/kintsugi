"""模型客户端:接口 + mock + 真实 qwen 实现。

真实实现 QwenModelClient 经 openai SDK 走 OpenAI 兼容端点(实测 04:qwen3.7-plus
吃 video,本地文件转 data URI 传输,无需上传)。
"""
from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
import time
from typing import Any, Callable, Protocol

from video_idea_extractor.types import AsrInput, FramesInput, Idea, ModelInput, VideoInput

_DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
_DEFAULT_MODEL = "qwen3.7-plus"
_VALID_TYPES = {"insight", "step", "visual", "turn", "other"}

_EXTRACT_SYSTEM = (
    "你是一个视频创意提取助手。从给定的视频/画面/转写文本中提取值得记的创意。"
    "每条创意含:timestamp(秒,相对于片段起点,浮点数)、"
    "type(枚举 insight|step|visual|turn|other:观点/步骤/视觉/转折/其他)、"
    "title(简短标题)、detail(说明)。"
    "只输出一个 JSON 数组,不要额外解释或 markdown 代码块。"
    "没有可提取的就输出 []。"
)
_EXTRACT_USER = "请提取创意,输出 JSON 数组。"


class ModelClient(Protocol):
    """统一模型接口:接收 InputAdapter 产出的输入,返回 Idea[]。"""

    supports_video: bool

    def extract(self, model_input: ModelInput) -> list[Idea]: ...


class MockModelClient:
    """mock 模型:返回预设 Idea,记录每次 extract 收到的输入(供测试断言输入形状)。"""

    def __init__(self, *, supports_video: bool, ideas: list[Idea]) -> None:
        self.supports_video = supports_video
        self._ideas = ideas
        self.calls: list[ModelInput] = []

    def extract(self, model_input: ModelInput) -> list[Idea]:
        self.calls.append(model_input)
        return list(self._ideas)


def _to_data_uri(path: str) -> str:
    """本地文件转 data URI(base64);http(s) URL 原样返回。"""
    if path.startswith(("http://", "https://")):
        return path
    mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return f"data:{mime};base64,{b64}"


def _ensure_v1(base_url: str) -> str:
    """OpenAI 兼容端点需以 /v1 结尾;缺则补上。"""
    b = base_url.rstrip("/")
    if not b.endswith("/v1"):
        b += "/v1"
    return b


def _extract_json_array(text: str) -> list[dict[str, Any]]:
    """从模型输出解析 JSON 数组;容忍 markdown 围栏与前后噪声。"""
    s = text.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\n?", "", s)
        s = re.sub(r"\n?```$", "", s).strip()
    try:
        obj = json.loads(s)
    except json.JSONDecodeError:
        m = re.search(r"\[.*\]", s, re.DOTALL)
        if m is None:
            raise ValueError(f"无法从模型输出解析 Idea[]: {text[:200]!r}") from None
        obj = json.loads(m.group(0))
    if isinstance(obj, dict) and "ideas" in obj:
        obj = obj["ideas"]
    if not isinstance(obj, list):
        raise ValueError(f"模型输出不是 JSON 数组: {text[:200]!r}")
    return obj


class QwenModelClient:
    """真实 ModelClient:openai SDK 走 OpenAI 兼容端点调 qwen。

    配置(环境变量):DASHSCOPE_API_KEY(必需)、DASHSCOPE_BASE_URL(默认官方兼容端点,
    自动补 /v1)、MODEL(默认 qwen3.7-plus)、VIE_SUPPORTS_VIDEO(默认 1)。
    实测(04):qwen3.7-plus 吃 video(data URI),supports_video=True -> B 起步。
    限流(429)/5xx 固定退避重试。
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        supports_video: bool | None = None,
        max_retries: int = 3,
        backoff: float = 2.0,
        client: Any = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.api_key = api_key or os.environ.get("DASHSCOPE_API_KEY", "")
        self.base_url = _ensure_v1(
            base_url or os.environ.get("DASHSCOPE_BASE_URL", _DEFAULT_BASE_URL)
        )
        self.model = model or os.environ.get("MODEL", _DEFAULT_MODEL)
        self.supports_video = (
            supports_video
            if supports_video is not None
            else os.environ.get("VIE_SUPPORTS_VIDEO", "1") == "1"
        )
        self._max_retries = max_retries
        self._backoff = backoff
        self._sleep = sleep
        if client is not None:
            self._client: Any = client
        else:
            from openai import OpenAI

            self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def extract(self, model_input: ModelInput) -> list[Idea]:
        messages = self._build_messages(model_input)
        text = self._call_with_retry(messages)
        return self._parse_ideas(text)

    def _build_messages(self, model_input: ModelInput) -> list[dict[str, Any]]:
        if isinstance(model_input, VideoInput):
            content: list[dict[str, Any]] = [
                {"type": "video_url", "video_url": {"url": _to_data_uri(model_input.video)}},
                {"type": "text", "text": _EXTRACT_USER},
            ]
        elif isinstance(model_input, FramesInput):
            content = [
                {"type": "image_url", "image_url": {"url": _to_data_uri(f)}}
                for f in model_input.frames
            ]
            text_parts = [_EXTRACT_USER]
            if model_input.asr_text:
                text_parts.insert(0, f"转写文本:\n{model_input.asr_text}")
            content.append({"type": "text", "text": "\n\n".join(text_parts)})
        elif isinstance(model_input, AsrInput):
            content = [
                {"type": "text", "text": f"转写文本:\n{model_input.asr_text}\n\n{_EXTRACT_USER}"},
            ]
        else:
            raise TypeError(f"不支持的 ModelInput 类型: {type(model_input)}")
        return [
            {"role": "system", "content": _EXTRACT_SYSTEM},
            {"role": "user", "content": content},
        ]

    def _call_with_retry(self, messages: list[dict[str, Any]]) -> str:
        for attempt in range(self._max_retries + 1):
            try:
                resp = self._client.chat.completions.create(
                    model=self.model, messages=messages
                )
                return resp.choices[0].message.content or ""
            except Exception as e:
                # 固定退避(非递增):每次重试等 backoff 秒
                if attempt < self._max_retries and self._is_retryable(e):
                    self._sleep(self._backoff)
                    continue
                raise
        raise RuntimeError("重试耗尽(不应到达)")  # pragma: no cover

    @staticmethod
    def _is_retryable(e: Exception) -> bool:
        """429 或 5xx 才重试(openai SDK 异常带 status_code)。"""
        status = getattr(e, "status_code", None)
        if status is None:
            response = getattr(e, "response", None)
            status = getattr(response, "status_code", None)
        if status is None:
            return False
        return int(status) == 429 or 500 <= int(status) < 600

    def _parse_ideas(self, text: str) -> list[Idea]:
        ideas: list[Idea] = []
        for item in _extract_json_array(text):
            t = item.get("type", "other")
            if t not in _VALID_TYPES:
                t = "other"
            ideas.append(
                Idea(
                    timestamp=float(item["timestamp"]),
                    type=t,
                    title=str(item.get("title", "")),
                    detail=str(item.get("detail", "")),
                )
            )
        return ideas
