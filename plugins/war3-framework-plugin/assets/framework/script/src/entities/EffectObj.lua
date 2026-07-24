local japi = require 'jass.japi'
local code = require 'jass.code'
EffectObj = class("EffectObj", Entity)
PointEffectComp = Component.create('PointEffectComp',{'point'})
TargetEffectComp = Component.create('TargetEffectComp',{"target",'attachPoint'},{attachPoint = AttachPoint.Origin})



function PointEffectComp:__tostring()
    return '点特效组件'
end

function TargetEffectComp:__tostring()
    return '目标特效组件'
end

function EffectObj:initialize(data)
    Entity.initialize(self,nil,'目标特效')
    --模型
    self.model = data.model
    self.size = data.size or 1
    self.angle = data.angle or 0

    --目标
    if data.point then
        self:add(PointEffectComp(data.point))
        if data.point[3] >  0 then
            self:setPoint(data.point)
        end
    elseif data.target  then
        self:add(TargetEffectComp(data.target,data.attachPoint or AttachPoint.Origin))
    else
        ecs.debugError('请设置特效目标或者特效位置')    
    end
    Game.curState().engine:addEntity(self)
    self:setSize(self.size)
end

--移除特效
function EffectObj:destroy(time)
    if self.handle then
        if time then
            ac.wait(time * 1000,function()
                Game.curState().engine:removeEntity(self)
            end)  
        else
            Game.curState().engine:removeEntity(self)
        end
    end
    return self
end

--显示特效
function EffectObj:show()
    if self.handle and self:get('PointEffectComp') then
        japi.EXSetEffectVisible(self.handle, true)
    end
    return self
end

--隐藏特效
function EffectObj:hide()
    if self.handle and self:get('PointEffectComp') then
        japi.EXSetEffectVisible(self.handle, false)
    end
    return self
end

-- 设置特效位置
function EffectObj:setPoint(point)
    if self.handle and self:get('PointEffectComp') then
        if point[3]~= 0 then
            japi.EXSetEffectZ(self.handle,point[3])
        end
        japi.EXSetEffectXY(self.handle,point:get())
        self:get('PointEffectComp').point = point
    end
    return self
end

function EffectObj:getPoint()
    if not  self.handle then
        return Types.point(0,0)
    end
    local peComp = self:get('PointEffectComp')
    if peComp then
        return peComp.point
    end
    local teComp = self:get('TargetEffectComp')
    if teComp then
        return teComp.target:getPoint()
    end
end

-- 设置缩放
function EffectObj:setSize(size) 
    if not self:get('PointEffectComp') then
        return
    end
    japi.EXSetEffectSize(self.handle,size)
    return self
end

-- 设置播放速度
function EffectObj:setSpeed(speed) 
    if not self:get('PointEffectComp') then
        return
    end
    japi.EXSetEffectSpeed(self.handle,speed) 
    return self
end

-- 设置动画
function EffectObj:setAnimation(index) 
    if not self.handle then
        return
    end
    japi.EXSetEffectAnimation(self.handle,index)
end

-- 设置颜色
function EffectObj:setColor(color) 
    if not self.handle then
        return
    end
    japi.EXSetEffectAnimation(self.handle,color)
end

function EffectObj:setRotateX(angle) 
    if not self:get('PointEffectComp') then
        return
    end
    japi.EXEffectMatRotateX(self.handle,angle)
end
function EffectObj:setRotateY(angle) 
    if not self:get('PointEffectComp') then
        return
    end
    japi.EXEffectMatRotateY(self.handle,angle)
end
function EffectObj:setRotateZ(angle) 
    if not self:get('PointEffectComp') then
        return
    end
    japi.EXEffectMatRotateZ(self.handle,angle)
end

function EffectObj:setAngle(angle)
    if not self:get('PointEffectComp') then
        return
    end
    local deltaAngle = self.angle - angle
    self.angle = angle
    self:setRotateZ(deltaAngle)
end

function EffectObj:setTween(data)
    self.tweens = self.tweens or {}
    local entity = Entity()
    entity:add(TweenComp(data.from,data.to,data.duration,data.style,data.easing,data.onUpdate,data.onFinished))
    Game.curState().engine:addEntity(entity)
    entity.eff = self
    table.insert(self.tweens,entity)
end