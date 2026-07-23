# Spec — 不卡壳 TDD 闭环(exec_game + 进程清理 + 项目适配生成)

> 日期:2026-07-23 初稿 / 2026-07-24 grilling 三轮演进 + W2 完成
> 状态:ready-for-agent;**W2 已完成**
> 来源:grilling 三轮演进(8 决策 + 项目感知适配生成)+ CONTEXT.md + ADR-0001/0002
> 仓库:war3-tester 插件(marketplace kintsugi);被测项目不改游戏逻辑

---

## 问题陈述

war3-tester 现状无法支撑不卡壳的完整 TDD:AI 经 inspect 通道只能**只读查询**(`inspect_game`),无法**操控**游戏造测试条件;每个 TDD 迭代卡在 ① 启动时旧进程没死透,新游戏卡在 8766 单活冲突;② wzns 启动后弹段位→难度 modal 对话框,锁死游戏循环,连带 inspect 通道失效;③ 测试跑起来 AI 看不到/没法干预,干等结果。

## 解决方案

war3-tester 升级为**项目感知的适配生成器**:提供通用能力(`exec_game` 操控 / `inspect_game` 查询 / 进程清理)+ **项目适配生成**(分析被测项目→生成项目特定适配钩子→持久化→加载)。本次交付:W1 exec_game + W2 进程清理(已完成)+ W3 项目适配生成机制(难度屏蔽首个用例)。

## 架构原则(CONTEXT.md)

- **注入式测试能力**:war3-tester 注入 lua 模块提供测试能力,被测项目不改游戏逻辑。
- **项目感知适配生成**:war3-tester 分析项目实际情况→生成项目特定适配(如难度屏蔽)→持久化→test_commit 加载。**通用的是"分析→生成→持久化→加载"流程;生成产物是项目特定的**。一次性生成,复用。
- **通用性**:war3-tester 不为单一项目特化(不硬编码 wzns 的 `SelectState` 等);项目特定逻辑由适配生成产出。

## 实现决策(grilling 8 条 + 演进)

1. 操控语义模型 = C:`exec_game` 底层任意 Lua + 结构化动作 API 后做。
2. exec/inspect 并存,共享 inspect HTTP 通道(pending 队列 + `/inspect/*` + inspect_handler;mode 标记区分)。
3. 执行模型 = 重启式(保持),常驻热重载作可选增强(未验证)。
4. 卡点① 进程清理:**启动前复查残留,报错不自启**。✅ **W2 完成**(`ExecutorBase.is_war3_clean` + `run_single_test` sleep 后复查)。
5. 卡点② 难度屏蔽:由**项目适配生成**产出(war3-tester 分析 wzns→生成难度屏蔽钩子→持久化→加载),**非硬编码 patch**(通用性;ADR-0001)。modal 对话框锁游戏循环是 runtime 约束。
6. 卡点③ AI 交互 = 操优先(`exec_game` 造条件)+ 查(`inspect_game`)。
7. 通信协议 = 继续 HTTP(ADR-0002)。
8. exec_game 的 TDD 角色 = α(AI 辅助:测试脚本写断言,AI exec/inspect 辅助)。

## 工作单元

| W | 内容 | 状态 |
|---|---|---|
| **W1** | `exec_game`(MCP 工具 + store mode 标记 + inspect_handler exec 分支去 `return` 前缀) | 通用,待 |
| **W2** | 进程清理(`ExecutorBase.is_war3_clean` + `run_single_test` sleep 后复查残留→env_error 不自启) | ✅ 完成,16+3 单测 |
| **W3** | 项目适配生成机制:分析项目(`get_project_info` 增强)→ AI 生成项目特定适配钩子 → 持久化 `_war3_tester/` → test_commit 加载。难度屏蔽 = 首个用例 | 待,含 prototype |

依赖:W3 难度屏蔽是 W1 exec_game 真正可用的前提(不屏蔽对话框,游戏循环被锁,exec/inspect 全失效)。

## 测试决策

- **Seam A — Python module 单测**(`server/*_test.py`):war3-tester 自身逻辑(is_war3_clean / exec store mode / 适配生成)。W2 用此(16+3 case)。
- **Seam B — 游戏内 integration(`test_commit`)**:端到端 + W3 难度屏蔽(跳过 modal 只能真游戏验)。
- 好测试:只测外部行为,不测实现细节。

## 范围外

- 常驻热重载(决策3,可选增强)。
- 自定义 TCP 协议(ADR-0002 否决)。
- 结构化动作 API(决策1 B,exec_game 沉淀后做)。
- 安全护栏(exec 任意 Lua 的误操作防护,后续)。

## 补充说明

- **ADR-0001**:难度屏蔽由项目适配生成产出(非硬编码 patch);modal 对话框锁游戏循环约束。
- **ADR-0002**:通信协议继续 HTTP。
- **W3 prototype 风险**:持久化钩子加载机制(不改 wzns 游戏逻辑)需 prototype 验证(首轮 patch 时机 prototype 已证"运行时 patch 赶不上 SelectState.enter",W3 改为"持久化预生成钩子 + 加载")。
