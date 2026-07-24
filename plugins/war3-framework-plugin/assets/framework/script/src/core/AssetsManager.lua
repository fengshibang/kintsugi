-- core/AssetsManager.lua — 资源管理器(工厂)
-- 提炼自 rouge_lua core/AssetsManager.lua,剥 MoeHero 专属(createSkill/Buff/Bullet/Item/Quest/TextTag)
-- 设计:提供 createPlayer/createUnit/createUnitAtPos 桩,用户按需扩展

local dbg = require 'jass.debug'
local jass = require 'jass.common'

AssetsManager = class("AssetsManager")

function AssetsManager:initialize()
end

-- 创建玩家实体
-- @param id 玩家 ID(1-12)
function AssetsManager:createPlayer(id)
    local handle = Player(id - 1)
    local entity = PlayerObj(handle)
    Game.curState().engine:addEntity(entity)
    return entity
end

-- 创建单位实体
-- @param handle 单位 handle
-- @param player 玩家实体
function AssetsManager:createUnit(handle, player)
    local id = GetUnitTypeId(handle)
    -- 幂等:同 handle 已注册则返回已有 entity,避免重复创建
    local engine = Game.curState().engine
    if engine and engine.entityLists then
        local existing = engine.entityLists[handle]
        if existing then
            return existing
        end
    end
    local entity
    -- 用户可在全局 unitTable 注册自定义单位类
    local unitClass = unitTable and unitTable[id]
    dbg.handle_ref(handle)
    if unitClass then
        entity = unitClass(handle, player)
    else
        entity = UnitObj(handle, player)
    end
    -- 注册伤害触发器(AnyUnitDamaged 事件源)
    local trig = CreateTrigger()
    TriggerRegisterUnitEvent(trig, handle, jass.EVENT_UNIT_DAMAGED)
    local condition = jass.Condition(function()
        Game.curState().eventManager:fireEvent(AnyUnitDamaged(GetEventDamageSource(), GetTriggerUnit(), jass.GetEventDamage()))
    end)
    TriggerAddCondition(trig, condition)
    dbg.handle_ref(trig)
    entity.damagedTrigger = trig
    Game.curState().engine:addEntity(entity)
    entity:add(UnitModelComp())
    return entity
end

-- 在指定位置创建单位
-- @param rawId 单位类型 ID
-- @param player 玩家实体
-- @param x, y 坐标
-- @param facing 朝向(可选)
function AssetsManager:createUnitAtPos(rawId, player, x, y, facing)
    local handle = jass.CreateUnit(player.handle, rawId, x, y, facing or 0)
    if not handle then
        ecs.debugError('创建单位失败: ' .. rawId .. ' at ' .. x .. ',' .. y)
        return nil
    end
    return self:createUnit(handle, player)
end

-- 初始化单例
local function init()
    AssetsManager.singleton = AssetsManager()
end

init()
