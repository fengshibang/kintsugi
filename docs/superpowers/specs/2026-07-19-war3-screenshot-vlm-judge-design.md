# war3-tester 截图后主动调用 VLM 判读 — 设计文档

- **日期**: 2026-07-19
- **状态**: 已确认，待实现
- **来源**: brainstorming 技能产出
- **关联**: war3-tester 插件 v0.13.18 / kintsugi marketplace（`fengshibang/kintsugi`）

## 1. 背景与问题

用户反馈：「war3-tester 在看截图的时候不会主动使用视觉模型」。

war3-tester 插件提供两个相关的 MCP 工具，但二者割裂：

- `take_screenshot`：截取游戏窗口，返回 PNG 路径，**不调用任何视觉模型**。
- `analyze_screenshot`：读图 → base64 → 调 Anthropic 兼容接口（VLM）→ 返回画面判读文本（画面状态 / UI 元素 / 是否卡对话框 / 可见数值）。

结果：截图后 Claude 拿到一张路径，要么不看，要么用 Read 工具自己看图（走 Claude 自身视觉，而非用户专门配置的 VLM）。

## 2. 根因分析（两层）

### 2.1 配置层：analyze_screenshot 当前跑不通

`server/mcp_server.py` 中 `analyze_screenshot()`（第 897 行起）的环境变量读取逻辑：

| 变量 | 读取 | 兜底 | 当前状态 |
|------|------|------|----------|
| base_url | `VLM_BASE_URL` | `ANTHROPIC_BASE_URL` | 已配置（兜底可用） |
| api_key | `VLM_API_KEY` | `ANTHROPIC_AUTH_TOKEN` | 已配置（兜底可用） |
| **model** | `VLM_MODEL` | **无兜底** | **未配置 → 必报错** |

`~/.claude/settings.json` 的 env 配置了 `ANTHROPIC_BASE_URL` / `ANTHROPIC_AUTH_TOKEN` / `ANTHROPIC_MODEL=qwen3.7-plus`，但**没有 `VLM_MODEL`**。因此现在一调 `analyze_screenshot` 必报「未配置 VLM_MODEL」（`mcp_server.py:925-930`）。

这是「不主动用」的直接原因之一：调了就失败，久而久之不再调用。

### 2.2 行为层：截图与判读割裂，文档未强制

- `take_screenshot`（`mcp_server.py:1814`）只返回路径。
- 失败自动截图（`auto_screenshot_on_failure`）只把 PNG 路径塞进结果 JSON，不判读。
- SKILL.md「常见错误」表写「游戏卡对话框 → take_screenshot → 判读 → send_key」，但「判读」未明确要用 `analyze_screenshot`，也未禁止用 Read 自看。

## 3. 目标

任何截图（手动 / 测试失败自动 / 调试）后，主动调用 `analyze_screenshot`（VLM）判读画面，不依赖 Claude 用 Read 自看。

## 4. 设计方案

### 4.1 层 1 · 配置层（前提，必做）

在 `~/.claude/settings.json` 的 `env` 中新增：

```json
"VLM_MODEL": "qwen3.7-plus"
```

- 复用现有 `ANTHROPIC_MODEL` 的值（qwen3.7-plus，视觉模型）。
- `base_url` / `api_key` 走 `ANTHROPIC_BASE_URL` / `ANTHROPIC_AUTH_TOKEN` 兜底，已存在，无需另配。
- 改完需 `/mcp` 重连 war3-tester 让新 env 生效。

### 4.2 层 2 · 行为层 · 改 war3-auto-test SKILL.md

**改动位置**：`marketplaces/kintsugi/plugins/war3-tester/skills/war3-auto-test/SKILL.md`（git 源，`fengshibang/kintsugi` 仓库 master 分支）。

**四处改动**：

1. **「常见错误」表**「游戏卡对话框」行：
   `take_screenshot → 判读 → send_key` → 改为
   `take_screenshot → analyze_screenshot（VLM 判读）→ send_key`

