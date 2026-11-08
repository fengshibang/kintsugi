-- ============================================================================
-- runtime.lua - Agent 运行调度、状态机与主线程冻结步进控制
-- ============================================================================

local runtime = {}
local bridge = require 'script.src.auto-test.agent.bridge'
local protocol = require 'script.src.auto-test.agent.protocol'
local observe = require 'script.src.auto-test.agent.observe'
local actions = require 'script.src.auto-test.agent.actions'
local setup = require 'script.src.auto-test.agent.setup'
local events = require 'script.src.auto-test.agent.events'
local oracle = require 'script.src.auto-test.agent.oracle.init'

local MODE_FREE = 'free'
local MODE_STEP = 'step'
local FREEZE_MAX_SEC = 600.0

local state = {
    mode = MODE_FREE,
    frozen = false,
    run_until = nil,
    pending_act = nil,
    act_start_clock = 0,
    act_results = {}
}

--- 统一求值 inspect 表达式
local function eval_inspect(expr)
    if not expr or type(expr) ~= 'string' then
        return nil, "INVALID_EXPR"
    end

    local fn, err = load("return " .. expr)
    if not fn then
        fn, err = load(expr)
    end
    if not fn then
        return nil, "SYNTAX_ERROR: " .. tostring(err)
    end

    local ok, res = pcall(fn)
    if not ok then
        return nil, "RUNTIME_ERROR: " .. tostring(res)
    end
    return res, nil
end

--- 完成并回复挂起的 act 请求
local function finish_act()
    if not state.pending_act then return end

    local now_clock = ac and ac.clock and ac.clock() or 0
    local ran_frames = now_clock - state.act_start_clock
    local since_events = events.get_since(state.act_start_clock)
    local obs = observe.snapshot({ detail = "brief", mode = state.mode })

    bridge.reply(state.pending_act.id, true, {
        results = state.act_results,
        ran_frames = ran_frames,
        events = since_events,
        observation = obs
    })

    state.pending_act = nil
    state.run_until = nil
    state.act_results = {}

    if state.mode == MODE_STEP then
        state.frozen = true
    end
end

--- 命令分发处理
---@param req table
local function dispatch(req)
    local id = req.id
    local rtype = req.type
    local payload = req.payload or {}

    if rtype == "status" then
        bridge.reply(id, true, {
            mode = state.mode,
            frozen = state.frozen,
            frame = ac and ac.clock and ac.clock() or 0
        })

    elseif rtype == "set_mode" then
        local new_mode = payload.mode
        if new_mode == MODE_FREE or new_mode == MODE_STEP then
            state.mode = new_mode
            if new_mode == MODE_STEP and not state.pending_act then
                state.frozen = true
            elseif new_mode == MODE_FREE then
                state.frozen = false
            end
            bridge.reply(id, true, { mode = state.mode, frozen = state.frozen })
        else
            bridge.reply(id, false, { code = "BAD_REQUEST", message = "Invalid mode: " .. tostring(new_mode) })
        end

    elseif rtype == "freeze" then
        state.frozen = true
        bridge.reply(id, true, { frozen = true })

    elseif rtype == "resume" then
        state.frozen = false
        bridge.reply(id, true, { frozen = false })

    elseif rtype == "observe" then
        local obs = observe.snapshot({
            detail = payload.detail or "full",
            radius = payload.radius or 1200,
            mode = state.mode
        })
        bridge.reply(id, true, obs)

    elseif rtype == "inspect" then
        local val, err = eval_inspect(payload.expr)
        if err then
            bridge.reply(id, false, { code = "INSPECT_ERROR", message = err })
        else
            bridge.reply(id, true, { result = val })
        end

    elseif rtype == "setup" then
        local ok, err = setup.execute(payload.cmd, payload.args)
        if ok then
            bridge.reply(id, true, { cmd = payload.cmd, success = true })
        else
            bridge.reply(id, false, { code = "SETUP_ERROR", message = err or "Setup command failed" })
        end

    elseif rtype == "act" then
        local act_list = payload.actions or {}
        local results = actions.execute_batch(act_list)

        if state.mode == MODE_STEP then
            local run_sec = math.max(0.1, math.min(10.0, payload.run_seconds or 1.0))
            local run_ms = run_sec * 1000.0

            state.act_results = results
            state.act_start_clock = ac and ac.clock and ac.clock() or 0
            state.run_until = state.act_start_clock + run_ms
            state.pending_act = req
            state.frozen = false -- 解除冻结推进游戏
        else
            -- free 模式立即回传
            bridge.reply(id, true, {
                results = results,
                observation = observe.snapshot({ detail = "brief", mode = state.mode })
            })
        end

    else
        bridge.reply(id, false, { code = "BAD_REQUEST", message = "Unknown request type: " .. tostring(rtype) })
    end
end

--- 安全分发命令（捕获异常并保证必回包，避免客户端超时死等）
local function safe_dispatch(req)
    if not req then return end
    local ok, err = xpcall(function()
        dispatch(req)
    end, debug.traceback)
    if not ok then
        bridge.log("[Runtime] Dispatch error: " .. tostring(err))
        if req.id then
            bridge.reply(req.id, false, {
                code = "LUA_RUNTIME_ERROR",
                message = tostring(err)
            })
        end
    end
end

--- 启动调度主循环
function runtime.start()
    bridge.log("[Runtime] Starting Agent runtime loop")

    -- 默认使用 10ms (10 tick) 循环
    ac.loop(10, function()
        -- 1. 运行态
        if not state.frozen then
            for _ = 1, 8 do
                local req = bridge.poll(0)
                if not req then break end
                safe_dispatch(req)
            end

            oracle.tick()

            if state.pending_act and ac.clock() >= state.run_until then
                local ok, err = xpcall(finish_act, debug.traceback)
                if not ok and state.pending_act then
                    local failed_id = state.pending_act.id
                    state.pending_act = nil
                    state.run_until = nil
                    bridge.reply(failed_id, false, { code = "ACT_FINISH_ERROR", message = tostring(err) })
                end
            end

            if not state.frozen then
                return
            end
        end

        -- 2. 冻结态（主线程 Hard Freeze 阻塞循环）
        local hold_start = os.clock()
        while state.frozen do
            local req = bridge.poll(100)
            if req then
                safe_dispatch(req)
            end

            -- 看门狗超时保护 (600s)
            if (os.clock() - hold_start) > FREEZE_MAX_SEC then
                events.push('agent_watchdog', { reason = "Freeze timeout reached 600s" })
                state.frozen = false
                break
            end
        end
    end)
end

return runtime
