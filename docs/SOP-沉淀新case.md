# SOP — 沉淀新 eval case（任何开发领域）

> 何时用：师傅带徒弟做**任何开发任务**（迁移 / 建模块 / 建组件 / 接口对接 / 配置物编…）时，
> 徒弟犯了值得记录的错，就按本 SOP 沉淀成 eval case。case 覆盖任何领域，按真实错误沉淀，不预构造。
>
> **路径约定**：框架脚本随插件（`${CLAUDE_PLUGIN_ROOT}/framework/`，只读）；case 数据在项目（`$EVALS_DIR`，默认 `<项目>/.claude/evals`）。下面命令里两者分开引用。

## 何时沉淀（满足任一）

- **崩溃级错误**：运行时静默崩溃 / 功能失效 → 候选 `## RED` 硬线
- **同类反复犯**：同类新错误 ≥2 次 → 说明 CHK / skill 表述有缺陷，必须沉淀 + 强化
- **CHK 未覆盖的新坑**：错误暴露现有 CHK 清单没覆盖的模式

> 不沉淀：一次性笔误、探索性试错的正常碰壁（除非踩中崩溃级红线）。

## 沉淀 5 步

### 1. 建 case 骨架

框架模板在插件只读目录，数据写到项目 `EVALS_DIR`：

```bash
cp -r "${CLAUDE_PLUGIN_ROOT}/framework/templates/case-skill" "$EVALS_DIR/cases/<target>-<seq>"
```

`<target>` 按领域命名（如 `migrate` / `buff` / `system` / `component` / `api`…）。
`<seq>` 三位序号：`001` / `002`…
（下文 `<id>` 即本步创建的目录名 `<target>-<seq>`。）

### 2. 写 `prompt.md`

任务描述 + **真实素材内联**（报错信息 / 代码片段 / 基线文件:行号）。

**铁律**：
- **别在 prompt 里点名要用的 skill** —— "是否触发 skill"要作为 baseline delta 信号（config 开 `baseline:true` 时对比）。点名了信号就废了。
- 内联真实素材，别让被测 agent 去猜；任务边界要清楚。

### 3. 写 `rubric.md`（三层）

每个检查项一个二级标题，按 layer 分层：

```markdown
## CHECK skill-invoked            [layer=logic]
被测是否调用 Skill 加载 <领域 skill> / 触发对应 Workflow。
判定依据：工具列表出现 Skill。
（baseline:true 时此项应 fail → baseline delta 即 skill 触发增量。）

## CHECK <domain-static>          [layer=static]
<机器判定依据，用 auto-pass/auto-fail 命令，在 product/ 下执行，可引用 $CHANGED_FILES>

auto-pass: <命令 exit0=pass>
auto-fail: <命令 exit0=fail>

## CHECK <domain-logic>           [layer=logic]
<师傅 LLM 对照领域规范判定依据，二元可判>

## CHECK runtime-effect           [layer=run]
判定：运行验证（跑测试/跑应用看效果）。待用户回填。
```

- **崩溃级**用 `## RED <id>`（一票否决，fail → 整条 passed=false）
- **写二元判定**（pass/fail 有明确依据），避免笼统"质量打分"——降低 judge 方差

### 4. 写 `expected.md`

符合领域 skill 规范的正解骨架。仅给 judge logic 层做对照参考（非精确匹配）。可只列关键点，不必完整代码。

### 5. 验证 case 本身可跑

```bash
EVALS_DIR=<数据目录>
RUN_DIR="$(bash "${CLAUDE_PLUGIN_ROOT}/framework/runner.sh" "cases/<id>")"
bash "${CLAUDE_PLUGIN_ROOT}/framework/judge.sh" "cases/<id>" "$RUN_DIR"
# 确认 <RUN_DIR>/parsed.json 有 result/tool_uses，<RUN_DIR>/score.json 有 checks 数组
```

- 若 case 含 `[layer=run]` check → score.json 该项 `judged_by:"user"`、`pass:false`、`note:"pending-user"`，正常。
- 跑通即沉淀完成。后续用 `bash "${CLAUDE_PLUGIN_ROOT}/framework/run_all.sh" <target>` 回归（按 target 子串过滤，只跑该领域 case）。

