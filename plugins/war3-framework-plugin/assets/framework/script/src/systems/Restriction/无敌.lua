local RestrictionInvulnerableSystem = class('RestrictionInvulnerableSystem',System)
local jass = require 'jass.common'

function RestrictionInvulnerableSystem:initialize()
    System.initialize(self)
end

function RestrictionInvulnerableSystem:update(dt)

end

function RestrictionInvulnerableSystem:onAddEntity(entity,group)
    System.onAddEntity(entity,group)
    entity:addAbility('Avul',1)
end

function RestrictionInvulnerableSystem:onRemoveEntity(entity,group)
    System.onRemoveEntity(entity,group)
    entity:removeAbility('Avul')
end


function RestrictionInvulnerableSystem:requires()
    return {'RestrictionInvulnerableComp','UnitModelComp'}
end

return RestrictionInvulnerableSystem