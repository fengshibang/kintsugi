---
description: 引导沉淀新eval case(把徒弟错误案例化,任何开发领域)
argument-hint: <target-序号 如 buff-001 / system-001 / migrate-002>
allowed-tools: ["Bash(${CLAUDE_PLUGIN_ROOT}/framework/*:*)", "Read", "Write"]
---

引导沉淀一个新 eval case，把徒弟犯的错案例化。case id：`$ARGUMENTS`

按 `docs/SOP-沉淀新case.md` 走。**先问用户**这个 case 要覆盖什么错误 / 什么领域 / 徒弟当时怎么错的，然后据回答组装四件套：

1. **建骨架**（Bash）：
   `cp -r "${CLAUDE_PLUGIN_ROOT}/framework/templates/case-skill" "$PWD/.claude/evals/cases/$ARGUMENTS"`
   （数据目录默认项目 `.claude/evals`；框架模板从插件只读拷贝）

2. **写 `prompt.md`**：任务描述 + **真实素材内联**（报错 / 代码片段 / 行号）。**铁律：别在 prompt 点名要用的 skill**——"是否触发 skill"要作为 baseline delta 信号。

3. **写 `rubric.md`**（三层）：`[layer=static]` + `auto-pass:`/`auto-fail:` grep（在 product/ 下，引用 `$CHANGED_FILES`）；`[layer=logic]` 师傅对照领域规范；`[layer=run]` 运行验证（pending-user）；崩溃级用 `## RED <id>`。参考 SOP 的「完成信号对照表（示例）」。

4. **写 `expected.md`**：符合领域规范的正解骨架（logic 层对照参考，非精确匹配）。

5. **写 `config.json`**：`baseline:true` / `budget_usd` / `timeout_secs` / `isolate:true`。

6. **验证 case 可跑**（Bash）：
   `EVALS_DIR="$PWD/.claude/evals" && RD="$(bash "${CLAUDE_PLUGIN_ROOT}/framework/runner.sh" "cases/$ARGUMENTS")" && bash "${CLAUDE_PLUGIN_ROOT}/framework/judge.sh" "cases/$ARGUMENTS" "$RD"`
   确认 `<RD>/parsed.json` 有 result/tool_uses、`<RD>/score.json` 有 checks 数组。

跑通即沉淀完成。汇报：四件套内容要点 + 验证结果（score.json 的 checks）。