## 「完成信号」对照表 — 通用骨架 + 领域示例

> **通用骨架**（沉淀任何领域的 case 都按这三列填）：
> - **static auto**（机器判）：grep 该领域的文件存在 / 命名规范 / 注册信号，引用 `$CHANGED_FILES`
> - **logic**（师傅 LLM 对照）：对照该领域 skill 规范 + 项目同类实现
> - **run**（用户运行验证）：跑测试/跑应用看效果
>
> ⚠️ **下表是示例（领域特定，源自 war3 项目，仅供参考）**。沉淀你项目的 case 时，按上面的通用骨架，结合你的领域填这三列。

`$CHANGED_FILES` = runner 注入的被测改动文件列表（空格分隔，auto 命令在其上执行）。`<Name>` 等占位按具体 case 替换。

| 领域（示例） | static auto（机器判） | logic（LLM 对照） | run（用户验证） |
|---|---|---|---|
| **建 Buff**（war3 示例） | ① 新文件在 `Buffs/`：`echo "$CHANGED_FILES" \| grep -q "Buffs/"`<br>② Buff ID 以 B 开头（扫文件内容）：`grep -hqE '"B[A-Za-z0-9]+"' $CHANGED_FILES`<br>③ 走 `unit:addBuff` 而非手动 create：`! grep -q "BuffObj\.create" $CHANGED_FILES`<br>④ 继承 `BuffObj`：`grep -q "class(.*BuffObj" $CHANGED_FILES` | 对照 Buff 规范：`unit:addBuff({name, from, duration})`、继承 `BuffObj`、文件在 `Buffs/`、禁手动 create | 运行验证：Buff 持续时间 / 层数 / 触发效果生效 |
| **建系统**（war3 示例） | ① 新文件在 `systems/`：`echo "$CHANGED_FILES" \| grep -q "systems/"`<br>② PascalCase + System 后缀：`echo "$CHANGED_FILES" \| grep -qE "[A-Z][a-zA-Z0-9]*System[A-Za-z0-9]*\.lua"`<br>③ Battle 注册：`grep -q "<Name>" map/script/src/states/Battle.lua`<br>④ 监听事件：`grep -qE "onEvent\|addEventListener" $CHANGED_FILES` | 对照系统规范：命名、注册、事件监听模式（参考项目同类实现） | 运行验证：系统效果生效 |
| **JASS→ECS 迁移**（war3 示例） | ① migrate_status 更新：`grep -rq "<trigId>" docs/migrations/migrate_status.json`<br>② 系统文件命名：`for f in map/script/src/systems/*<NNN>*.lua; do [ -f "$f" ] \|\| exit 1; done` | 对照原 JASS：五件事全覆盖、触发器已禁用 | 运行验证：触发器效果生效 |

> 其余领域（建物品 / 建组件 / 配置 / UI…）按同构模式现写：static = grep 该领域的文件存在/命名/注册信号，logic = 对照领域 skill 该领域规范，run = 运行验证看效果。

## 通用检查项（所有领域 rubric 都建议含）

- `## CHECK skill-invoked [layer=logic]`：被测是否触发 skill / Workflow（baseline delta 信号）
- `## CHECK naming-convention [layer=static]`：命名符合该领域规范（`auto-pass` grep）
- `## CHECK runtime-effect [layer=run]`：运行验证效果（pending-user）

## run 层回填

沉淀的 case 含 run check → judge 标 pending-user → 用户运行验证后：

```bash
# 在 <run-dir>/user-verdict.json 写：
# {"<check-id>":{"pass":true,"note":"效果生效"}}
bash "${CLAUDE_PLUGIN_ROOT}/framework/judge.sh" "cases/<id>" <run-dir> --merge-user
```

summarize 把含 pending 的 case 标「未完成」不计入通过率，回填后才会计入。

## 沉淀后

- 反复 fail 的崩溃级 `## RED` check → 晋升领域 skill 的 CHK 硬红线（硬红线 ≤10，超 10 = skill 表述缺陷需重构）
- 改完 skill → `bash "${CLAUDE_PLUGIN_ROOT}/framework/run_all.sh" <target>` 看通过率是否↑（量化 skill 增益；run_all.sh 按 target 子串过滤，只跑该领域 case）
