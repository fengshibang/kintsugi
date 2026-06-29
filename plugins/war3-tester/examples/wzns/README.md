# examples/wzns — 本框架（wzns ECS）接入范例

本目录展示「已有完整 Lua 测试框架的 war3 项目」如何接入 war3-tester 通用插件。
wzns 是 war3-tester 插件的源生项目（插件从此剥离而来），其测试体系最完整，
适合作「框架适配器」的范例。

## wzns 测试体系概述

| 组件（`map/script/src/auto-test/`） | 作用 |
|------|------|
| `TestRunner.lua` | 测试运行器：注册用例、执行、记录结果、HTTP 上报（`exportResults`）|
| `run_unit_tests.lua` | 同步执行注册的用例（`_G._RunRegisteredTests`）|
| `init.lua` | 检测 `_G.__auto_test_mode` 标记 → 自动进入 Battle → 在 `BattleInitCompleted` 调用 `RunAutoTest` |
| `TestScenario.lua` | 异步测试场景基类 |
| `test_*.lua` | 具体测试（用 `TestRunner:register` 注册用例）|

## 与通用契约的差异

通用插件契约（见 `skills/war3-auto-test/SKILL.md`）要求：测试文件定义全局 `RunAutoTest()`，
通用引导（`server/lua_bootstrap.lua`）加载后**立即调用**。

wzns 不同：
- 测试文件用 `TestRunner:register` 注册用例，**不直接定义 `RunAutoTest` 全局函数**
- 框架 `init.lua` 在 `BattleInitCompleted` 事件触发执行（非立即）
- 因此需要一个**适配器引导**（本目录 `run_auto_test.framework.lua`）：把 TestRunner 机制包装成 `RunAutoTest`，并设置 `__auto_test_mode` 标记让 `init.lua` 驱动

## 接入配置

在项目根 `config.json` 配置：

```json
{
  "test": {
    "test_dir": "map/script/src/auto-test",
    "test_module_prefix": "script.src.auto-test.",
    "test_bootstrap_template": "examples/wzns/run_auto_test.framework.lua"
  },
  "compile": { "output_name": "MoeHero.w3x" }
}
```

- `test_dir`：wzns 测试目录（相对 `source_dir`）
- `test_module_prefix`：框架打包的 require 路径前缀（让 `require` 走 `script.src.auto-test.<name>`）
- `test_bootstrap_template`：指向本目录的框架适配器引导，实现无缝接入
- `output_name`：wzns 地图名

**配置后即可无缝接入**：`test_commit` 会自动使用自定义引导模板，无需手动覆盖。

## 范例文件说明

| 文件 | 说明 |
|------|------|
| `run_auto_test.framework.lua` | wzns 框架适配器引导（含 `TestRunner`/`__auto_test_mode`/sync 模式 + async 模式注释说明）|

> 注：本目录文件**故意包含框架专属符号**（`TestRunner`、`script.src.auto-test`、`__auto_test_mode` 等）——这是「框架范例」的本质。插件的**通用层**（`server/`、`skills/`、`commands/`）不含任何框架符号，已通过审查验证。
