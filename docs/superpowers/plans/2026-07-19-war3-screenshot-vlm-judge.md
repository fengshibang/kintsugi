# war3-tester 截图后主动调用 VLM 判读 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 war3-tester 在任何截图后主动调用 `analyze_screenshot`（VLM）判读画面，而非只拿路径或用 Read 自看。

**Architecture:** 双层修复——① 配置层补 `VLM_MODEL`（`analyze_screenshot` 的 model 无兜底，当前必报错）；② 行为层改 `war3-auto-test` SKILL.md 四处，强制「截图→VLM 判读」流程。改动落在 kintsugi 仓库（`fengshibang/kintsugi`）git 源，bump 版本后推送远端，并同步 cache 副本让本机立即生效。

**Tech Stack:** MCP 插件（Python `mcp_server.py` + Lua skill 文档）、JSON 配置、git。

## Global Constraints

- `VLM_MODEL = qwen3.7-plus`（复用现有 `ANTHROPIC_MODEL`，视觉模型）；`base_url`/`api_key` 走 `ANTHROPIC_BASE_URL`/`ANTHROPIC_AUTH_TOKEN` 兜底（已存在）。
- 仅改插件 SKILL.md，**不加 CLAUDE.md 兜底**（用户决策）。
- 行为层改动提交到 `fengshibang/kintsugi` master 并 push；`~/.claude/settings.json` 是本机全局配置，**不进 kintsugi 仓库**。
- 全程中文：文档、注释、commit message 均用中文。
- **本计划为配置/文档任务，无可自动化单测的代码单元**——验证采用运行时手动验证（`/mcp` 重连 + 实际 MCP 调用），非 TDD 单测。诚实声明，不强行套 TDD。
- 基础设施准则：若 `/mcp` 重连、游戏启动、HTTP 服务、w2l.exe 等失败，**停止并告知用户**，不自行诊断/修复（见目标项目 CLAUDE.md「基础设施问题行为准则」）。

## File Structure

| 文件 | 责任 | 性质 |
|------|------|------|
| `~/.claude/settings.json` | Claude Code 全局 env，注入 MCP server 进程环境 | 本机配置（不进 git） |
| `marketplaces/kintsugi/plugins/war3-tester/skills/war3-auto-test/SKILL.md` | war3-auto-test skill 指引文档（git 源） | git 源（推送） |
| `marketplaces/kintsugi/plugins/war3-tester/.claude-plugin/plugin.json` | 插件版本号 | git 源（推送） |
| `marketplaces/kintsugi/plugins/war3-tester/CHANGELOG.md` | 变更日志 | git 源（推送） |
| `cache/kintsugi/war3-tester/0.13.18/skills/war3-auto-test/SKILL.md` | 实际加载的 skill 文档快照 | 本机 cache（立即生效） |

> marketplaces 与 cache 两份 SKILL.md 内容当前一致（同 0.13.18），改动需同步。

---

### Task 1: 配置层 — settings.json 补 VLM_MODEL

**Files:**
- Modify: `C:\Users\bang\.claude\settings.json`（env 块）

**Interfaces:**
- Produces: 环境变量 `VLM_MODEL=qwen3.7-plus`，供 war3-tester MCP server 的 `analyze_screenshot()`（`mcp_server.py:925`）读取。
- 注：`base_url`/`api_key` 由 `analyze_screenshot` 内部走 `ANTHROPIC_BASE_URL`/`ANTHROPIC_AUTH_TOKEN` 兜底，已存在，无需另配。

- [ ] **Step 1: 用 Edit 在 env 块插入 VLM_MODEL**

old_string（锚点：REASONING_MODEL 行 + AGENT_TEAMS 行，避开 token）:
```
    "ANTHROPIC_REASONING_MODEL": "qwen3.7-plus",
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
```
new_string:
```
    "ANTHROPIC_REASONING_MODEL": "qwen3.7-plus",
    "VLM_MODEL": "qwen3.7-plus",
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
```

