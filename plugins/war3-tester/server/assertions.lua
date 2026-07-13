-- ============================================================================
-- assertions.lua - 通用断言库（war3-tester 插件内置）
-- ============================================================================
-- 功能：提供通用断言 API，所有装上 war3-tester 的项目即用。
-- 对齐 wzns TestRunner/TestHelpers 现有 API 风格 + 补 Approx/Throws。
--
-- API 列表：
--   assertEquals(expected, actual [, message])
--   assertNotEquals(unexpected, actual [, message])
--   assertTrue(condition [, message])
--   assertFalse(condition [, message])
--   assertNil(value [, message])
--   assertNotNil(value [, message])
--   assertType(value, expectedType [, message])
--   assertApprox(expected, actual [, tolerance [, message]])  -- 浮点容差
--   assertThrows(fn [, expectedPattern [, message]])           -- pcall 捕获预期错误
--
-- 使用方式（require 路径取决于项目配置的 test_module_prefix）：
--   local A = require('<your_test_module_prefix>_war3_tester.assertions')
--   A.assertEquals(1, 1)
--   A.assertApprox(3.14, math.pi, 0.001)
--   A.assertThrows(function() error('boom') end, 'boom')
--
-- 注：所有断言失败时调用 error()，让外层 pcall 捕获（与 TestRunner/TestCase 一致）。
-- ============================================================================

local Assertions = {}

--- 断言相等
---@param expected any 期望值
---@param actual any 实际值
---@param message string|nil 错误消息（可选）
function Assertions.assertEquals(expected, actual, message)
    if expected ~= actual then
        error(string.format('%s: 期望 [%s], 实际 [%s]',
            message or '断言失败',
            tostring(expected),
            tostring(actual)), 2)
    end
end

--- 断言不相等
---@param unexpected any 不应相等的值
---@param actual any 实际值
---@param message string|nil 错误消息（可选）
function Assertions.assertNotEquals(unexpected, actual, message)
    if unexpected == actual then
        error(string.format('%s: 值不应相等 (%s)',
            message or '断言失败',
            tostring(unexpected)), 2)
    end
end

--- 断言为真
---@param condition boolean 条件
---@param message string|nil 错误消息（可选）
function Assertions.assertTrue(condition, message)
    if not condition then
        error(message or '条件应为真', 2)
    end
end

--- 断言为假
---@param condition boolean 条件
---@param message string|nil 错误消息（可选）
function Assertions.assertFalse(condition, message)
    if condition then
        error(message or '条件应为假', 2)
    end
end

--- 断言为 nil
---@param value any 要检查的值
---@param message string|nil 错误消息（可选）
function Assertions.assertNil(value, message)
    if value ~= nil then
        error(string.format('%s: 期望 nil, 实际 [%s]',
            message or '断言失败',
            tostring(value)), 2)
    end
end

--- 断言非 nil
---@param value any 要检查的值
---@param message string|nil 错误消息（可选）
function Assertions.assertNotNil(value, message)
    if value == nil then
        error(message or '期望非 nil', 2)
    end
end

--- 断言类型
---@param value any 要检查的值
---@param expectedType string 期望类型（如 'number', 'string', 'table'）
---@param message string|nil 错误消息（可选）
function Assertions.assertType(value, expectedType, message)
    local actualType = type(value)
    if actualType ~= expectedType then
        error(string.format('%s: 期望类型 %s, 实际类型 %s',
            message or '类型断言失败',
            expectedType,
            actualType), 2)
    end
end

--- 断言浮点近似相等（容差比较）
---@param expected number 期望值
---@param actual number 实际值
---@param tolerance number|nil 容差（默认 1e-6）
---@param message string|nil 错误消息（可选）
function Assertions.assertApprox(expected, actual, tolerance, message)
    if type(expected) ~= 'number' or type(actual) ~= 'number' then
        error(string.format('assertApprox: 参数必须是 number，期望 %s (%s), 实际 %s (%s)',
            tostring(expected), type(expected),
            tostring(actual), type(actual)), 2)
    end
    local tol = tolerance or 1e-6
    local diff = math.abs(expected - actual)
    if diff > tol then
        error(string.format('%s: 期望 ≈ %s (容差 %s), 实际 %s (差值 %s)',
            message or '近似断言失败',
            tostring(expected), tostring(tol),
            tostring(actual), tostring(diff)), 2)
    end
end

--- 断言函数调用会抛出错误（pcall 捕获）
---@param fn function 要调用的函数
---@param expectedPattern string|nil 期望的错误消息模式（子串匹配，可选）
---@param message string|nil 错误消息（可选，断言失败时的消息）
---@return string err_msg 捕获到的错误消息（成功时返回，供进一步断言）
function Assertions.assertThrows(fn, expectedPattern, message)
    if type(fn) ~= 'function' then
        error('assertThrows: 第一个参数必须是 function', 2)
    end
    local ok, err = pcall(fn)
    if ok then
        error(message or '期望函数抛出错误，但调用成功', 2)
    end
    -- 若指定了 expectedPattern，检查错误消息是否包含该模式
    if expectedPattern then
        local err_str = tostring(err)
        if not err_str:find(expectedPattern, 1, true) then
            error(string.format('%s: 期望错误包含 [%s], 实际错误 [%s]',
                message or '错误模式不匹配',
                expectedPattern,
                err_str), 2)
        end
    end
    return tostring(err)
end

return Assertions
