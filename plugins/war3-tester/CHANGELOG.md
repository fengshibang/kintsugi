# Changelog — war3-tester

## 0.2.0 — 2026-06-30

首个**全链路实跑验证通过**的可用版本（test_skill_a00d 测试通过，端到端 29.6s 自动）。

### 修复（实跑发现的 3 个对接 bug）
- **framework.lua**：`require('_target_test')` 裸名 → 完整点分路径 `script.src.auto-test._target_test`
  （wzns 等点分 require 框架下裸名找不到模块，致 `__auto_test_mode=false` 测试被静默跳过）
- **http_receiver `/result`**：严格 `request.json` → 容错 `get_json(force=True, silent=True)` + `get_data`+`json.loads` 兜底
  （对接非标准 HTTP 客户端时 strict 模式判 400）
- **mcp_server `test_module`**：含前缀完整路径 + framework.lua 又拼 prefix → 双重前缀模块找不到；
  改为写不含前缀的 base，由引导脚本拼一次 prefix

### 新增
- eval case `war3-plugin-bridge-001`（沉淀上述通用插件对接真实项目的崩溃级坑）
- 设计 spec：win_proxy Windows 服务一键安装（NSSM 方案，待实现）—— 见 `docs/superpowers/specs/`

## 0.1.0 — 2026-06-29
- 初始版本：通用 MCP 层（server/）+ war3-auto-test skill + wzns 框架适配器范例
- marketplace 双注册（mentor-kit + war3-tester）
