local RestrictionHideSystem = class('RestrictionHideSystem',System)
local jass = require 'jass.common'

function RestrictionHideSystem:initialize()
    System.initialize(self)
end

function RestrictionHideSystem:update(dt)

end

function RestrictionHideSystem:onAddEntity(entity,group)
    System.onAddEntity(entity,group)
    jass.ShowUnit(entity.handle,false)
end

function RestrictionHideSystem:onRemoveEntity(entity,group)
    jass.ShowUnit(entity.handle,true)
    System.onRemoveEntity(entity,group)
end


function RestrictionHideSystem:requires()
    return {'RestrictionHideComp','UnitModelComp'}
end

return RestrictionHideSystem