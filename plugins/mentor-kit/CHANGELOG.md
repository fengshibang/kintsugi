# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

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