- [ ] **Step 2: 验证 JSON 合法**

Run:
```bash
python -c "import json; json.load(open(r'C:/Users/bang/.claude/settings.json', encoding='utf-8')); print('JSON OK')"
```
Expected: `JSON OK`

- [ ] **Step 3: 让新 env 生效（用户操作）**

提示用户执行 `/mcp` 重连 war3-tester（MCP server 进程重启后读到新 env）。此步非自动化，标记等待用户确认。

> ⚠️ 基础设施准则：若 `/mcp` 重连失败，停止告知用户，不自行修复。

---

### Task 2: 行为层 — 改 SKILL.md（git 源）四处

**Files:**
- Modify: `C:\Users\bang\.claude\plugins\marketplaces\kintsugi\plugins\war3-tester\skills\war3-auto-test\SKILL.md`

**Interfaces:**
- Produces: SKILL.md 四处强化「截图→VLM 判读」，供 skill 加载时约束 Claude 行为。

- [ ] **Step 1: 改动①「截图策略」注释（第 59 行）**

old_string:
```
> **截图策略（设计文档 4.7）**：仅 `crash` / `timeout` / `unknown` 自动截图（`auto_screenshot_on_failure=true` 时）；`assertion` / `runtime_error` / `compile_error` 不截图（日志已足够诊断）。
```
new_string:
```
> **截图策略（设计文档 4.7）**：仅 `crash` / `timeout` / `unknown` 自动截图（`auto_screenshot_on_failure=true` 时）；`assertion` / `runtime_error` / `compile_error` 不截图（日志已足够诊断）。**自动截图后，必须对失败截图调用 `analyze_screenshot` 调 VLM 判读**，辅助定位（禁止用 Read 自看）。
```

- [ ] **Step 2: 改动② MCP 工具清单 take_screenshot 行（第 120 行）**

old_string:
```
| `take_screenshot` | 截取游戏窗口（PrintWindow） |
```
new_string:
```
| `take_screenshot` | 截取游戏窗口（PrintWindow）；**截图后必须配合 `analyze_screenshot` 调 VLM 判读，禁止用 Read 自看** |
```

- [ ] **Step 3: 改动③「常见错误」游戏卡对话框行（第 354 行）**

old_string:
```
| 游戏卡对话框 | `take_screenshot` → 判读 → `send_key` 继续 |
```
new_string:
```
| 游戏卡对话框 | `take_screenshot` → `analyze_screenshot`（VLM 判读）→ `send_key` 继续 |
```

- [ ] **Step 4: 改动④「操作约束」小节追加一条（第 362 行后）**

old_string:
```
**⚠️ 严禁 AI 直接操作 Windows 端**：所有编译/启动/截图/按键都通过 MCP 工具代理，不直接 `net start`/访问 Windows 路径/手动启停 War3。
```
new_string:
```
**⚠️ 严禁 AI 直接操作 Windows 端**：所有编译/启动/截图/按键都通过 MCP 工具代理，不直接 `net start`/访问 Windows 路径/手动启停 War3。

**⚠️ 截图后必须调 VLM 判读**：任何截图（`take_screenshot` / 失败自动截图）后，必须调用 `analyze_screenshot` 用 VLM 判读画面，**禁止用 Read 工具自己看图**。判读结果用于决定下一步（如 `send_key` 跳过对话框、定位失败原因）。`analyze_screenshot` 失败时（VLM 临时不可用）只影响判读，截图本身仍可用。
```

- [ ] **Step 5: 验证四处改动落地**

Run:
```bash
grep -n "analyze_screenshot\|禁止用 Read" "C:/Users/bang/.claude/plugins/marketplaces/kintsugi/plugins/war3-tester/skills/war3-auto-test/SKILL.md"
```
Expected: 至少 5 行命中（截图策略 1 + 工具清单 1 + 常见错误 1 + 操作约束 2）。

---

### Task 3: 版本 bump — plugin.json + CHANGELOG.md

