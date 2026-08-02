# video-idea-extractor

用 qwen3.7-plus 多模态模型从视频提取"点子创意",输出 JSON/Markdown 速览。kintsugi marketplace plugin(自包含,源码内置)。

## 一键配置(脚手架)

装 plugin 后,到 plugin 目录(含 pyproject.toml)跑:

    python install.py

自动:检查 Python → pip install -e .(vie + openai)→ 检查 ffmpeg → 生成 .env 模板 → 验证 vie。可重复跑(幂等)。

## 手动安装(自包含)

本 plugin 自带 video_idea_extractor/ 源码 + pyproject.toml。装 plugin 后,到 plugin 目录:

    pip install -e <plugin安装目录>

(装 vie 命令 + openai SDK。plugin 目录 = 含 pyproject.toml 的那个,通常在 ~/.claude/plugins/.../plugins/video-idea-extractor/)

## 配置

- ffmpeg:在 PATH,或设 VIE_FFMPEG_BIN 指 ffmpeg.exe 目录
- .env(放 plugin 目录,pyproject.toml 同级):
  DASHSCOPE_API_KEY=sk-xxx
  DASHSCOPE_BASE_URL=http://your-proxy:3000   # OpenAI 兼容代理,代码自动补 /v1
  MODEL=qwen3.7-plus
  VIE_SUPPORTS_VIDEO=1
  CLI 启动时自动加载该 .env。

## 用法

装上 + 配好后,在 Claude Code 会话说"分析视频 <路径>"或 /video-idea-extractor,Claude 按 skill 调 vie CLI 提取创意并整理呈现。

详见 skills/video-idea-extractor/SKILL.md。
