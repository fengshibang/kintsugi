local DamageSystem = class("DamageSystem", System)

function DamageSystem:initialize()
    System.initialize(self)
end

function DamageSystem:update(dt)

end

function DamageSystem:onAddEntity(entity,group)
    System.onAddEntity(entity,group)
    entity:onDamage()
    entity:remove('OnDamageComp')
    Game.curState().engine:removeEntity(entity)
end

function DamageSystem:onRemoveEntity(entity,group)
    System.onRemoveEntity(entity,group)
end


function DamageSystem:requires()
    return {'OnDamageComp'}
end

return DamageSystem