# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.3.0] - 2026-07-10

framework 支持 **Windows 原生 / Git Bash**（逻辑零改动；WSL / macOS / Linux 完全向后兼容）。

### Added
- `framework/lib/cli.sh` 新增 `PYTHON_BIN` 解释器解析器：按 `python3 → python → py` 顺序探测，**跳过 WindowsApps Store 别名桩**（App Execution Alias，不同启动上下文行为不一致、不可靠），可用 `PYTHON_BIN` 环境变量强制覆盖。与 `war3-tester/scripts/install_service.bat` 的 python 探测策略一致
- `CLAUDE_BIN` 解析器加 `claude.cmd` 兜底（Windows npm 全局），可用 `CLAUDE_BIN` 环境变量覆盖
- 新增 `plugins/mentor-kit/.gitattributes`：强制 LF 行尾，防止 git `autocrlf` 在 Windows checkout 时把 `.sh`/`.py` 转 CRLF 致 bash 报错（作用域仅限 mentor-kit，不波及其他插件）

### Changed
- `runner.sh` / `judge.sh` / `mentor-rework.sh` / `run_all.sh`：所有 `python3` 调用统一改为 `"$PYTHON_BIN"`（共 21 处）
- `run_all.sh`：`./summarize.py` → `"$PYTHON_BIN" ./summarize.py`（摆脱 shebang 依赖）
- `.py` 文件（含 shebang `#!/usr/bin/env python3`）零改动——统一通过 `"$PYTHON_BIN" file.py` 调用，shebang 不参与执行

### 验证
- **Windows（MINGW64）实测**：`PYTHON_BIN` 解析到 `/c/Python313/python`（真身，非 Store 桩）；`bash -n` 5 脚本全过；stdin+argv / 跑 .py / `python -c` 三种调用姿势通过；MINGW bash 5.2 对 CRLF 容忍（含 heredoc 体）
- **跨平台解析器 mock**：Linux / WSL / 纯 py Windows / 全无 四类环境选中结果均正确；Linux/WSL 首选真实 `python3`，行为与旧版完全等价（零回归）

### 已知限制
- `--max-budget-usd` 在第三方中转 API（`ANTHROPIC_BASE_URL` 指向非官方）上可能被忽略：在 case 的 `config.json` 里调大 `budget_usd` 即可
- 真机 Linux 端到端尚未跑（当前为 Windows 机器）：Linux 侧为静态扫描 + 解析器逻辑 mock 验证，等价性强

## [0.2.0] - 2026-06-26

### Added
- 多徒弟编排：师傅根据任务需要判断拆分，并行 spawn 多个徒弟（各自 worktree 隔离），集成徒弟负责 merge + 冲突解决
- 三类错误沉淀：part 级 / 集成级（`integrate-<seq>`）/ 拆分判断级（`decompose-<seq>`）
- 多徒弟场景度量指标：拆分率 / 集成失败率 / 并行度
- 多徒弟场景冒烟测试流程

## [0.1.0] - 2026-06-24

首个可发布版本。从 rouge_lua 项目抽出师徒试错机制 + eval 框架，插件化、领域中立。

### Added
- 通用师傅协议 skill `mentor-protocol`（角色词化，去 glm/qwen/war3 痕迹）
- 4 个命令：`mentor` / `evals` / `rework` / `new-case`，均走 `${CLAUDE_PLUGIN_ROOT}` + `EVALS_DIR` 注入
- eval 框架：`runner` / `judge` / `mentor-rework` / `run_all` / `summarize` + `lib/` + `rubrics/` + `templates/`
- 自描述 marketplace（`.claude-plugin/marketplace.json`）
- 文档：`docs/README.md`（安装 / 前置 / 度量）+ `docs/SOP-沉淀新case.md`
- `LICENSE`（MIT）、根 `README.md`、`CHANGELOG.md`、GitHub Actions 语法检查（`.github/workflows/check.yml`）

### Changed
- `framework/lib/cli.sh` 解耦 `FRAMEWORK_DIR`（框架，只读，按 `BASH_SOURCE` 推算）/ `EVALS_DIR`（数据，显式 env 强制注入，不猜 `$PWD`）
- `framework/judge.sh` / `mentor-rework.sh` 的 `lib/` + `rubrics/` 引用改指 `$FRAMEWORK_DIR`
- 全程角色词化（师傅 / 徒弟），无模型名硬编码

### 验证
- 框架 `bash -n` 全通过；4 个 Python 脚本 `py_compile` 通过
- 路径解耦验证通过（`FRAMEWORK_DIR` / `EVALS_DIR` / `REPO_ROOT` 三者正确分离；未注入 `EVALS_DIR` 时守卫生效）
- 端到端 `run_all.sh` 回归：待首次实际使用补跑
