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
        local seen_handles = {}

        for eid, ent in pairs(entities) do
            -- 严格过滤：必须包含 UnitModelComp（排除 PlayerObj 等非单位实体），且排除等待复活的英雄实体 (HeroComp)
            if ent.handle and ent.get and ent:get('UnitModelComp') ~= nil and ent:get('HeroComp') == nil then
                seen_handles[ent.handle] = true
                local is_dead = (ent.isAlive and not ent:isAlive()) or false

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

        -- 清理已从 entities 中移除的句柄记录，防止表内存泄漏
        for h, _ in pairs(dead_tracked_units) do
            if not seen_handles[h] then
                dead_tracked_units[h] = nil
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
