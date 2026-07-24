local EffectSystem = class("EffectSystem", System)
local debug = require 'jass.debug'

function EffectSystem:initialize()
    System.initialize(self)
end

function EffectSystem:update(dt)

end

function EffectSystem:onAddEntity(entity, group)
    System.onAddEntity(entity, group)
    if group == 'point' then
        local comp = entity:get('PointEffectComp')
        entity.handle = AddSpecialEffect(entity.model, comp.point:getPoint():get())
        debug.handle_ref(entity.handle)
    elseif group == 'target' then
        local target = entity:get('TargetEffectComp').target
        local attachPoint = entity:get('TargetEffectComp').attachPoint
        entity.handle = AddSpecialEffectTarget(entity.model, target.handle, attachPoint)
        debug.handle_ref(entity.handle)
    end
end

function EffectSystem:onRemoveEntity(entity, group)
    debug.handle_unref(entity.handle)
    DestroyEffect(entity.handle)
    entity.handle = nil
    System.onRemoveEntity(entity, group)
end

function EffectSystem:requires()
    return {
        point = {'PointEffectComp'},
        target = {'TargetEffectComp'},
    }
end

return EffectSystem
