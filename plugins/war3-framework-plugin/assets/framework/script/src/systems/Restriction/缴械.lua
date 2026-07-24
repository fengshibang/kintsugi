local RestrictionAbunSystem = class('RestrictionAbunSystem',System)
local jass = require 'jass.common'

function RestrictionAbunSystem:initialize()
    System.initialize(self)
end

function RestrictionAbunSystem:update(dt)
    for index, entity in pairs(self.targets) do
        local comp = entity:get('RestrictionAbunComp')
        if comp.duration and  comp.duration  > 0  then
            for i, v in ipairs(comp.ticks) do
                if v <= ac.clock() then
                    table.remove(comp.ticks,i)
                end
            end
            if #comp.ticks == 0 then
                entity:remove('RestrictionAbunComp')
            end
        end
    end
end

function RestrictionAbunSystem:onAddEntity(entity,group)
    System.onAddEntity(entity,group)
    if entity:has('RestrictionControlFreeComp') then
        entity:remove('RestrictionAbunComp')
        return
    end
    local comp = entity:get('RestrictionAbunComp')
    if comp.duration and  comp.duration  > 0  then
        comp.ticks = comp.ticks or {}
        comp.ticks[1] = ac.clock() + comp.duration * 1000
    end
    entity:addAbility('Abun')
end

function RestrictionAbunSystem:onRemoveEntity(entity,group)
    entity:removeAbility('Abun')
    System.onRemoveEntity(entity,group)
end


function RestrictionAbunSystem:requires()
    return {'RestrictionAbunComp','UnitModelComp'}
end

return RestrictionAbunSystem