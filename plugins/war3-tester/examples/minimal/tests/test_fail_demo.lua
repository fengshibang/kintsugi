-- ============================================================================
-- test_fail_demo.lua - 故意失败的测试（验证失败路径）
-- ============================================================================
-- 用于验证 desktop_bootstrap 的失败路径是否正确返回 success=false
-- ============================================================================

-- 加载插件内置断言库
local assert_lib = _G.__war3_tester_assertions or {}
local assertEquals = assert_lib.assertEquals or function(a, b, msg) error(msg or 'assertion failed') end

-- 加载被测模块
local MathUtils = require('math_utils')

-- ============================================================================
-- 故意失败的测试用例
-- ============================================================================

local function test_will_fail()
    print('[TEST] test_will_fail: 故意失败的测试')
    -- 故意写错的断言：2+2 应该等于 4，但我们断言等于 5
    assertEquals(5, MathUtils.factorial(2), '故意失败：2! 应该等于 2，不是 5')
    print('[PASS] test_will_fail')
end

-- ============================================================================
-- 测试入口
-- ============================================================================

function RunAutoTest()
    print('=== 开始测试: test_fail_demo ===')

    local cases = {}
    local ok, err = pcall(test_will_fail)
    table.insert(cases, {name = 'test_will_fail', passed = ok, message = ok and '' or tostring(err)})

    print('=== 测试完成: test_fail_demo ===')

    _G.__test_result = {
        success = ok,
        test_name = 'test_fail_demo',
        details = ok and 'all passed' or tostring(err),
        cases = cases,
    }
end
