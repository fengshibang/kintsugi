-- ============================================================================
-- inspect_handler.lua - 运行时对象查询处理器
-- ============================================================================
-- 功能：auto-test 模式开启时，定期轮询 MCP 服务器的 /inspect/pending 端点，
--       获取待求值的 Lua 表达式，用 load 求值后将结果 POST 回 /inspect/result。
--       这样 AI 通过 MCP 的 inspect_game 工具可查询游戏内任意状态。
-- 协议：
--   GET  /inspect/pending  → {"id":"<id>","expr":"<lua表达式>"} 或 {}（无查询）
--   POST /inspect/result   ← {"id":"<id>","value":"<结果文本>"} 或 {"id":"<id>","error":"<错误文本>"}
-- 安全：
--   - load 求值用 pcall 包裹，求值失败不崩游戏
--   - poll_once 整体用 pcall 兜底，HTTP/JSON 异常不崩游戏
--   - ac.loop 回调额外 pcall 包裹
--   - 结果截断前 2000 字符防爆
-- ============================================================================

local HttpClient = require('script.lib.util.http_socket')
local json = require('script.lib.util.json')

local PENDING_URL = 'http://127.0.0.1:8766/inspect/pending'
local RESULT_URL  = 'http://127.0.0.1:8766/inspect/result'

-- 结果文本最大长度，防止 table tostring 爆掉 HTTP body
local MAX_RESULT_LEN = 2000

local _timer_handle = nil
local _started = false

--- 截断字符串到指定长度
local function truncate(s, max_len)
    if type(s) ~= 'string' then
        s = tostring(s)
    end
    if #s > max_len then
        return s:sub(1, max_len) .. '...(truncated, total ' .. #s .. ' chars)'
    end
    return s
end

--- 单次轮询：拉取待查询表达式 → load 求值 → 回传结果
-- 整个函数被外层 pcall 包裹，任何异常不会崩游戏
local function poll_once()
    -- 1. GET /inspect/pending（超时 2s，无 callback 同步调用）
    local ok, response = HttpClient.get(PENDING_URL, nil, 2)
    if not ok or not response then
        return  -- HTTP 失败，graceful 跳过
    end

    -- 2. 解析 JSON（json.decode 返回 val, err）
    local data, err = json.decode(response)
    if err then
        return  -- JSON 解析失败，graceful 跳过
    end

    -- 3. 检查是否有待查询（无查询时 MCP 返回 {}，data.id 为 nil）
    local id = data.id
    if not id or id == '' then
        return  -- 无查询，直接 return
    end

    local expr = data.expr
    if not expr or expr == '' then
        -- 有 id 但无表达式，回传错误
        HttpClient.post(RESULT_URL, {
            id = id,
            error = 'empty expression'
        }, nil, 2)
        return
    end

    -- 4. 用 load 求值 Lua 表达式（pcall 包裹，求值失败不崩游戏）
    local eval_ok, result = pcall(function()
        local fn = load('return ' .. expr)
        if not fn then
            error('load() returned nil for expression: ' .. expr)
        end
        return fn()
    end)

    -- 5. POST 结果回 MCP
    if eval_ok then
        local value_str = truncate(tostring(result), MAX_RESULT_LEN)
        HttpClient.post(RESULT_URL, {
            id = id,
            value = value_str
        }, nil, 2)
    else
        local err_str = truncate(tostring(result), MAX_RESULT_LEN)
        HttpClient.post(RESULT_URL, {
            id = id,
            error = err_str
        }, nil, 2)
    end
end

--- 启动轮询定时器（200ms 间隔）
local function start()
    if _started then
        return  -- 防止重复启动
    end
    _started = true

    print("[InspectHandler] 启动运行时查询轮询（200ms 间隔）")

    -- ac.loop(interval_ms, callback)：callback 接收 timer 句柄 t
    -- 额外 pcall 包裹 poll_once，确保任何异常不影响游戏循环
    _timer_handle = ac.loop(200, function(t)
        pcall(poll_once)
    end)
end

return { start = start }
