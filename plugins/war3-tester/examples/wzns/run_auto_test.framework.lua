-- ============================================================================
-- run_auto_test.framework.lua - wzns 框架适配器引导（范例）
-- ============================================================================
-- 本文件是 examples/wzns/ 下的「框架适配器范例」，展示：已有完整测试框架
-- （TestRunner + init.lua BattleInitCompleted 钩子）的 war3 项目，如何写一个
-- 引导，把自己的测试框架桥接到 war3-tester 通用插件的 RunAutoTest 契约。
--
-- 与通用引导（server/lua_bootstrap.lua）的区别：
--   - 通用引导：测试文件自带全局 RunAutoTest()，引导加载后立即调用
--   - 本框架引导：测试文件用 TestRunner:register 注册用例，本引导把 TestRunner
--     包装成 RunAutoTest，由框架 init.lua 在 BattleInitCompleted 事件触发执行
--
-- 来源：提取自原 wzns 项目 scripts/mcp_war3_tester.py 的 RUN_AUTO_TEST_TEMPLATE
-- ============================================================================

-- 测试模式标记（auto-test/init.lua 检测此标记以自动进入 Battle）
_G.__auto_test_mode = true

-- 尝试加载测试配置（正常游戏时文件不存在，必须静默降级）
-- 【v0.2 改造】使用通用 _target_test.lua 字段（test_name/test_file/test_module/test_module_prefix/http_host/http_port）
-- 【修复】wzns 的 require 是点分路径，必须用完整模块名 script.src.auto-test._target_test
--        （裸名 require('_target_test') 在 wzns 打包路径下找不到，导致 __auto_test_mode 被置 false）
local config = nil
local TEST_MODULE_PREFIX = 'script.src.auto-test.'
local ok, result = pcall(require, TEST_MODULE_PREFIX .. '_target_test')

if not ok then
    -- _target_test.lua 不存在，静默退出（不阻断游戏加载）
    _G.__auto_test_mode = false
    return
end

config = result

-- 验证配置结构（通用字段）
if type(config) ~= 'table' or not config.test_name or not config.test_file then
    print('[run_auto_test] 配置格式错误，需要 {test_name, test_file}')
    _G.__auto_test_mode = false
    return
end

-- 构建模块名（优先使用 test_module，fallback 到 test_file 去后缀）
local module_name = config.test_module or config.test_file:gsub('%.lua$', '')
if config.test_module_prefix and config.test_module_prefix ~= '' then
    module_name = config.test_module_prefix .. module_name
end

-- HTTP 上报地址（通用字段）
local http_host = config.http_host or '127.0.0.1'
local http_port = config.http_port or 8766

print('')
print('========================================')
print('        自动化测试入口已加载')
print('========================================')
print(string.format('测试名称: %s', config.test_name))
print(string.format('测试文件: %s', config.test_file))
print(string.format('测试模块: %s', module_name))
print(string.format('HTTP 上报: http://%s:%s/result', http_host, http_port))
print('========================================')
print('')

-- ============================================================================
-- 同步模式：使用 TestRunner 框架
-- ============================================================================
-- 定义 RunAutoTest 函数，由 init.lua 在 BattleInitCompleted 后调用
function RunAutoTest()
    print('')
    print('========================================')
    print(string.format('        执行同步测试: %s', config.test_name))
    print('========================================')
    print('')

    if type(set_current_test_name) == 'function' then
        set_current_test_name(config.test_name)
    end

    local TestRunner = require('script.src.auto-test.TestRunner')
    local runner = TestRunner:create(config.test_name)
    TestRunner._current = runner

    print(string.format('[RunAutoTest] 加载测试模块: %s', module_name))
    package.loaded[module_name] = nil
    local loadOk, loadErr = pcall(function()
        require(module_name)
    end)

    if not loadOk then
        print(string.format('[RunAutoTest] ✗ 模块加载失败: %s', tostring(loadErr)))
        runner:record(module_name .. ' (加载)', false, tostring(loadErr))
        runner:exportResults()
        TestRunner._current = nil
        return
    end

    print(string.format('[RunAutoTest] ✓ 模块加载成功'))

    require('script.src.auto-test.run_unit_tests')

    if type(_G._RunRegisteredTests) == 'function' then
        _G._RunRegisteredTests(runner)
    else
        print('[RunAutoTest] ✗ _RunRegisteredTests 函数未定义')
        runner:record('_RunRegisteredTests', false, '函数未定义')
    end

    -- 发送 HTTP 结果
    runner:exportResults()

    TestRunner._current = nil
    print('')
    print('========================================')
    print(string.format('        测试完成: %s', config.test_name))
    print('========================================')
    print('')
end

print('[run_auto_test] 同步模式：RunAutoTest 函数已定义，等待 BattleInitCompleted')

-- ============================================================================
-- 异步模式说明（注释保留）
-- ============================================================================
-- 若测试文件自带全局 RunAutoTest（异步场景），可改为：
--
-- package.loaded[module_name] = nil
-- require(module_name)
-- print('[run_auto_test] 异步模式：目标模块已加载，等待 BattleInitCompleted 调用 RunAutoTest')
--
-- 此时不需要本文件定义 RunAutoTest，由测试文件自行提供。
-- ============================================================================
