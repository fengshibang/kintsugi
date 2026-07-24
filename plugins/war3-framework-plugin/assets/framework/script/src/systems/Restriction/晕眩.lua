local RestrictionStunSystem = class('RestrictionStunSystem',System)
local jass = require 'jass.common'

function RestrictionStunSystem:initialize()
    System.initialize(self)
end

function RestrictionStunSystem:update(dt)
    for index, entity in pairs(self.targets) do
        local comp = entity:get('RestrictionStunComp')
        for i = #comp.ticks, 1, -1 do
            if comp.ticks[i][1] <= ac.clock() then
                table.remove(comp.ticks,i)
            end
        end
        local maxShowEff = 0
        for i, v in ipairs(comp.ticks) do
            if v[2] and v[1]>maxShowEff then
                maxShowEff = v[1]
            end
        end
        if  maxShowEff > ac.clock()   then
            comp.eff = comp.eff or EffectObj{
                target = entity,
                model = 'Abilities\\Spells\\Human\\Thunderclap\\ThunderclapTarget.mdl',
                attachPoint = AttachPoint.Overhead,
            }
        else
            if comp.eff then
                comp.eff:destroy()
                comp.eff = nil
            end
        end
        if #comp.ticks == 0 then
            entity:remove('RestrictionStunComp')
        end
    end
end

function RestrictionStunSystem:onAddEntity(entity,group)
    System.onAddEntity(entity,group)
    if entity:has('RestrictionControlFreeComp') then
        entity:remove('RestrictionStunComp')
        return
    end
    local comp = entity:get('RestrictionStunComp')
    comp.ticks = comp.ticks or {}
    table.insert(comp.ticks, {ac.clock() + comp.duration * 1000,comp.showEff})
    jass.PauseUnit(entity.handle, true)
end

function RestrictionStunSystem:onRemoveEntity(entity,group)
    jass.PauseUnit(entity.handle, false)
    System.onRemoveEntity(entity,group)
end


function RestrictionStunSystem:requires()
    return {'RestrictionStunComp','UnitModelComp'}
end

return RestrictionStunSystem