local BulletSystem = class("BulletSystem", System)

function BulletSystem:initialize()
    System.initialize(self)
end

function BulletSystem:update(dt)
    for _,entity in pairs(self.targets) do
        local comp =entity:get('BulletComp')
        local t = Selector():inRange(entity:getPoint(),comp.radius,comp.filter,function(obj)
            if not comp.objs[obj.eid] then
                comp.objs[obj.eid] = obj
                if comp.onHit then
                    comp.onHit(entity,obj)
                end
            end
        end)
    end
end

function BulletSystem:onAddEntity(entity,group)
    System.onAddEntity(entity,group)
end


function BulletSystem:onRemoveEntity(entity,group)
    System.onRemoveEntity(entity,group)
end

function BulletSystem:requires()
    return {"PointEffectComp","BulletComp",'TweenComp'}
end

return BulletSystem