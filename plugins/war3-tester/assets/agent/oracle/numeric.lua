-- ============================================================================
-- oracle/numeric.lua - 数值健全性 Oracle
-- ============================================================================

local oracle = require 'script.src.auto-test.agent.oracle.init'
local entity_ref = require 'script.src.auto-test.agent.entity_ref'

local function is_invalid_num(val)
    if type(val) ~= 'number' then return true end
    if val ~= val then return true end -- NaN
    if val == math.huge or val == -math.huge then return true end
    return false
end

oracle.register({
    name = "numeric.hp_range",
    interval = 0.5,
    severity = "high",
    check = function(ctx)
        local violations = {}
        if not (Game and Game.curState and Game.curState().engine) then return nil end

        local heroes = Game.curState().engine:getEntitiesWithComponent('HeroComp')
        if not heroes then return nil end

        for _, h in pairs(heroes) do
            if h.handle and h:isAlive() then
                local hp = h.getHp and h:getHp() or (GetUnitState and GetUnitState(h.handle, UNIT_STATE_LIFE)) or 0
                local max_hp = h.getMaxHp and h:getMaxHp() or (GetUnitState and GetUnitState(h.handle, UNIT_STATE_MAX_LIFE)) or 1
                local ref = entity_ref.get_ref(h)

                if is_invalid_num(hp) or hp < 0 or hp > (max_hp * 1.5 + 100) then
                    table.insert(violations, {
                        subject = ref,
                        msg = "生命值超出正常范围异常",
                        data = { ref = ref, hp = tostring(hp), max_hp = tostring(max_hp) }
                    })
                end

                local mp = h.getMana and h:getMana() or 0
                local max_mp = h.getMaxMana and h:getMaxMana() or 1
                if is_invalid_num(mp) or mp < 0 then
                    table.insert(violations, {
                        subject = ref,
                        msg = "真气/魔法值异常",
                        data = { ref = ref, mp = tostring(mp), max_mp = tostring(max_mp) }
                    })
                end
            end
        end
        return violations
    end
})

oracle.register({
    name = "numeric.attr_sanity",
    interval = 1.0,
    severity = "medium",
    check = function(ctx)
        local violations = {}
        if not (Game and Game.curState and Game.curState().engine) then return nil end

        local heroes = Game.curState().engine:getEntitiesWithComponent('HeroComp')
        if not heroes then return nil end

        for _, h in pairs(heroes) do
            local umc = h:get('UnitModelComp')
            if umc and umc.attributeMap then
                local check_attrs = {'攻击', '防御', '力道', '身法', '根骨', '悟性'}
                for _, attr_name in ipairs(check_attrs) do
                    local obj = umc.attributeMap:get(attr_name)
                    if obj and obj.get then
                        local val = obj:get()
                        if is_invalid_num(val) or val < -0.001 then
                            table.insert(violations, {
                                subject = entity_ref.get_ref(h) .. ":" .. attr_name,
                                msg = "核心属性值异常: " .. attr_name,
                                data = { ref = entity_ref.get_ref(h), attr = attr_name, value = tostring(val) }
                            })
                        end
                    end
                end
            end
        end
        return violations
    end
})
