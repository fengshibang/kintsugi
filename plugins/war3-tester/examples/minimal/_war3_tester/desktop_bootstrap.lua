-- ============================================================================
-- desktop_bootstrap.lua - 桌面测试引导（war3-tester 插件内置）
-- ============================================================================
-- 功能：桌面 Lua 环境下跑纯逻辑测试，不依赖 BattleInitCompleted 等游戏事件
-- 机制：desktop_runner.py 调用本文件，传入测试模块路径
-- 注意：
--   1. 本文件由 desktop_runner.py 通过 lua5.3 执行
--   2. 加载顺序：jass_mock → assertions → 被测模块 → 测试文件
--   3. 测试文件须定义 RunAutoTest() 函数
--   4. 结果以 JSON 格式输出到 stdout，供 desktop_runner.py 解析
-- ============================================================================

-- 命令行参数解析（由 desktop_runner.py 传入）
-- 格式：lua5.3 desktop_bootstrap.lua <test_module> <source_dir> <test_dir>
--   test_module: 测试模块全名（含 prefix，如 '<prefix>.test_xxx' 或 'test_xxx'）
--   source_dir:  源码根目录绝对路径（用于 package.path，让项目点分 require 能解析）
--   test_dir:    测试目录绝对路径（用于 package.path，让 _war3_tester/ 文件能解析）
local args = {...}
if #args < 3 then
    print('{"success":false,"error":"用法: lua5.3 desktop_bootstrap.lua <test_module> <source_dir> <test_dir>"}')
    os.exit(1)
end

local test_module = args[1]
local source_dir = args[2]
local test_dir = args[3]

-- 统一路径分隔符为 /（Lua 在 Windows/Linux 都接受 /）
local function normalize_path(p)
    return (p:gsub('\\', '/'))
end

source_dir = normalize_path(source_dir)
test_dir = normalize_path(test_dir)

-- 配置 package.path（通用，基于 source_dir 和 test_dir 动态推导，不硬编码项目路径）
-- 让项目点分 require（如 'script.src.xxx'）能相对 source_dir 解析：
--   require('script.src.xxx') -> 查找 source_dir/script/src/xxx.lua
-- 让 _war3_tester/ 下的文件能相对 test_dir 解析：
--   require('_war3_tester.jass_mock') -> 查找 test_dir/_war3_tester/jass_mock.lua
-- 让裸名测试模块（prefix 为空时）能相对 test_dir 解析：
--   require('test_xxx') -> 查找 test_dir/test_xxx.lua
package.path = test_dir .. '/?.lua;' .. test_dir .. '/?/init.lua;'
                .. source_dir .. '/?.lua;' .. source_dir .. '/?/init.lua;'
                .. package.path

-- 辅助函数：输出 JSON 格式结果
local function output_result(success, test_name, details, cases, error_msg)
    local result = {
        success = success,
        test_name = test_name or 'unknown',
        details = details or '',
        cases = cases or {},
        error = error_msg,
    }
    -- 简单 JSON 序列化（避免依赖 cjson）
    local function serialize(val, indent)
        indent = indent or 0
        local t = type(val)
        if t == 'string' then
            return string.format('%q', val)
        elseif t == 'number' or t == 'boolean' then
            return tostring(val)
        elseif t == 'nil' then
            return 'null'
        elseif t == 'table' then
            local parts = {}
            local is_array = #val > 0 or next(val) == nil
            if is_array then
                for i, v in ipairs(val) do
                    table.insert(parts, serialize(v, indent + 2))
                end
                return '[' .. table.concat(parts, ',') .. ']'
            else
                for k, v in pairs(val) do
                    table.insert(parts, string.format('%q:%s', tostring(k), serialize(v, indent + 2)))
                end
                return '{' .. table.concat(parts, ',') .. '}'
            end
        else
            return string.format('%q', tostring(val))
        end
    end
    print(serialize(result))
end

-- 加载 jass_mock（graceful，缺失时静默跳过）
-- require 路径用裸名 '_war3_tester.jass_mock'，相对 test_dir 查找
-- （package.path 已配置 test_dir/?.lua，故解析为 test_dir/_war3_tester/jass_mock.lua）
local jass_mock = nil
pcall(function()
    jass_mock = require('_war3_tester.jass_mock')
    if jass_mock and jass_mock.install then
        jass_mock.install()
    end
end)

-- 加载 assertions（graceful）
-- 同理，用裸名 '_war3_tester.assertions' 相对 test_dir 查找
local assertions = nil
pcall(function()
    assertions = require('_war3_tester.assertions')
    if assertions then
        _G.__war3_tester_assertions = assertions
    end
end)

-- 加载测试模块
local test_ok, test_err = pcall(function()
    -- 清除缓存，确保重新加载
    package.loaded[test_module] = nil
    return require(test_module)
end)

if not test_ok then
    output_result(false, test_module, '', {}, string.format('测试模块加载失败: %s', tostring(test_err)))
    os.exit(0)
end

-- 检查 RunAutoTest 是否存在
if type(RunAutoTest) ~= 'function' then
    local mod = package.loaded[test_module]
    if type(mod) == 'table' and type(mod.RunAutoTest) == 'function' then
        RunAutoTest = mod.RunAutoTest
    else
        output_result(false, test_module, '', {}, '测试文件未定义 RunAutoTest() 函数')
        os.exit(0)
    end
end

-- 捕获 stdout（测试文件可能 print 调试信息）
local stdout_capture = {}
local original_print = print
local function capture_print(...)
    local args = {...}
    local parts = {}
    for i, v in ipairs(args) do
        table.insert(parts, tostring(v))
    end
    table.insert(stdout_capture, table.concat(parts, '\t'))
end

-- 临时替换全局 print
_G.print = capture_print

-- 调用 RunAutoTest
local run_ok, run_err = pcall(RunAutoTest)

-- 恢复原始 print
_G.print = original_print

-- 输出捕获的 stdout
local captured_output = table.concat(stdout_capture, '\n')

-- 解析测试结果（测试文件应通过 HTTP POST 上报，但桌面模式下我们尝试从全局变量获取）
-- 约定：测试文件可将结果存入 _G.__test_result = {success, test_name, details, cases}
local test_result = _G.__test_result or {}

if not run_ok then
    -- RunAutoTest 调用失败
    output_result(false, test_result.test_name or test_module, captured_output, test_result.cases or {},
                  string.format('RunAutoTest 调用失败: %s', tostring(run_err)))
else
    -- RunAutoTest 调用成功
    output_result(
        test_result.success ~= false,  -- 默认成功，除非显式标记失败
        test_result.test_name or test_module,
        test_result.details or captured_output,
        test_result.cases or {},
        nil
    )
end

-- 卸载 jass_mock（若已安装）
if jass_mock and jass_mock.uninstall then
    pcall(jass_mock.uninstall)
end

os.exit(0)
