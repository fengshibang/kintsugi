-- RushSlide 的 TweenSystem 替代实现
-- 替代 YDWETimerPatternRushSlide
local jass = require 'jass.common'
local Easing = require 'script.lib.util.Easing'

-- 地图边界缓存（yd_Map* 是 war3map.j 全局变量，Lua 侧无法引用，
-- 用 ac/common.lua 导出的全局函数 GetCameraBound* 和常量 CAMERA_MARGIN_* 计算）
local mapBounds = nil
local function getMapBounds()
    if not mapBounds then
        local minX = GetCameraBoundMinX and GetCameraBoundMinX() or 0
        local maxX = GetCameraBoundMaxX and GetCameraBoundMaxX() or 0
        local minY = GetCameraBoundMinY and GetCameraBoundMinY() or 0
        local maxY = GetCameraBoundMaxY and GetCameraBoundMaxY() or 0
        local marginL = GetCameraMargin and GetCameraMargin(CAMERA_MARGIN_LEFT) or 0
        local marginR = GetCameraMargin and GetCameraMargin(CAMERA_MARGIN_RIGHT) or 0
        local marginB = GetCameraMargin and GetCameraMargin(CAMERA_MARGIN_BOTTOM) or 0
        local marginT = GetCameraMargin and GetCameraMargin(CAMERA_MARGIN_TOP) or 0
        mapBounds = {
            minX = minX - marginL,
            maxX = maxX + marginR,
            minY = minY - marginB,
            maxY = maxY + marginT,
        }
    end
    return mapBounds
end

---@class RushSlide
local RushSlide = {}

---@param unit Entity 冲锋单位
---@param distance number 滑行距离
---@param duration number 持续时间（秒）
---@param damage number 碰撞伤害（每个目标仅生效一次，0=无伤害）
---@param hitRadius number 碰撞检测半径（默认 120）
---@param effectPath string|nil 移动特效路径
---@param attachPoint string|nil 特效绑定点
function RushSlide.execute(unit, distance, duration, damage, hitRadius, effectPath, attachPoint)
    if not unit or not unit.handle then return end

    local handle = unit.handle
    local face = jass.GetUnitFacing(handle)
    local from = Types.point(jass.GetUnitX(handle), jass.GetUnitY(handle))
    local dx = math.cos(face * math.pi / 180) * distance
    local dy = math.sin(face * math.pi / 180) * distance
    local to = Types.point(from[1] + dx, from[2] + dy)

    -- 碰撞去重表
    local hitObjs = {}

    -- 移动特效（可选）
    local moveEff = nil
    if effectPath then
        moveEff = EffectObj {
            target = unit,
            model = effectPath,
            attachPoint = attachPoint or "origin",
        }
    end

    -- 预计算总距离
    local totalDist = from * to

    -- TweenComp 实现位移 + 碰撞检测
    unit:add(TweenComp(from, to, duration, ENUM.TweenStyle.Once, Easing.outQuad, function(entity, value)
        -- 清理函数（提前退出时调用）
        local function earlyCleanup()
            entity:remove('TweenComp')
            if moveEff then
                moveEff:destroy()
                moveEff = nil
            end
        end

        -- 1. 计算当前位置
        local currentDist = totalDist * value
        local p = from:getLineDest(to, currentDist, true)

        -- 2. 地图边界检测（yd_MapMinX 等是 war3map.j 中的全局变量）
        local bounds = getMapBounds()
        if p[1] < bounds.minX or p[1] > bounds.maxX or p[2] < bounds.minY or p[2] > bounds.maxY then
            earlyCleanup()
            return
        end

        if p:is_block() then
            earlyCleanup()
            return
        end

        -- 4. 更新位置
        entity:setPoint(p)

        -- 5. 碰撞伤害（仅 damage > 0 时）
        if damage <= 0 then return end

        -- 存活检查
        if not entity.handle or jass.GetWidgetLife(entity.handle) <= 0.405 then return end

        -- 6. 范围检测（CreateGroup + GroupEnumUnitsInRange + FirstOfGroup 循环）
        local px, py = p[1], p[2]
        local radius = hitRadius or 120
        local group = jass.CreateGroup()
        jass.GroupEnumUnitsInRange(group, px, py, radius, nil)

        local target = jass.FirstOfGroup(group)
        while target ~= nil do
            if target ~= handle
                and jass.GetWidgetLife(target) > 0.405
                and not jass.IsUnitType(target, UNIT_TYPE_STRUCTURE)
                and not jass.IsUnitType(target, UNIT_TYPE_MAGIC_IMMUNE)
                and not hitObjs[jass.GetHandleId(target)]
            then
                hitObjs[jass.GetHandleId(target)] = true

                local targetEntity = Game.curState().engine:getEntityWithHandle(target)
                if targetEntity then
                    -- 冲锋为固定数值伤害，不走技能加成（忠实原版 YDWETimerPatternRushSlide 的 UnitDamageTarget）
                    -- 项目生命值由 Attribute 管理，需同步扣减
                    if targetEntity.attribute then
                        local life = targetEntity.attribute:get('生命')
                        if life <= damage then
                            -- 击杀：派发死亡事件（与 DamageObj:kill 一致）
                            Game.curState().eventManager:fireEvent(AnyUnitAboutToDie(targetEntity, unit))
                        else
                            -- 造成仇恨（触发原生伤害事件）
                            jass.UnitDamageTarget(handle, target, damage, false, false,
                                ATTACK_TYPE_MAGIC, DAMAGE_TYPE_UNIVERSAL, WEAPON_TYPE_WHOKNOWS)
                            -- 扣减项目生命值
                            targetEntity.attribute:add('生命', -damage)
                        end
                    end
                end
            end

            jass.GroupRemoveUnit(group, target)
            target = jass.FirstOfGroup(group)
        end
        jass.DestroyGroup(group)

    end, function()
        -- 滑行结束，清理特效（TweenComp 已由 TweenSystem 移除）
        if moveEff then
            moveEff:destroy()
            moveEff = nil
        end
    end))
end

return RushSlide
