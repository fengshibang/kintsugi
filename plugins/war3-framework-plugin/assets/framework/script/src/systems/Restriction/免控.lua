local RestrictionAvoidDeathSystem = class('RestrictionControlFreeSystem',System)
local jass = require 'jass.common'

function RestrictionAvoidDeathSystem:initialize()
    System.initialize(self)
end

function RestrictionAvoidDeathSystem:update(dt)

end

function RestrictionAvoidDeathSystem:onAddEntity(entity,group)
    System.onAddEntity(entity,group)
    if entity:has('RestrictionStopMoveComp') then
        entity:remove('RestrictionStopMoveComp')
    end
    if entity:has('RestrictionStunComp') then
        entity:remove('RestrictionStunComp')
    end
end

function RestrictionAvoidDeathSystem:onRemoveEntity(entity,group)
    System.onRemoveEntity(entity,group)
end


function RestrictionAvoidDeathSystem:requires()
    return {'RestrictionControlFreeComp','UnitModelComp'}
end

return RestrictionAvoidDeathSystem