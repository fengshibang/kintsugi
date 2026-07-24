local RestrictionAvoidDeathSystem = class('RestrictionAvoidDeathSystem',System)
local jass = require 'jass.common'

function RestrictionAvoidDeathSystem:initialize()
    System.initialize(self)
end

function RestrictionAvoidDeathSystem:update(dt)

end

function RestrictionAvoidDeathSystem:onAddEntity(entity,group)
    System.onAddEntity(entity,group)
end

function RestrictionAvoidDeathSystem:onRemoveEntity(entity,group)
    System.onRemoveEntity(entity,group)
end

function RestrictionAvoidDeathSystem:AnyUnitAboutToDie(event)
    local dyingUnit,killer = event.info[1],event.info[2]
    if not dyingUnit:has('RestrictionAvoidDeathComp') then
        dyingUnit:kill(killer)
        else
            -- 免死：保留 1 血（原 UnitModelComp Base/Other 模块逻辑统一为 Attribute direct）
            dyingUnit.attribute:set('生命', 1)
        end
end

function RestrictionAvoidDeathSystem:requires()
    return {'RestrictionAvoidDeathComp','UnitModelComp'}
end

return RestrictionAvoidDeathSystem