**Files:**
- Modify: `C:\Users\bang\.claude\plugins\marketplaces\kintsugi\plugins\war3-tester\.claude-plugin\plugin.json`
- Modify: `C:\Users\bang\.claude\plugins\marketplaces\kintsugi\plugins\war3-tester\CHANGELOG.md`

**Interfaces:**
- Produces: 版本号 `0.13.19` + 变更记录，让更新可被感知。

> 既有问题：CHANGELOG 顶部最新为 `0.6.1`，而 plugin.json 已 `0.13.18`，长期脱节。本次只在顶部插入 `0.13.19` 记录并注明脱节，不回溯补齐 0.7–0.13（超出范围）。

- [ ] **Step 1: plugin.json 版本号 0.13.18 → 0.13.19**

old_string:
```
  "version": "0.13.18",
```
new_string:
```
  "version": "0.13.19",
```

- [ ] **Step 2: CHANGELOG.md 顶部插入 0.13.19 段**

old_string:
```
# Changelog — war3-tester

## 0.6.1 — 2026-07-11
```
new_string:
```
# Changelog — war3-tester

## 0.13.19 — 2026-07-19

### 文档

- **SKILL.md 强制截图后调用 VLM 判读**：四处改动明确「截图（`take_screenshot` / 失败自动截图）后必须调 `analyze_screenshot` 用 VLM 判读，禁止用 Read 自看」，修复「截图后不主动用视觉模型」的工作流缺口。配合 `~/.claude/settings.json` 配置 `VLM_MODEL`（`analyze_screenshot` 的 model 无兜底，此前一调必报错）。

> 注：CHANGELOG 历史与 plugin.json 版本长期脱节（上一条 0.6.1，plugin.json 已至 0.13.x），既有问题，不在本次范围。

## 0.6.1 — 2026-07-11
```

- [ ] **Step 3: 验证 plugin.json 合法 + 版本号**

Run:
```bash
python -c "import json; d=json.load(open(r'C:/Users/bang/.claude/plugins/marketplaces/kintsugi/plugins/war3-tester/.claude-plugin/plugin.json', encoding='utf-8')); print('version =', d['version'])"
```
Expected: `version = 0.13.19`

---

### Task 4: 本机生效 — 同步 cache 副本 SKILL.md

**Files:**
- Modify: `C:\Users\bang\.claude\plugins\cache\kintsugi\war3-tester\0.13.18\skills\war3-auto-test\SKILL.md`

**Interfaces:**
- Consumes: Task 2 的四处改动（内容相同）。
- Produces: cache 副本（Claude Code 实际加载）立即生效，无需重装插件。

- [ ] **Step 1: 将 Task 2 的四处 Edit 原样应用到 cache 副本**

对 `cache/kintsugi/war3-tester/0.13.18/skills/war3-auto-test/SKILL.md` 执行与 Task 2 Step 1-4 完全相同的四处 Edit（old_string/new_string 一致，因两份文件当前内容相同）。

- [ ] **Step 2: 验证 cache 副本与 marketplaces 源一致**

Run:
```bash
diff "C:/Users/bang/.claude/plugins/marketplaces/kintsugi/plugins/war3-tester/skills/war3-auto-test/SKILL.md" "C:/Users/bang/.claude/plugins/cache/kintsugi/war3-tester/0.13.18/skills/war3-auto-test/SKILL.md" && echo "两份一致" || echo "存在差异"
```
Expected: `两份一致`（diff 无输出）

---

### Task 5: 提交推送 — kintsugi 仓库

**Files:**
- 无新增；提交 Task 2/3 在 `marketplaces/kintsugi/` 产生的改动。

**Interfaces:**
- Consumes: Task 2（SKILL.md）、Task 3（plugin.json、CHANGELOG.md）的改动。
- Produces: 推送到 `fengshibang/kintsugi` master 的 commit（含此前已本地提交的 spec commit `e969bda`）。

