---
description: 交互式配置 video-idea-extractor 环境(装依赖 + .env + ffmpeg + 验证 vie)
---

交互式引导用户完成 video-idea-extractor(vie)环境配置。需要用户输入时用 AskUserQuestion;敏感信息(DASHSCOPE_API_KEY)让用户手动填,不要求在对话里贴。

## 步骤

### 1. 定位 plugin 目录
用 Bash 在 ~/.claude/plugins/ 下找含 pyproject.toml 的 video-idea-extractor plugin 目录:

    find ~/.claude/plugins -path '*plugins/video-idea-extractor/pyproject.toml' 2>/dev/null

取其父目录记为 PLUGIN_DIR。找不到则问用户 plugin 安装路径。

### 2. 装依赖
Bash:

    pip install -e "<PLUGIN_DIR>"

装 vie 命令 + openai SDK。

### 3. 检查 ffmpeg
Bash 查 ffmpeg(which ffmpeg 或 where ffmpeg)。
- 找到:记下,继续。
- 没找到:用 AskUserQuestion 问用户 ffmpeg 所在目录(或"还没装"),设为 VIE_FFMPEG_BIN 写入 .env。

### 4. 交互收集配置
用 AskUserQuestion 问:
- MODEL:qwen3.7-plus(默认)/ 其他
- VIE_SUPPORTS_VIDEO:1(原生视频 B 路径,默认)/ 0(强制 C 降级)
- DASHSCOPE_BASE_URL:让用户填代理地址

DASHSCOPE_API_KEY 不在此问(敏感,步骤 5 引导手填)。

### 5. 写 .env
用 Write 写 <PLUGIN_DIR>/.env:

    DASHSCOPE_API_KEY=
    DASHSCOPE_BASE_URL=<步骤4 收集>
    MODEL=<步骤4>
    VIE_SUPPORTS_VIDEO=<步骤4>
    VIE_FFMPEG_BIN=<步骤3,若有>

然后告知用户:编辑该 .env 填 DASHSCOPE_API_KEY。建议用 ! 跑(不进对话):

    echo "DASHSCOPE_API_KEY=sk-xxx" >> "<PLUGIN_DIR>/.env"

或用编辑器。不要让用户在对话里贴 key。

### 6. 验证
Bash:

    vie analyze --help

确认 vie 装好、命令可用。

### 7. 报告
告知配置完成 + 下一步:填完 key 后,会话说"分析视频 <路径>"或 /video-idea-extractor,或命令行:

    vie analyze <视频> --format md
