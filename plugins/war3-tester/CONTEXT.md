# War3 Tester

通用 War3 地图自动测试 MCP 插件:编译地图、启动游戏,AI 经 HTTP 双向通道驱动游戏并回收测试结果,支撑 TDD 闭环。

## Language

### 架构原则

**注入式测试能力**:
war3-tester 把 lua 模块注入被测项目(`_war3_tester/` 目录,如 `inspect_handler`/`assertions`/`jass_mock`/`run_auto_test`),在游戏加载时提供测试能力。**被测项目零代码改动**——查询、操控、初始化编排都由注入的模块实现,war3-tester 不要求项目为测试改自己的游戏逻辑。
_Avoid_: 插件改造、项目适配、monkey-patch(是实现手段,非概念)

### AI ↔ 游戏双向通道

**inspect 通道**:
AI 与运行中游戏的双向通道。AI 把 Lua 代码提交进 pending 队列,游戏端轮询拉取、`load` 执行、回传结果。由 `/inspect/pending`(GET)+ `/inspect/result`(POST)+ 游戏端 `inspect_handler.lua` 构成。`inspect_game` 与 `exec_game` 共用此通道。
_Avoid_: HTTP 通道、命令通道

**inspect_game**:
只读查询工具。AI 提交 Lua 表达式,游戏端以 `return` 前缀求值并回传值,**无副作用**。
_Avoid_: 查询、evaluate、probe

**exec_game**:
带副作用操控工具。AI 提交 Lua 语句块,游戏端执行(可改游戏态),可选回传返回值。与 `inspect_game` 共享 inspect 通道。
_Avoid_: 操控、控制、inject、execute

### 项目感知

**项目适配生成**:
war3-tester 分析被测项目的实际情况(启动交互/结构),为其生成项目特定的适配钩子(如难度屏蔽),持久化后 test_commit 加载复用。**通用的是"分析→生成→持久化→加载"流程;生成出来的钩子是项目特定的**。一次性生成,不每次重生成——项目首次适配时生成一次,后续测试复用。难度屏蔽是首个用例。
_Avoid_: 项目特化、硬编码适配、运行时 patch
