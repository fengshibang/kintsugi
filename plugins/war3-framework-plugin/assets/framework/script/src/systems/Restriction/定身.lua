local RestrictionStopMoveSystem = class('RestrictionStopMoveSystem',System)
local jass = require 'jass.common'

function RestrictionStopMoveSystem:initialize()
    System.initialize(self)
end

function RestrictionStopMoveSystem:update(dt)

end

function RestrictionStopMoveSystem:onAddEntity(entity,group)
    System.onAddEntity(entity,group)
    jass.SetUnitMoveSpeed(entity.handle, 0)
    
end

function RestrictionStopMoveSystem:onRemoveEntity(entity,group)
    System.onRemoveEntity(entity,group)
    -- 恢复移速（原读 UnitModelComp 移速，但其依赖已废弃的 initAttr 实为 0；改用原生默认移速）
    jass.SetUnitMoveSpeed(entity.handle, jass.GetUnitDefaultMoveSpeed(entity.handle))
end


function RestrictionStopMoveSystem:requires()
    return {'RestrictionStopMoveComp','UnitModelComp'}
end

return RestrictionStopMoveSystem