2. **「操作约束」小节** 追加一条约束：
   > 截图（take_screenshot / 失败自动截图）后，必须调用 `analyze_screenshot` 用 VLM 判读画面，禁止用 Read 工具自己看图。

3. **「截图策略」注释** 补充：
   crash/timeout/unknown 自动截图后，对失败截图也调用 `analyze_screenshot` 判读，辅助定位。

4. **MCP 工具清单** `take_screenshot` 行描述补充：
   「截图后应配合 `analyze_screenshot` 调 VLM 判读」。

### 4.3 版本与推送

- bump 版本号：`.claude-plugin/plugin.json` `0.13.18` → `0.13.19`。
- `CHANGELOG.md` 追加一条 0.13.19 记录：「SKILL.md 强制截图后调用 analyze_screenshot 判读」。
- 在 `marketplaces/kintsugi/` 仓库内 `git commit + push` 到 `fengshibang/kintsugi` master。

### 4.4 本机生效（cache 副本同步）

Claude Code 实际加载的是 `cache/kintsugi/war3-tester/0.13.18/`（安装快照，非 git）。改 marketplaces 源不会自动刷新 cache。因此：

- **同步改 cache 副本** `cache/kintsugi/war3-tester/0.13.18/skills/war3-auto-test/SKILL.md`（同 4.2 四处改动），让本机立即生效。
- 后续重装插件时由 git 源覆盖 cache，保持一致。

## 5. 实现位置清单

| # | 文件 | 改动 | 位置性质 |
|---|------|------|----------|
| 1 | `~/.claude/settings.json` | env 加 `VLM_MODEL=qwen3.7-plus` | 全局配置 |
| 2 | `marketplaces/kintsugi/plugins/war3-tester/skills/war3-auto-test/SKILL.md` | 四处改动 | git 源（推送） |
| 3 | `marketplaces/kintsugi/plugins/war3-tester/.claude-plugin/plugin.json` | 版本 0.13.18→0.13.19 | git 源（推送） |
| 4 | `marketplaces/kintsugi/plugins/war3-tester/CHANGELOG.md` | 追加 0.13.19 记录 | git 源（推送） |
| 5 | `cache/kintsugi/war3-tester/0.13.18/skills/war3-auto-test/SKILL.md` | 同 #2 四处改动 | 本机 cache（立即生效） |

## 6. 局限性（已确认接受）

- **覆盖范围**：SKILL.md 仅在 war3-auto-test skill 被加载时生效（`/war3-auto-test` 或 Skill 调度）。未加载该 skill 时的手动 `take_screenshot` 不覆盖。用户已明确选择不加 CLAUDE.md 兜底。
- **升级覆盖**：cache 副本改动会在重装时被源覆盖（这是期望行为，源已同步）。
- **VLM 失败降级**：`analyze_screenshot` 失败时（如 VLM 临时不可用）只影响判读步骤，`take_screenshot` 本身不受影响，截图仍可用。

## 7. 验证

- **配置层**：`/mcp` 重连 war3-tester 后，手动 `take_screenshot` + `analyze_screenshot` 跑通一次，确认返回画面判读文本而非「未配置 VLM_MODEL」。
- **行为层**：跑一次 war3-auto-test 流程（含卡对话框或失败截图场景），确认截图后主动调用 `analyze_screenshot`，而非用 Read 自看。

## 8. 决策记录

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 覆盖场景 | 所有截图一律判读 | 用户要求最大覆盖 |
| 行为层机制 | 改插件 SKILL.md | 用户选择；文档级改动，风险低 |
| VLM_MODEL 值 | qwen3.7-plus | 复用现有 ANTHROPIC_MODEL，视觉模型 |
| 副本策略 | 改 git 源 + 推送远端 + 同步 cache | 源为权威，cache 立即生效 |
| CLAUDE.md 兜底 | 不加 | 用户明确拒绝，仅针对插件 skill |
