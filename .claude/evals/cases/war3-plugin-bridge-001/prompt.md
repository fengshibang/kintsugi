# 任务：为 war3-tester 通用插件写「对接已有测试框架项目」的引导适配器

## 背景

`war3-tester` 是一个**通用** war3 测试插件（编译地图 + 启动游戏 + HTTP 接收测试结果），
要适配**所有** war3 项目，不限某框架。它的测试入口注入两份文件到目标项目测试目录：

- `_target_test.lua`：由插件写入，`return` 一个配置表，字段（通用契约）：
  ```lua
  return {
    test_name = 'test_xxx',
    test_file = 'test_xxx.lua',
    test_module = 'test_xxx',           -- 不含前缀的相对模块名（base）
    test_module_prefix = 'script.src.auto-test.',  -- require 路径前缀
    http_host = '127.0.0.1',            -- 测试结果回传的 HTTP 地址
    http_port = 8768,
  }
  ```
- `run_auto_test.lua`：**引导适配器**——本任务要写的文件。它被目标项目的 init.lua 在
  加载测试模块时 require，职责：读 `_target_test.lua` → 设置测试模式标记 → 定义 `RunAutoTest()`
  （由 init.lua 在 `BattleInitCompleted` 事件后调用）→ 跑测试 → HTTP 回传结果。

插件提供通用引导模板 `server/lua_bootstrap.lua`（针对「测试文件自带全局 RunAutoTest」的项目，
加载后立即调用）。但对「已有完整测试框架」的项目，需要**自定义引导适配器**（即本文件）。

## 目标项目 wzns 的特征（你要对接的）

- 测试框架：`TestRunner`（注册用例 / 执行 / HTTP 上报），位于 `map/script/src/auto-test/`
- **require 是点分路径**：`require('script.src.auto-test.TestRunner')`，
  `require('script.src.auto-test.test_skill_a00d')` 等——**没有「相对 require」**，
  裸名 `require('_target_test')` 找不到模块
- init.lua 在 `BattleInitCompleted` 事件后调用全局 `RunAutoTest()`；它还检测全局标记
  `_G.__auto_test_mode`，为 false 时打印「测试已关闭，跳过执行」并**不调用 RunAutoTest**
- 正常游戏时 `_target_test.lua` 不存在，引导适配器必须**静默降级**（不阻断游戏加载）

## 你要产出

写 `run_auto_test.lua`（即 war3-tester 的自定义引导适配器，等价于
`examples/wzns/run_auto_test.framework.lua`），满足：
1. 读 `_target_test.lua` 配置（不存在则静默降级）
2. 设置 `__auto_test_mode` 标记
3. 定义 `RunAutoTest()`：用 `test_module_prefix` 拼出完整 require 路径加载测试模块 →
   调 `TestRunner` + `run_unit_tests` 跑测试 → `exportResults()` HTTP 回传

## ⚠️ 真实对接陷阱（本 case 的核心——以下都是实跑踩过的崩溃级坑，务必避免）

实跑 `test_commit` 全链路时，引导适配器若写错会**静默失效**（不报错，直接测试被跳过 / 超时）。
以下是 3 个真实踩坑的报错与错误写法，你的产出必须规避：

### 陷阱 1：require 裸名 → 测试被静默跳过

错误写法：
```lua
return require('_target_test')   -- ❌ 裸名
```
wzns 框架日志（实跑证据）：
```
[AutoTest] run_auto_test 加载结果：true
[AutoTest] __auto_test_mode = false          -- require 失败 → 标记被置 false
[AutoTest] 测试配置加载失败: nil
[AutoTest] 测试已关闭，跳过执行              -- RunAutoTest 从未被调用，test_commit 超时
```
正解：用 wzns 的点分完整路径 `require('script.src.auto-test._target_test')`
（前缀可从配置或已知常量取）。

### 陷阱 2：test_module 双重前缀 → 模块找不到

错误写法（引导适配器把 `test_module`（已含前缀的完整路径）又拼了一次前缀）：
```lua
local module_name = config.test_module              -- 若它是 'script.src.auto-test.test_xxx'
module_name = config.test_module_prefix .. module_name  -- ❌ → 'script.src.auto-test.script.src.auto-test.test_xxx'
```
实跑报错：
```
module 'script.src.auto-test.script.src.auto-test.test_skill_a00d' not found
```
正解：`_target_test.lua` 的 `test_module` 字段写**不含前缀的 base**（`test_xxx`），
引导适配器拼一次 `test_module_prefix` 得完整路径。**前缀只拼一次**。

### 陷阱 3：HTTP 回传地址硬编码 → 收不到结果

引导适配器 / TestRunner 的 HTTP 上报地址必须从 `_target_test.lua` 的 `http_host`/`http_port`
读取（插件会分配端口，不能硬编码 8766）。

---

任务边界：只写引导适配器 `run_auto_test.lua` 一个文件。不需要改插件的通用层
（`http_receiver` / `mcp_server` 已是正确的）。产出放在测试目录下。
