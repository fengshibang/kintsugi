# video-idea-extractor

用 qwen3.7-plus 多模态模型从视频提取"点子创意",输出 JSON/Markdown 速览。kintsugi marketplace plugin。

## 依赖

- Python >=3.13 + `openai` SDK
- ffmpeg(切片/抽帧):在 PATH,或设 `VIE_FFMPEG_BIN`
- vie CLI:`pip install -e <video-idea-extractor 源码目录>`
- `.env`:`DASHSCOPE_API_KEY` / `DASHSCOPE_BASE_URL` / `MODEL` / `VIE_SUPPORTS_VIDEO`

## 用法

装上本 plugin 后,在 Claude Code 会话说"分析视频 <路径>"或 `/video-idea-extractor`,Claude 按 skill 调 vie CLI 提取创意并整理呈现。

详见 `skills/video-idea-extractor/SKILL.md`。
