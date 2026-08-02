---
name: video-idea-extractor
description: 用 qwen3.7-plus 多模态模型从视频里提取"点子创意"(观点/步骤/视觉/转折),输出带时间戳的结构化创意清单(JSON 或 Markdown)。用户给视频文件或目录路径、要"分析视频""提取创意""看看视频里有什么值得记的"时用。
---

# 视频创意提取

用 `vie` CLI(项目在 `D:\maps\tools\视频分析工具`)分析视频,自适应提取带时间戳的创意。CLI 内部:ffmpeg 切片 -> qwen3.7-plus 提取 -> 合并去重 -> 信封输出。三路降级:原生视频(B)/ 抽帧+ASR(C1)/ 纯 ASR(C2),自动选。

## 何时用

- 用户给一个视频文件路径(或目录),想提取里面的创意/观点/步骤/亮点
- 用户说"分析这个视频""提取视频创意""看看这视频有什么值得记的""总结视频要点子"

## 怎么做

把 `<VIDEO>` 换成用户给的视频路径(或目录),跑:

```bash
cd "D:\maps\tools\视频分析工具" && VIE_FFMPEG_BIN='D:\FeverApps\party_pc\bin' PYTHONPATH=. PYTHONUTF8=1 python -m video_idea_extractor.cli analyze "<VIDEO>" --format md
```

**参数**
- `<VIDEO>`:视频文件路径,或目录(批量处理其下音视频,每视频一个输出文件)
- `--format`:`md`(Markdown 速览,给人读,推荐)或 `json`(默认,信封结构)
- `-o <路径>`:单文件=输出文件路径;目录=输出目录。省略则默认 `<视频名>.ideas.<json|md>`(写在项目根,故建议显式 `-o` 指到视频同目录或用户指定处)
- `--keep-artifacts`:保留切片/转写供调试(路径写入 `artifacts`)
- `--model <名>`:覆盖模型(默认 `qwen3.7-plus`)

**环境**:`VIE_FFMPEG_BIN` 指 ffmpeg.exe 目录;`.env`(项目根,含 `DASHSCOPE_API_KEY`/`DASHSCOPE_BASE_URL`/`MODEL`)由 CLI 自动加载,无需手动 source。

## 输出形状

- **JSON**:`{video, path("B"|"C"), ideas:[{timestamp, type, title, detail}], errors:[{segment, offset, message}], artifacts}`
  - `type` ∈ `insight|step|visual|turn|other`(观点/步骤/视觉/转折/其他)
  - `errors` 空=全成功;非空=部分段失败(结果仍写出)
- **Markdown**:`# 创意速览:<视频名>` + 路径/创意数 + 每条 `## 类型·时间戳` / `**标题**` / 详情

## 呈现给用户

跑完后**整理成易读列表**给用户,不要直接贴原始 JSON/MD:
- 每条创意:时间戳 + 类型 + 标题 + 一句简述
- 批量时按视频分组
- 有 `errors` 时,告知哪些段/视频失败、整体是否仍可用
- 输出文件路径告诉用户(方便其后续查看)

## 注意

- 真模型调用,几秒到几十秒;长视频(切片)更久,批量更长
- 创意**非确定性**:同视频多次跑可能不同
- 全程只读,不修改原视频
- 模型按 token 计费;429/5xx 自动重试
