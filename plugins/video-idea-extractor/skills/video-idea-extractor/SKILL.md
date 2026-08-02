---
name: video-idea-extractor
description: 用 qwen3.7-plus 多模态模型从视频里提取"点子创意"(观点/步骤/视觉/转折),输出带时间戳的结构化创意清单(JSON 或 Markdown)。用户给视频文件或目录路径、要"分析视频""提取创意""看看视频里有什么值得记的"时用。
---

# 视频创意提取

调 vie CLI(需先装:`pip install -e <video-idea-extractor 源码目录>`)分析视频,提取带时间戳的创意。CLI 内部:ffmpeg 切片 -> qwen3.7-plus 提取 -> 合并去重 -> 信封输出。

## 何时用

用户给视频文件(或目录)路径,想提取创意/观点/步骤/亮点;或说"分析这个视频""提取视频创意""看看视频里有什么值得记的"。

## 怎么做

把 `<VIDEO>` 换成视频路径:

    VIE_FFMPEG_BIN='D:/FeverApps/party_pc/bin' vie analyze "<VIDEO>" --format md

**参数**
- `<VIDEO>`:视频文件路径,或目录(批量)
- `--format`:`md`(速览,推荐)或 `json`(默认)
- `-o <路径>`:输出路径;省略则默认 `<视频名>.ideas.<json|md>`
- `--keep-artifacts`:保留切片/转写供调试
- `--model <名>`:覆盖模型

**配置**:vie 需 `pip install -e` 源码另装;ffmpeg 需 `VIE_FFMPEG_BIN` 或 PATH;`.env`(vie 项目根)含 `DASHSCOPE_API_KEY`/`DASHSCOPE_BASE_URL`/`MODEL`/`VIE_SUPPORTS_VIDEO`,CLI 自动加载。

## 输出

- JSON:`{video, path("B"|"C"), ideas:[{timestamp,type,title,detail}], errors, artifacts}`
- Markdown:`# 创意速览:<视频名>` + 路径/创意数 + 每条 `## 类型·时间戳` / `**标题**` / 详情

## 呈现给用户

跑完后整理成易读列表(时间戳+类型+标题+简述),不贴原始 JSON。批量按视频分组。有 errors 告知失败段/视频。告知输出文件路径。

## 注意

真模型调用,几秒~几十秒;创意非确定性;全程只读;429/5xx 自动重试。
