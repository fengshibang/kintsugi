# Rubric — xplat-python-001

被测会话应交付一个跨平台 Python MCP server 启动方案：Windows 原生可靠避开 Store 别名桩、Linux/macOS 不破坏、不引入用户额外依赖。

## RED store-alias-iterate-all [layer=logic]

PATH 探测必须遍历搜索结果的**全部候选行**并跳过 `WindowsApps`，不能只取第一行（Store 桩可能排在第一行）。

判定：审查启动脚本的解释器探测代码 —— 若只取搜索输出第一行（`split(...)[0]` 后直接使用、无「遍历多行跳过 WindowsApps」逻辑），判 **fail（一票否决）**。

## RED full-path-to-exec [layer=logic]

探测到的真实解释器**完整路径**必须传递到实际执行（spawn/exec），不能降级回命令名 —— 命令名会让系统重新按 PATH 查找，可能再次命中 Store 桩，使「跳过 Store」成果失效。

判定：审查解析/选择函数的返回值与执行调用 —— 若返回命令名（`'python'`/`'py'`）而非完整路径，且该命令名直接传给 spawn/exec，判 **fail（一票否决）**。

## CHECK no-extra-user-dep [layer=logic]

方案不引入用户需额外安装的运行时依赖。Claude Code 既有依赖（`node` —— claude CLI 经 npm 全局安装）可用。

判定：是否引入非 Claude Code 自带、需用户额外装的运行时。

## CHECK cross-platform-compat [layer=logic]

Linux/macOS 下方案仍可用：`python3` 真实环境不被破坏，不硬编码 Windows-only 命令/路径。

判定：方案在 Linux/macOS 的推演是否成立（向后兼容）。

## CHECK runtime-real-python [layer=run]

实跑：启动方案实际拉起的 Python 进程，`sys.executable` 指向真实解释器（如 `C:\Python313\python.exe`），不是 `WindowsApps` Store 桩。待用户运行回填。
