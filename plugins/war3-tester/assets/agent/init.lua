-- ============================================================================
-- init.lua - War3 LLM Agent 模块引导加载入口
-- ============================================================================

local agent = {
    started = false
}

local function notify_screen(msg)
    print(msg)
    if DisplayTextToPlayer and GetLocalPlayer then
        pcall(function()
            local p = GetLocalPlayer()
            if p then
                DisplayTextToPlayer(p, 0, 0, msg)
            end
        end)
    end
end

local function check_single_player()
    if not (GetPlayerController and Player) then return true end
    local human_count = 0
    for i = 0, 15 do
        local p = Player(i)
        if GetPlayerController(p) == MAP_CONTROL_USER and GetPlayerSlotState(p) == PLAYER_SLOT_STATE_PLAYING then
            human_count = human_count + 1
        end
    end
    return human_count <= 1
end

function agent.start(from_chat)
    if agent.started then
        if from_chat then
            local bridge = require 'script.src.auto-test.agent.bridge'
            notify_screen(string.format("|cff00ff00[Agent]|r 已在运行中 (version: %d, 管道: \\\\.\\pipe\\war3_agent)", bridge.version()))
        end
        return true
    end

    -- 1. 检查单机运行约束（防止联机 desync）
    if not check_single_player() then
        notify_screen("|cffff6600[Agent]|r 检测到多个真人玩家，出于防掉线机制禁用 Agent")
        return false
    end

    -- 2. 加载 bridge 模块
    local ok_b, bridge = pcall(require, 'script.src.auto-test.agent.bridge')
    if not ok_b or not bridge or not bridge.available then
        if from_chat then
            notify_screen("|cffff4444[Agent]|r agent_bridge 未加载或不可用，请确认 agent_bridge.dll / .asi 已放入目录")
        else
            print("[Agent] agent_bridge 不可用或加载失败，静默跳过")
        end
        return false
    end

    -- 3. 初始化管道通信服务
    if not bridge.init() then
        notify_screen("|cffff4444[Agent]|r 管道服务初始化失败，跳过 Agent 启动")
        return false
    end

    -- 4. 挂钩错误日志（不破坏原有行为，额外广播给 Agent 与 Oracle）
    local events = require 'script.src.auto-test.agent.events'

    do
        if log and log.error then
            local _orig_log_error = log.error
            log.error = function(...)
                _orig_log_error(...)
                local parts = {}
                local args = {...}
                for i = 1, #args do
                    parts[i] = tostring(args[i])
                end
                local msg = table.concat(parts, " ")
                local tb = debug.traceback()
                if _G.__agent_record_lua_error then
                    _G.__agent_record_lua_error(msg, tb)
                end
                events.push('lua_error', { source = 'log.error', message = msg, traceback = tb })
            end
        end

        local ok_ecs, ecs_module = pcall(require, 'script.lib.ecs')
        if ok_ecs and ecs_module and ecs_module.debugError then
            local _orig_ecs_error = ecs_module.debugError
            ecs_module.debugError = function(msg)
                _orig_ecs_error(msg)
                local tb = debug.traceback()
                if _G.__agent_record_lua_error then
                    _G.__agent_record_lua_error(msg, tb)
                end
                events.push('lua_error', { source = 'ecs.debugError', message = tostring(msg), traceback = tb })
            end
        end
    end

    -- 5. 订阅游戏事件
    events.init_subscribers()

    -- 6. 启动 runtime 调度循环
    local runtime = require 'script.src.auto-test.agent.runtime'
    runtime.start()

    agent.started = true
    notify_screen(string.format("|cff00ff00[Agent]|r 已启动 (mode=%s, version=%d, 监听 \\\\.\\pipe\\war3_agent)",
        tostring(bridge.mode), bridge.version()))
    return true
end

_G.__start_war3_agent = agent.start

return agent
