local EquipSystem = class("EquipSystem", System)


---装备
function ItemObj:onEquip()
    if not self:get('EquipComp') then
        return
    end
    return true
end
function ItemObj:onTakeOff()
    if not self:get('EquipComp') then
        return
    end
    return true
end



function EquipSystem:initialize()
    System.initialize(self)
end

function EquipSystem:update(dt)
    for k, v in pairs(self.targets) do
        v:onUpdate()
    end
end

function EquipSystem:onEquip(entity)
    entity:onEquip()
end

function EquipSystem:onTakeOff(entity)
end


function EquipSystem:onAddEntity(entity,group)
    System.onAddEntity(entity,group)
end


function EquipSystem:onRemoveEntity(entity,group)
    System.onRemoveEntity(entity,group)
end

function EquipSystem:requires()
    return {"EquipComp"}
end



return EquipSystem