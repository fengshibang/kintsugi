# 参考答案（judge 上下文，非精确匹配）

一次正确执行的预期要点：

- 用一个跨平台启动脚本（wrapper）做 Python 解释器解析 —— `.mcp.json` 是静态 JSON，无法内联探测逻辑。
- 探测顺序：`PYTHON_BIN` 环境变量覆盖 → `python3`（跳过 WindowsApps）→ `python`（跳过 WindowsApps，**遍历所有候选行**）→ `py` 启动器 → 兜底（让报错直观）。
- **遍历跳过**：PATH 搜索（`where`/`command -v`）可能返回多行，Store 别名桩（`WindowsApps`）可出现在任意位置；必须遍历全部行、返回第一个非 Store 的真实路径，不能只取第一行。
- **完整路径传递**：解析得到的【完整路径】直接传给 spawn/exec，不降级回命令名（否则系统重新按 PATH 查找，可能再中 Store 桩）。
- wrapper 语言选 Claude Code 既有依赖（`node`），不引入用户额外装的运行时。
- Linux/macOS：`python3` 真实，直接用；遍历/完整路径逻辑对 Unix 也合法（无 Store 桩，不误伤）。
- 运行验证：spawn 的进程 `sys.executable` = 真实解释器路径，非 `WindowsApps`。
