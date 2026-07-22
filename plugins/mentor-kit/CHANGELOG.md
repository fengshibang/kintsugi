# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.4.0] - 2026-07-22

**重定位**：从"训练徒弟"改为"师傅审查基建 + 硬红线传承"。理论基础——弱模型无状态、权重不可调，无法训练；in-context 注入对弱模型只有"硬红线内联进 spawn prompt"一条可靠通道，长 skill 正文 / 自觉加载基本失效。机制迭代的是师傅手里的规范库（审查 rubric + 硬红线），不是弱模型本身。

### Removed（Breaking）
- **多徒弟编排**整套：拆分判断 / decomposition / worktree 并行 / 集成徒弟 / part·integrate·decompose 三级沉淀 / 拆分率·集成失败率·并行度指标——均为纸面设计，框架代码零实现，且让 haiku 弱模型跑 `git merge` 解冲突风险高
- **rework 三阶段**（R1摸索/R2给标准/R3给正解）整套：`/mentor-kit:rework` 命令 + `framework/mentor-rework.sh` + `framework/lib/rework_stages.py`——本质是"喂弱模型"，与新定位冲突
- **毕业标准**（N=5/K=1）+ "返工率随迭代单调下降"机制有效性叙事——无状态弱模型不存在"毕业"，框架代码零实现

### Changed
- 全文术语：去"徒弟"（暗示可训练的人），改"弱模型 / 被审查产出"；"师徒试错循环"→"审查→沉淀→硬红线传承"
- `mentor-protocol` skill：Overview 重写并补理论基石（弱模型无状态不可训 / in-context 唯一通道 / 硬红线内联唯一可靠 / 迭代的是师傅规范库）；核心循环改为「审查→沉淀→晋升→传承」四步；三层检查强化 static auto 为首选（绕过弱模型不可靠）
- `commands/mentor.md`：删拆分判断 + 多徒弟流程，步骤 4 `fail→rework` 改为 `fail→沉淀`；`allowed-tools` 删 `Bash(git worktree/merge/checkout/branch:*)`（eval 隔离走 framework 内部）

### 验证
- 删剩框架脚本 `bash -n` / `py_compile` 全过；`plugin.json` JSON 有效
- 全仓库 grep 无 rework / 多徒弟 / 毕业标准 / N=5 / 返工率 悬空残留（`worktree` / `K=3` 仅余 eval 隔离义 / rework 上限义）

## [0.3.0] - 2026-07-10

framework 支持 **Windows 原生 / Git Bash**（逻辑零改动；WSL / macOS / Linux 完全向后兼容）。

### Added
- `framework/lib/cli.sh` 新增 `PYTHON_BIN` 解释器解析器：按 `python3 → python → py` 顺序探测，**跳过 WindowsApps Store 别名桩**（App Execution Alias，不同启动上下文行为不一致、不可靠），可用 `PYTHON_BIN` 环境变量强制覆盖。与 `war3-tester/scripts/install_service.bat` 的 python 探测策略一致
- `CLAUDE_BIN` 解析器加 `claude.cmd` 兜底（Windows npm 全局），可用 `CLAUDE_BIN` 环境变量覆盖
- 新增 `plugins/mentor-kit/.gitattributes`：强制 LF 行尾，防止 git `autocrlf` 在 Windows checkout 时把 `.sh`/`.py` 转 CRLF 致 bash 报错（作用域仅限 mentor-kit，不波及其他插件）

### Changed
- `runner.sh` / `judge.sh` / `run_all.sh`：所有 `python3` 调用统一改为 `"$PYTHON_BIN"`
- `run_all.sh`：`./summarize.py` → `"$PYTHON_BIN" ./summarize.py`（摆脱 shebang 依赖）
- `.py` 文件（含 shebang `#!/usr/bin/env python3`）零改动——统一通过 `"$PYTHON_BIN" file.py` 调用，shebang 不参与执行

### 验证
- **Windows（MINGW64）实测**：`PYTHON_BIN` 解析到 `/c/Python313/python`（真身，非 Store 桩）；`bash -n` 脚本全过；stdin+argv / 跑 .py / `python -c` 三种调用姿势通过；MINGW bash 5.2 对 CRLF 容忍（含 heredoc 体）
- **跨平台解析器 mock**：Linux / WSL / 纯 py Windows / 全无 四类环境选中结果均正确；Linux/WSL 首选真实 `python3`，行为与旧版完全等价（零回归）

### 已知限制
- `--max-budget-usd` 在第三方中转 API（`ANTHROPIC_BASE_URL` 指向非官方）上可能被忽略：在 case 的 `config.json` 里调大 `budget_usd` 即可
- 真机 Linux 端到端尚未跑（当前为 Windows 机器）：Linux 侧为静态扫描 + 解析器逻辑 mock 验证，等价性强

## [0.1.0] - 2026-06-24

首个可发布版本。从 rouge_lua 项目抽出师傅审查 + eval 框架，插件化、领域中立。

### Added
- 通用审查协议 skill `mentor-protocol`（角色词化，去 glm/qwen/war3 痕迹）
- 3 个命令：`mentor` / `evals` / `new-case`，均走 `${CLAUDE_PLUGIN_ROOT}` + `EVALS_DIR` 注入
- eval 框架：`runner` / `judge` / `run_all` / `summarize` + `lib/` + `rubrics/` + `templates/`
- 自描述 marketplace（`.claude-plugin/marketplace.json`）
- 文档：`docs/README.md`（安装 / 前置 / 度量）+ `docs/SOP-沉淀新case.md`
- `LICENSE`（MIT）、根 `README.md`、`CHANGELOG.md`、GitHub Actions 语法检查（`.github/workflows/check.yml`）

### Changed
- `framework/lib/cli.sh` 解耦 `FRAMEWORK_DIR`（框架，只读，按 `BASH_SOURCE` 推算）/ `EVALS_DIR`（数据，显式 env 强制注入，不猜 `$PWD`）
- `framework/judge.sh` 的 `lib/` + `rubrics/` 引用改指 `$FRAMEWORK_DIR`
- 全程角色词化（师傅 / 弱模型），无模型名硬编码

### 验证
- 框架 `bash -n` 全通过；Python 脚本 `py_compile` 通过
- 路径解耦验证通过（`FRAMEWORK_DIR` / `EVALS_DIR` / `REPO_ROOT` 三者正确分离；未注入 `EVALS_DIR` 时守卫生效）
- 端到端 `run_all.sh` 回归：待首次实际使用补跑
