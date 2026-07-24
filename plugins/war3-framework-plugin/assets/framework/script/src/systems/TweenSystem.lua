local TweenSystem = class("TweenSystem", System)

function TweenSystem:initialize()
    System.initialize(self)
end

function TweenSystem:update(dt)
    for k, entity in pairs(self.targets) do
        local comp = entity:get("TweenComp")
        comp.elapsed = comp.elapsed + dt
        local value = comp.easing(comp.elapsed,0,1, comp.duration)
        if (comp.onUpdate) then
            comp.onUpdate(entity, value)
        end
        if (comp.style == ENUM.TweenStyle.Once and comp.elapsed >= comp.duration) then
            if (comp.onFinished) then
                comp.onFinished(entity)
            end
            entity:remove("TweenComp")
        end
    end
end

function TweenSystem:onAddEntity(entity,group)
    System.onAddEntity(entity,group)
end

function TweenSystem:onRemoveEntity(entity,group)
    System.onRemoveEntity(entity,group)
end


function TweenSystem:requires()
    return {"TweenComp"}
end

return TweenSystem