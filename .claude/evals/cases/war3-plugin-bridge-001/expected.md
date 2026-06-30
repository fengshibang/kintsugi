# 参考答案（给 judge 做上下文，非精确匹配标准）

一次正确执行的预期要点（参考 `examples/wzns/run_auto_test.framework.lua` 修复后版本）：

- **require 完整点分路径**：`require('script.src.auto-test._target_test')`（或用配置前缀拼），
  禁裸名 `require('_target_test')`。pcall 包裹，失败静默降级。
- **静默降级**：`_target_test.lua` 不存在 → `_G.__auto_test_mode = false; return`，不阻断游戏。
- **设置标记**：`_G.__auto_test_mode = true`（让 init.lua 驱动 BattleInitCompleted）。
- **模块名只拼一次前缀**：
  ```lua
  local module_name = config.test_module   -- base，不含前缀
  if config.test_module_prefix and config.test_module_prefix ~= '' then
      module_name = config.test_module_prefix .. module_name
  end
  ```
- **HTTP 地址从配置读**：`http_host`/`http_port` 从 `_target_test.lua` 取，禁硬编码 8766。
- **定义 RunAutoTest()**（由 init.lua 在 BattleInitCompleted 后调用）：
  `TestRunner:create` → `require(module_name)` 加载测试模块 →
  `require('script.src.auto-test.run_unit_tests')` → `_G._RunRegisteredTests(runner)` →
  `runner:exportResults()` HTTP 回传。

## 这 3 个陷阱为何是崩溃级（实跑根因记录）

| 陷阱 | 静默失效表现 | 根因 |
|------|-------------|------|
| require 裸名 | `__auto_test_mode=false` → 测试跳过 → test_commit 超时 | wzns 无相对 require，裸名找不到模块 |
| 双重前缀 | `module not found: ...auto-test.script.src.auto-test.test_xxx` | test_module 已含前缀又拼一次 |
| HTTP 硬编码 | 收不到结果 / 端口不对 | 插件分配的端口与硬编码不一致 |

> 附带教训（非本 case 范畴，记录备查）：实跑还暴露 wzns 既有 bug
> `map/script/lib/util/json.lua` 的 `escape_char_map` 被损坏（控制字符值未转义），
> 致 `json.encode` 不转义换行 → HTTP body 破坏头部 → Werkzeug 400。对接真实项目时，
> 「验证客户端实际输出的数据格式」是 run 层必查项。
