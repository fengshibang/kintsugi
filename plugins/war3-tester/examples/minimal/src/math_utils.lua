-- ============================================================================
-- math_utils.lua - 纯 Lua 数学工具模块（零 jass 依赖）
-- ============================================================================
-- 功能：演示纯逻辑模块，用于验证 war3-tester 桌面单测层通用性
-- 特点：
--   1. 不依赖任何 jass 函数（无 CreateUnit、GetUnitName 等）
--   2. 不依赖任何游戏运行时（无 Player、UnitObj 等）
--   3. 纯 Lua 5.3 语法，可在桌面解释器直接运行
-- ============================================================================

local MathUtils = {}

--- 计算阶乘 n!
---@param n number 非负整数
---@return number n 的阶乘
function MathUtils.factorial(n)
    if n < 0 then
        error('阶乘参数不能为负数')
    end
    if n == 0 or n == 1 then
        return 1
    end
    local result = 1
    for i = 2, n do
        result = result * i
    end
    return result
end

--- 计算斐波那契数列第 n 项
---@param n number 非负整数（F(0)=0, F(1)=1, F(2)=1, ...）
---@return number 第 n 项的值
function MathUtils.fibonacci(n)
    if n < 0 then
        error('斐波那契参数不能为负数')
    end
    if n == 0 then return 0 end
    if n == 1 then return 1 end

    local a, b = 0, 1
    for i = 2, n do
        a, b = b, a + b
    end
    return b
end

--- 计算两个数的最大公约数（GCD）
---@param a number 正整数
---@param b number 正整数
---@return number a 和 b 的最大公约数
function MathUtils.gcd(a, b)
    if a <= 0 or b <= 0 then
        error('GCD 参数必须为正整数')
    end
    while b ~= 0 do
        a, b = b, a % b
    end
    return a
end

--- 判断一个数是否为素数
---@param n number 正整数
---@return boolean 是否为素数
function MathUtils.isPrime(n)
    if n < 2 then return false end
    if n == 2 then return true end
    if n % 2 == 0 then return false end

    for i = 3, math.floor(math.sqrt(n)), 2 do
        if n % i == 0 then
            return false
        end
    end
    return true
end

--- 反转字符串
---@param str string 输入字符串
---@return string 反转后的字符串
function MathUtils.reverseString(str)
    return str:reverse()
end

--- 统计字符串中某个字符出现的次数
---@param str string 输入字符串
---@param char string 要统计的字符（单字符）
---@return number 出现次数
function MathUtils.countChar(str, char)
    if #char ~= 1 then
        error('char 参数必须是单字符')
    end
    local count = 0
    for i = 1, #str do
        if str:sub(i, i) == char then
            count = count + 1
        end
    end
    return count
end

return MathUtils
