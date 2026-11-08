-- ============================================================================
-- events.lua - 事件管理与游戏 ECS System 监听器
-- ============================================================================

local events = {}
local bridge = require 'script.src.auto-test.agent.bridge'
local entity_ref = require 'script.src.auto-test.agent.entity_ref'

local recent_events = {}
local MAX_RECENT = 1000
local attached_em = nil

--- 推送通用事件
---@param kind string
---@param data table
function events.push(kind, data)
    data = data or {}
    data.kind = kind
    data.clock = ac and ac.clock and ac.clock() or 0

    table.insert(recent_events, data)
    if #recent_events > MAX_RECENT then
        table.remove(recent_events, 1)
    end

    bridge.event(kind, data)
end

--- 获取指定时间段内的事件
---@param since_clock number
---@return table[]
function events.get_since(since_clock)
    local list = {}
    for _, evt in ipairs(recent_events) do
        if evt.clock and evt.clock >= since_clock then
            table.insert(list, evt)
        end
    end
    return list
end

-- ============================================================================
-- ECS AgentEventSystem：作为标准 System 注册到 Engine 与 EventManager
-- ============================================================================
local AgentEventSystem
if type(class) == 'function' and System then
    ---@class AgentEventSystem : System
    AgentEventSystem = class("AgentEventSystem", System)

    function AgentEventSystem:initialize()
        System.initialize(self)
    end

    function AgentEventSystem:AnyUnitDamaged(evt)
        if not evt or not evt.info then return end
        local src = evt.info[1]
        local target = evt.info[2]
        local dmg_obj = evt.info[3]

        local dmg_val = 0
        if type(dmg_obj) == 'number' then
            dmg_val = dmg_obj
        elseif type(dmg_obj) == 'table' then
            dmg_val = dmg_obj.currentDamage or dmg_obj.damage or 0
        end

        events.push('damage', {
            source = src and entity_ref.get_ref(src) or "none",
            target = target and entity_ref.get_ref(target) or "none",
            damage = dmg_val
        })
    end

    function AgentEventSystem:AnyUnitDeath(evt)
        if not evt or not evt.info then return end
        local killer = evt.info[1]
        local victim = evt.info[2]
        events.push('unit_death', {
            killer = killer and entity_ref.get_ref(killer) or "none",
            victim = victim and entity_ref.get_ref(victim) or "none"
        })
    end
end

local function mount_system(engine, em)
    if not em or attached_em == em then
        return
    end
    attached_em = em

    local sys
    if AgentEventSystem then
        sys = AgentEventSystem()
    else
        -- 离线测试环境无 ECS 基类时的兜底实现
        sys = {
            class = { name = "AgentEventSystem" },
            AnyUnitDamaged = function(_, evt)
                if not evt or not evt.info then return end
                local src, target, dmg_obj = evt.info[1], evt.info[2], evt.info[3]
                local dmg_val = type(dmg_obj) == 'number' and dmg_obj or (type(dmg_obj) == 'table' and (dmg_obj.currentDamage or dmg_obj.damage or 0) or 0)
                events.push('damage', {
                    source = src and entity_ref.get_ref(src) or "none",
                    target = target and entity_ref.get_ref(target) or "none",
                    damage = dmg_val
                })
            end,
            AnyUnitDeath = function(_, evt)
                if not evt or not evt.info then return end
                local killer, victim = evt.info[1], evt.info[2]
                events.push('unit_death', {
                    killer = killer and entity_ref.get_ref(killer) or "none",
                    victim = victim and entity_ref.get_ref(victim) or "none"
                })
            end
        }
    end

    pcall(function()
        em:addListener('AnyUnitDamaged', sys, sys.AnyUnitDamaged)
        em:addListener('AnyUnitDeath', sys, sys.AnyUnitDeath)
        if engine and engine.addSystem and AgentEventSystem then
            engine:addSystem(sys)
        end
    end)
end

--- 订阅核心游戏事件（挂载 AgentEventSystem 到当前状态或 BattleInitCompleted）
function events.init_subscribers()
    if Game and Game.curState then
        local state = Game.curState()
        if state and state.eventManager then
            mount_system(state.engine, state.eventManager)
        end
    end

    -- 若在选难度阶段已启动 Agent，进入 Battle 状态时也会自动挂载到新的 EventManager
    if EventBus and EventBus.once then
        pcall(function()
            EventBus:once('BattleInitCompleted', function(_, engine, eventManager)
                mount_system(engine, eventManager)
            end)
        end)
    end
end

return events