> 注：`~/.claude/settings.json` 不在此仓库，不提交。Task 1 的改动属本机配置。

- [ ] **Step 1: 暂存改动（仅 war3-tester 三文件）**

Run:
```bash
KIT="C:/Users/bang/.claude/plugins/marketplaces/kintsugi"
git -C "$KIT" add plugins/war3-tester/skills/war3-auto-test/SKILL.md plugins/war3-tester/.claude-plugin/plugin.json plugins/war3-tester/CHANGELOG.md docs/superpowers/plans/2026-07-19-war3-screenshot-vlm-judge.md
git -C "$KIT" status --short
```
Expected: 四文件（SKILL.md/plugin.json/CHANGELOG.md 显示 `M`，计划文件显示 `A` 或 `??`），无其他意外文件。

- [ ] **Step 2: 提交**

Run:
```bash
KIT="C:/Users/bang/.claude/plugins/marketplaces/kintsugi"
git -C "$KIT" commit -m "feat(war3-tester): SKILL.md 强制截图后调 VLM 判读 + bump 0.13.19

四处改动强制「截图→analyze_screenshot VLM 判读，禁止 Read 自看」；
plugin.json 0.13.18→0.13.19；CHANGELOG 记录（注明与版本历史脱节）。"
```
Expected: `[master <hash>] feat(war3-tester): ...`

- [ ] **Step 3: 推送远端**

Run:
```bash
KIT="C:/Users/bang/.claude/plugins/marketplaces/kintsugi"
git -C "$KIT" push origin master
```
Expected: 推送成功（含 spec commit + 本次 feat commit）。

> ⚠️ 基础设施准则：若 push 失败（认证/网络），停止告知用户，不自行修复。

---

### Task 6: 运行时验证

**Files:**
- 无文件改动；验证 Task 1-4 的实际效果。

**Interfaces:**
- Consumes: Task 1（VLM_MODEL env）、Task 4（cache SKILL.md 生效）。

- [ ] **Step 1: 验证配置层 — analyze_screenshot 不再报「未配置 VLM_MODEL」**

前置：用户已执行 Task 1 Step 3 的 `/mcp` 重连。

调用 MCP 工具（需游戏窗口存在，否则 take_screenshot 报「未找到 War3 窗口」，属正常——此时可只验证 analyze_screenshot 对已有 PNG 的判读）：
1. `take_screenshot(test_name="vlm_verify")` → 记录返回的 `path`
2. `analyze_screenshot(png_path="<上一步 path>")`

Expected: `analyze_screenshot` 返回 `[OK] 截图分析完成` + 画面判读文本（画面状态/UI 元素/是否卡对话框/数值），**不再**出现「未配置 VLM_MODEL」。

- [ ] **Step 2: 验证行为层 — war3-auto-test 流程中截图后主动判读**

跑一次含截图场景的 war3-auto-test 流程（如卡对话框 / 失败自动截图），确认 Claude 在截图后主动调用 `analyze_screenshot` 而非 Read 自看。

Expected: 截图工具返回后，下一步调用是 `analyze_screenshot`（VLM 判读），不是 Read。

> ⚠️ 基础设施准则：若游戏启动 / HTTP 服务 / 编译失败，停止告知用户，不自行修复。

---

## Self-Review

**1. Spec 覆盖：**
- spec 4.1 配置层 VLM_MODEL → Task 1 ✓
- spec 4.2 SKILL.md 四处改动 → Task 2 ✓
- spec 4.3 版本 bump + 推送 → Task 3 + Task 5 ✓
- spec 4.4 cache 同步 → Task 4 ✓
- spec 7 验证 → Task 6 ✓

**2. 占位符扫描：** 无 TBD/TODO；每处改动均有完整 old/new 文本与验证命令 ✓

**3. 类型/文本一致性：** 四处 SKILL.md 改动在 Task 2 与 Task 4（cache 同步）完全一致；版本号 0.13.19 在 Task 3 plugin.json 与 CHANGELOG 一致 ✓
