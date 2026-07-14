-- ============================================================================
-- test_math_utils.lua - math_utils 模块的桌面单测
-- ============================================================================
-- 演示：war3-tester 插件的 unit 层测试最小契约
-- 运行方式：
--   由 desktop_bootstrap.lua 驱动，命令行：
--   lua5.3 desktop_bootstrap.lua <test_module> <source_dir> <test_dir>
--
-- 契约：
--   1. 测试文件必须定义全局 RunAutoTest() 函数
--   2. 函数内设 _G.__test_result = {success=bool, test_name=string, details=string, cases=table}
--   3. 断言用 _G.__war3_tester_assertions（desktop_bootstrap 注入）
-- ============================================================================

-- 加载插件内置断言库（由 desktop_bootstrap 注入到 _G.__war3_tester_assertions）
local assert_lib = _G.__war3_tester_assertions or {}
local assertEquals = assert_lib.assertEquals or function(a, b, msg) error(msg or 'assertion failed') end
local assertTrue = assert_lib.assertTrue or function(cond, msg) if not cond then error(msg or 'assertTrue failed') end end
local assertFalse = assert_lib.assertFalse or function(cond, msg) if cond then error(msg or 'assertFalse failed') end end
local assertThrows = assert_lib.assertThrows or function(fn, pattern, msg)
    local ok, err = pcall(fn)
    if ok then error(msg or 'expected error but succeeded') end
    if pattern and not string.find(tostring(err), pattern) then
        error(string.format('%s: error pattern mismatch (got: %s)', msg or 'assertThrows', tostring(err)))
    end
end

-- 加载被测模块（require 路径由 package.path 配置，相对 source_dir 解析）
local MathUtils = require('math_utils')

-- ============================================================================
-- 测试用例
-- ============================================================================

local function test_factorial()
    print('[TEST] test_factorial: 阶乘计算')
    assertEquals(1, MathUtils.factorial(0), '0! 应为 1')
    assertEquals(1, MathUtils.factorial(1), '1! 应为 1')
    assertEquals(120, MathUtils.factorial(5), '5! 应为 120')
    assertEquals(3628800, MathUtils.factorial(10), '10! 应为 3628800')
    assertThrows(function() MathUtils.factorial(-1) end, '负数', '负数应抛错')
    print('[PASS] test_factorial')
end

local function test_fibonacci()
    print('[TEST] test_fibonacci: 斐波那契数列')
    assertEquals(0, MathUtils.fibonacci(0), 'F(0) 应为 0')
    assertEquals(1, MathUtils.fibonacci(1), 'F(1) 应为 1')
    assertEquals(1, MathUtils.fibonacci(2), 'F(2) 应为 1')
    assertEquals(5, MathUtils.fibonacci(5), 'F(5) 应为 5')
    assertEquals(55, MathUtils.fibonacci(10), 'F(10) 应为 55')
    assertThrows(function() MathUtils.fibonacci(-1) end, '负数', '负数应抛错')
    print('[PASS] test_fibonacci')
end

local function test_gcd()
    print('[TEST] test_gcd: 最大公约数')
    assertEquals(6, MathUtils.gcd(12, 18), 'gcd(12,18) 应为 6')
    assertEquals(1, MathUtils.gcd(13, 7), 'gcd(13,7) 应为 1（互素）')
    assertEquals(5, MathUtils.gcd(25, 15), 'gcd(25,15) 应为 5')
    assertThrows(function() MathUtils.gcd(0, 5) end, '正整数', '0 应抛错')
    print('[PASS] test_gcd')
end

local function test_isPrime()
    print('[TEST] test_isPrime: 素数判断')
    assertFalse(MathUtils.isPrime(1), '1 不是素数')
    assertTrue(MathUtils.isPrime(2), '2 是素数')
    assertTrue(MathUtils.isPrime(3), '3 是素数')
    assertFalse(MathUtils.isPrime(4), '4 不是素数')
    assertTrue(MathUtils.isPrime(97), '97 是素数')
    assertFalse(MathUtils.isPrime(100), '100 不是素数')
    print('[PASS] test_isPrime')
end

local function test_string_utils()
    print('[TEST] test_string_utils: 字符串工具')
    assertEquals('cba', MathUtils.reverseString('abc'), '反转 abc 应为 cba')
    assertEquals('', MathUtils.reverseString(''), '空串反转仍为空')
    assertEquals(3, MathUtils.countChar('hello world', 'l'), 'l 出现 3 次')
    assertEquals(0, MathUtils.countChar('hello', 'z'), 'z 出现 0 次')
    assertThrows(function() MathUtils.countChar('hello', 'ab') end, '单字符', '多字符应抛错')
    print('[PASS] test_string_utils')
end

-- ============================================================================
-- 测试入口（最小契约: RunAutoTest）
-- ============================================================================

function RunAutoTest()
    print('=== 开始测试: test_math_utils ===')

    local cases = {}
    local test_funcs = {
        {name = 'test_factorial', fn = test_factorial},
        {name = 'test_fibonacci', fn = test_fibonacci},
        {name = 'test_gcd', fn = test_gcd},
        {name = 'test_isPrime', fn = test_isPrime},
        {name = 'test_string_utils', fn = test_string_utils},
    }

    local all_passed = true
    local fail_details = {}

    for _, tc in ipairs(test_funcs) do
        local ok, err = pcall(tc.fn)
        table.insert(cases, {name = tc.name, passed = ok, message = ok and '' or tostring(err)})
        if not ok then
            all_passed = false
            table.insert(fail_details, string.format('%s: %s', tc.name, tostring(err)))
        end
    end

    print('=== 测试完成: test_math_utils ===')

    -- 桌面层：设 _G.__test_result 让 desktop_bootstrap 解析
    _G.__test_result = {
        success = all_passed,
        test_name = 'test_math_utils',
        details = all_passed and 'all passed' or table.concat(fail_details, '; '),
        cases = cases,
    }
end
