
BuffComp = Component.create('BuffComp',{'interval','duration','frameCount','cover'},{frameCount = 0,interval = 0,duration = 0,cover = ENUM.BuffCoverType['按值覆盖']})

BuffObj = class('BuffObj',Entity)

function BuffObj:initialize(name,from,host)
    Entity.initialize(self,nil,name)
    self.from = from
    self.host =  host
    self.buffAbility = nil
    self.stack = 1
    self.maxStack = 1
    self.model = nil
end



function BuffObj:addStack()
    if (self.stack < self.maxStack) then
        self:untouch()
        self:touch()
    end
    local comp = self:get('BuffComp')
    if (comp) then
        comp.frameCount = 0
    end
end


function BuffObj:getRemainingFrameCount()
    local comp = self:get('BuffComp')
    if comp then
        return math.floor(comp.duration/Game.DeltaTime - comp.frameCount)
    else
        return 0
    end
end

function BuffObj:affect()end

function BuffObj:touch()end

function BuffObj:untouch()end


--添加时回调
function BuffObj:onAdd()end
--每帧回调
function BuffObj:onUpdate(dt)end
--移除时回调
function BuffObj:onRemove()end
--持有者攻击
function BuffObj:onAttack()end
--持有者受攻击
function BuffObj:onAttacked()end
--持有者击杀单位
function BuffObj:onKill()end
--持有者周围死亡
function BuffObj:onNearbyDeath(distance)end




return BuffObj