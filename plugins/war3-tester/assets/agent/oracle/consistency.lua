-- ============================================================================
-- oracle/consistency.lua - 状态一致性 Oracle
-- ============================================================================

local oracle = require 'script.src.auto-test.agent.oracle.init'
local entity_ref = require 'script.src.auto-test.agent.entity_ref'

local dead_tracked_units = {} -- handle -> death_time

oracle.register({
    name = "consistency.dead_entity",
    interval = 1.0,
    severity = "medium",
    check = function(ctx)
        local violations = {}
        if not (Game and Game.curState and Game.curState().engine) then return nil end

        local entities = Game.curState().engine.entities
        if not entities then return nil end

        local now_sec = ctx.sec
        for eid, ent in pairs(entities) do
            if ent.handle then
                local is_dead = false
                if UnitAlive then
                    is_dead = not UnitAlive(ent.handle)
                elseif IsUnitType and UNIT_TYPE_DEAD then
                    is_dead = IsUnitType(ent.handle, UNIT_TYPE_DEAD)
                end

                if is_dead then
                    if not dead_tracked_units[ent.handle] then
                        dead_tracked_units[ent.handle] = now_sec
                    elseif now_sec - dead_tracked_units[ent.handle] > 5.0 then
                        table.insert(violations, {
                            subject = entity_ref.get_ref(ent),
                            msg = "底层单位已死亡超过 5 秒但 ECS 实体未销毁",
                            data = { ref = entity_ref.get_ref(ent), eid = tostring(eid), dead_sec = now_sec - dead_tracked_units[ent.handle] }
                        })
                    end
                else
                    dead_tracked_units[ent.handle] = nil
                end
            end
        end
        return violations
    end
})

oracle.register({
    name = "consistency.buff_expired",
    interval = 1.0,
    severity = "medium",
    check = function(ctx)
        local violations = {}
        if not (Game and Game.curState and Game.curState().engine) then return nil end

        local heroes = Game.curState().engine:getEntitiesWithComponent('HeroComp')
        if not heroes then return nil end

        for _, h in pairs(heroes) do
            if h.buffs then
                for _, buff in ipairs(h.buffs) do
                    local comp = buff:get('BuffComp')
                    if comp and comp.duration > 0 then
                        local remain_frames = comp.duration - comp.frameCount
                        -- 过期超过 50 帧（约 1 秒）未移除
                        if remain_frames < -50 then
                            table.insert(violations, {
                                subject = entity_ref.get_ref(h) .. ":" .. tostring(buff.name),
                                msg = "Buff 已过期超过 1 秒但仍未被移除",
                                data = { ref = entity_ref.get_ref(h), buff = buff.name, expired_frames = -remain_frames }
                            })
                        end
                    end
                    if buff.maxStack == 1 and buff.stack and buff.stack > 1 then
                        table.insert(violations, {
                            subject = entity_ref.get_ref(h) .. ":" .. tostring(buff.name),
                            msg = "不可叠加 Buff 层数大于 1",
                            data = { ref = entity_ref.get_ref(h), buff = buff.name, stack = buff.stack }
                        })
                    end
                end
            end
        end
        return violations
    end
})
