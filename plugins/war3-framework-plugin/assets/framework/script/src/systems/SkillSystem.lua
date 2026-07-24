--技能系统
local SkillSystem = class("SkillSystem", System)
local japi =require 'jass.japi'

function SkillSystem:update(dt)
    for _, skill in pairs(self.targets) do
        skill:onUpdate(dt)
    end
end

--添加技能
function SkillSystem:onAddEntity(...)
    System.onAddEntity(self, ...)
    local entity = ...  
    local owner = entity.owner
    if owner.skills == nil then
        owner.skills = {}
    end
    table.insert(owner.skills,entity)
    if entity:getOrder() then
        owner._order_skills[entity:getOrder()] = entity
    end
    entity:onAdd()
end

--移除技能
function SkillSystem:onRemoveEntity(...)
    local entity = ...
    entity:onRemove()
    local owner = entity.owner
    for i, skill in ipairs(owner.skills) do
        if skill == entity then
            table.remove(owner.skills,i)
            break
        end
    end
    if entity:getOrder() then
        owner._order_skills[entity:getOrder()] = nil
    end
    System.onRemoveEntity(self, ...)
end

function SkillSystem:AnyUnitLearnedSkill(hero,abilityId)
    for i, skill in ipairs(hero.skills) do
        if skill.id == abilityId then
            skill:onLevelUp()
            return
        end
    end
    AssetsManager.Singleton:createSkill(japi.EXGetUnitAbility(hero.handle,abilityId),hero.handle)
end

function SkillSystem:AnyUnitAttack(event)
    local attackUnit,defUnit = event.info[1],event.info[2]
    for k, entity in pairs(self.targets) do
        if entity.owner then
            if entity.owner == attackUnit then
                entity:onAttack(defUnit)
            end
            if entity.owner == defUnit then
                entity:onAttacked(attackUnit)
            end
        end
    end
end



function SkillSystem:requires()
    return { "SkillComp" }
end

return SkillSystem