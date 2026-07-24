local BuffSystem = class("BuffSystem", System)
local japi = require 'jass.japi'
local code = require 'jass.code'

function BuffSystem:initialize()
    System.initialize(self)
end

function BuffSystem:update(dt)
    for index, entity in pairs(self.targets) do
        repeat
            if (entity.host:isDead()) then
                entity.host:removeBuffByInstance(entity)
                break
            end
            local comp = entity:get('BuffComp')
            comp.frameCount = comp.frameCount + 1
            if comp.interval > 0 and comp.frameCount % (comp.interval / dt) == 0 then
                entity:affect()
            end
            if (comp.duration ~= 0) and (comp.frameCount >= comp.duration/dt) then
                entity.host:removeBuffByInstance(entity)
            end
        until true
    end
end

function BuffSystem:onAddEntity(entity, group)
    System.onAddEntity(entity, group)
    if entity.buffAbility then
        entity.host:addAbility(entity.buffAbility)
        EXSetAbilityDataReal(entity.host.handle, IdHelp.Str2Id(entity.buffAbility), 1, 0x6E, 0x00)
    end
    entity:onAdd()
    if entity.model then
        entity.eff = EffectObj {
            target = entity.host,
            model = entity.model,
            attachPoint = entity.attachPoint
        }
    end
end

function BuffSystem:onRemoveEntity(entity, group)
    if entity.buffAbility then
        entity.host:removeAbility(entity.buffAbility)
    end
    if entity.eff then
        entity.eff:destroy()
    end
    entity:onRemove()
    System.onRemoveEntity(entity, group)
end

function BuffSystem:AnyUnitAttack(event)
    local attackUnit, defUnit = event.info[1], event.info[2]
    for k, entity in pairs(self.targets) do
        if entity.host then
            if entity.host == attackUnit then
                entity:onAttack(defUnit)
            end
            if entity.host == defUnit then
                entity:onAttacked(attackUnit)
            end
        end
    end
end

function BuffSystem:requires()
    return {"BuffComp"}
end

return BuffSystem
