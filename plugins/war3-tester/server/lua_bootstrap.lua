-- ============================================================================
-- lua_bootstrap.lua - 通用测试引导模板
-- ============================================================================
-- 功能：读取 _target_test.lua 配置 → 加载测试文件 → 调用 RunAutoTest()
-- 机制：test_commit 在编译前写入 _target_test.lua，本文件读取并执行
-- 注意：正常游戏时 _target_test.lua 不存在，require 必须静默降级
-- ============================================================================
-- 【红线 9】只做四件事：
-- 1. 读 _target_test.lua 配置
-- 2. 按 test_module_prefix 加载测试文件
-- 3. 游戏启动后调用测试文件的 RunAutoTest()
-- 4. 文档化「测试文件须自行 HTTP POST 结果到 8766」
-- ============================================================================

-- 尝试加载测试配置（正常游戏时文件不存在，必须静默降级）
local config = nil
local ok, result = pcall(function()
    -- TODO: 待验证 - 此处 require 路径取决于 _target_test.lua 与引导脚本同目录
    -- 若 war3 lua 不支持相对 require，可能需要改为 dofile 或其他方式
    -- 当前假设：_target_test.lua 与 run_auto_test.lua 同目录，可用相对 require
    return require('_target_test')
end)

if not ok then
    -- _target_test.lua 不存在，静默退出（不阻断游戏加载）
    return
end

config = result

-- 验证配置结构
if type(config) ~= 'table' or not config.test_name or not config.test_file then
    print('[lua_bootstrap] 配置格式错误，需要 {test_name, test_file}')
    return
end

print('')
print('========================================')
print('        自动化测试引导已加载')
print('========================================')
print(string.format('测试名称: %s', config.test_name))
print(string.format('测试文件: %s', config.test_file))
print('========================================')
print('')

-- ============================================================================
-- 加载测试文件
-- ============================================================================
-- 【红线 10】加载机制由 test_module_prefix 控制：
-- - 空串 = 同目录加载（引导脚本与测试文件同目录）
-- - 非空 = prefix..name 走 require（如 'some.prefix.'）
-- ============================================================================

local test_module = config.test_module or config.test_file:gsub('%.lua$', '')

-- 如果配置了 test_module_prefix，拼接完整模块名
if config.test_module_prefix and config.test_module_prefix ~= '' then
    test_module = config.test_module_prefix .. test_module
end

print(string.format('[lua_bootstrap] 加载测试模块: %s', test_module))

-- 清除缓存，确保重新加载
package.loaded[test_module] = nil

local loadOk, loadErr = pcall(function()
    require(test_module)
end)

if not loadOk then
    print(string.format('[lua_bootstrap] ✗ 测试模块加载失败: %s', tostring(loadErr)))
    -- TODO: 待验证 - 加载失败时如何上报？
    -- 测试文件应自行 HTTP POST 结果到 8766，但加载失败时测试文件可能未执行
    -- 此处可选择：1) 静默失败 2) 尝试 HTTP 上报
    -- 当前选择：静默失败，由 test_commit 超时处理
    return
end

print('[lua_bootstrap] ✓ 测试模块加载成功')

-- ============================================================================
-- 定义 RunAutoTest 函数（由游戏启动后调用）
-- ============================================================================
-- 【契约】测试文件须定义全局函数 RunAutoTest()，执行测试逻辑并 HTTP 上报
-- 上报格式：POST http://<host>:8766/result
-- Body: { "test_name": "<name>", "success": true|false, "details": "...", "cases": [...] }
-- ============================================================================

-- 检查测试文件是否定义了 RunAutoTest
if type(RunAutoTest) ~= 'function' then
    print('[lua_bootstrap] ✗ 测试文件未定义 RunAutoTest() 函数')
    -- 尝试从模块中获取
    local mod = package.loaded[test_module]
    if type(mod) == 'table' and type(mod.RunAutoTest) == 'function' then
        RunAutoTest = mod.RunAutoTest
        print('[lua_bootstrap] ✓ 从模块中获取 RunAutoTest 函数')
    else
        print('[lua_bootstrap] ✗ 无法获取 RunAutoTest 函数，测试将无法执行')
        return
    end
end

print('[lua_bootstrap] RunAutoTest 函数已就绪，立即调用')

-- ============================================================================
-- 【F3 修复】调用 RunAutoTest 的代码路径
-- ============================================================================
-- 【契约说明】
-- 通用引导脚本没有框架 init.lua 的 BattleInitCompleted 事件可挂。
-- 方案：直接调用 RunAutoTest()，由目标项目保证：
--   1. 引导脚本在游戏启动后被加载（通过 require 或 dofile）
--   2. RunAutoTest() 在被调用时游戏已初始化完成
--
-- 若目标项目需要延迟调用（如等待单位创建），可在自己的初始化逻辑中
-- 手动调用 RunAutoTest()，而非依赖引导脚本的自动调用。
-- ============================================================================

print('[lua_bootstrap] 尝试调用 RunAutoTest()...')
local autoTestOk, autoTestErr = pcall(RunAutoTest)
if not autoTestOk then
    print(string.format('[lua_bootstrap] ✗ RunAutoTest 调用失败: %s', tostring(autoTestErr)))
    print('[lua_bootstrap] 请确保游戏已初始化完成，或由目标项目在合适时机手动调用 RunAutoTest()')
else
    print('[lua_bootstrap] ✓ RunAutoTest 调用成功')
end

-- ============================================================================
-- 文档化：测试文件须自行 HTTP POST 结果到接收端
-- ============================================================================
-- 【契约说明】
-- 测试文件（test_file）须实现以下功能：
-- 1. 定义全局函数 RunAutoTest()
-- 2. 在 RunAutoTest() 中执行测试逻辑
-- 3. 通过 HTTP POST 上报结果到 http://<host>:8766/result
--
-- HTTP 上报格式：
-- POST /result
-- Content-Type: application/json
-- Body: {
--   "test_name": "<测试名称>",
--   "success": true|false,
--   "details": "<详细说明>",
--   "cases": [
--     {"name": "<用例名>", "success": true|false, "message": "..."},
--     ...
--   ]
-- }
--
-- 【运行层待验证】
-- war3 1.27 lua 的 HTTP 上报具体 API 需从项目现有实现提取
-- 不同项目可能有不同的 HTTP 客户端实现方式
-- ============================================================================
