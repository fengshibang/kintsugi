local RestrictionStealthSystem = class('RestrictionStealthSystem',System)
local jass = require 'jass.common'

function RestrictionStealthSystem:initialize()
    System.initialize(self)
end

function RestrictionStealthSystem:update(dt)

end

function RestrictionStealthSystem:onAddEntity(entity,group)
    System.onAddEntity(entity,group)
    entity:addAbility('A102',1)
end

function RestrictionStealthSystem:onRemoveEntity(entity,group)
    entity:removeAbility('A102')
    System.onRemoveEntity(entity,group)
end


function RestrictionStealthSystem:requires()
    return {'RestrictionStealthComp','UnitModelComp'}
end

return RestrictionStealthSystem