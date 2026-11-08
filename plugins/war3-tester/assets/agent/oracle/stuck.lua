-- ============================================================================
-- oracle/stuck.lua - 移动/行动卡死 Oracle
-- ============================================================================

local oracle = require 'script.src.auto-test.agent.oracle.init'
local entity_ref = require 'script.src.auto-test.agent.entity_ref'

local move_orders_count = 0
local last_hero_pos = nil

function _G.__agent_record_move_order(x, y)
    move_orders_count = move_orders_count + 1
end

oracle.register({
    name = "stuck.hero",
    interval = 3.0,
    severity = "low",
    check = function(ctx)
        if not (Game and Game.curState and Game.curState().engine) then return nil end

        local heroes = Game.curState().engine:getEntitiesWithComponent('HeroComp')
        if not heroes then return nil end

        local h = nil
        for _, ent in pairs(heroes) do
            h = ent
            break
        end
        if not h then return nil end
        if not h:isAlive() then return nil end

        local pt = h.getPoint and h:getPoint()
        if not pt then return nil end

        local cur_x, cur_y = pt[1], pt[2]

        if last_hero_pos and move_orders_count >= 3 then
            local dx = cur_x - last_hero_pos.x
            local dy = cur_y - last_hero_pos.y
            local dist = math.sqrt(dx * dx + dy * dy)

            -- 连续 3 次移动但位移小于 10
            if dist < 10.0 then
                move_orders_count = 0
                last_hero_pos = { x = cur_x, y = cur_y }
                return {
                    {
                        subject = entity_ref.get_ref(h),
                        msg = "英雄连续发布移动指令但位移异常停滞 (可能卡地形)",
                        data = { ref = entity_ref.get_ref(h), dist = dist }
                    }
                }
            end
        end

        last_hero_pos = { x = cur_x, y = cur_y }
        move_orders_count = 0
        return nil
    end
})
