# 难度屏蔽由项目适配生成产出(非硬编码 patch)

war3-tester 通用,不为单一项目特化。难度屏蔽(及任何启动交互适配)由**项目适配生成**产出:war3-tester 分析被测项目(发现 `SelectState`/`DifficultySelectSystem`/modal 对话框这套启动交互)→ 生成项目特定的难度屏蔽钩子 → 持久化(`_war3_tester/`)→ test_commit 加载复用。换项目(不同启动交互),分析它→生成对应适配。**通用的是"分析→生成→持久化→加载"流程,生成产物是项目特定的**。一次性生成,不每次重生成。

> 演进:本 ADR 初版曾定为"monkey-patch wzns SelectState"(硬编码),grilling 中被否决——违反通用性(其他项目没有 SelectState)。改为项目适配生成。

## 为什么不用 AI exec_game 选难度 / 为什么必须屏蔽对话框

war3 modal 对话框弹出后**锁死游戏循环**——`ac.loop`/`ac.wait` 连带失效,而 inspect/exec 通道恰恰靠 `ac.loop`(200ms 轮询)工作。对话框锁定期间 `exec_game`/`inspect_game` 本身就死,AI 调不动。故必须**根本不弹对话框**(屏蔽),而非在对话框期间靠 AI 操控。

## 约束(代码不可见)

war3 `DialogSystem` 的 modal 对话框会 pause 游戏主循环——这是 runtime 行为,代码里看不出"对话框锁 `ac.loop`"。没有这个认知会误判"AI `exec_game` 选难度"可行,从而把精力浪费在不通的方案上。

## W3 实现路径(项目适配生成)

- 分析项目(`get_project_info` 增强,识别启动交互模式)。
- AI 生成项目特定的难度屏蔽钩子(一次性,持久化到 `_war3_tester/`)。
- test_commit 加载已生成的钩子。
- prototype 验证:持久化钩子加载机制(不改 wzns 游戏逻辑)。首轮"运行时 patch SelectState.enter"prototype 已证时机不可行(注入赶不上 enter),W3 改为"预生成持久钩子 + 加载"。
