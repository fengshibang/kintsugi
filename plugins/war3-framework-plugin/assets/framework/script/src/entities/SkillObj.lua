
local japi = require 'jass.japi'
local jass = require 'jass.common'
local code = require 'jass.code'
local slk = require 'jass.slk'
SkillComp = Component.create('SkillComp')
SkillObj = class("SkillObj", Entity)

local target_table = {
	["地面"]	= 2 ^ 1,
    ["空中"]	= 2 ^ 2,
    ["建筑"]	= 2 ^ 3,
    ["守卫"]	= 2 ^ 4,
    ["物品"]	= 2 ^ 5,
    ["树木"]	= 2 ^ 6,
    ["墙"]		= 2 ^ 7,
    ["残骸"]	= 2 ^ 8,
    ["装饰物"]	= 2 ^ 9,
   	["桥"]		= 2 ^ 10,
    ["未知"]	= 2 ^ 11,
    ["自己"]	= 2 ^ 12,
    ["玩家单位"]	= 2 ^ 13,
    ["联盟"]	= 2 ^ 14,
    ["中立"]	= 2 ^ 15,
    ["敌人"]	= 2 ^ 16,
    ["未知"]	= 2 ^ 17,
    ["未知"]	= 2 ^ 18,
    ["未知"]	= 2 ^ 19,
    ["可攻击的"]	= 2 ^ 20,
    ["无敌"]	= 2 ^ 21,
    ["英雄"]	= 2 ^ 22,
    ["非-英雄"]	= 2 ^ 23,
    ["存活"]	= 2 ^ 24,
    ["死亡"]	= 2 ^ 25,
    ["有机生物"]	= 2 ^ 26,
    ["机械类"]	= 2 ^ 27,
    ["非-自爆工兵"]	= 2 ^ 28,
    ["自爆工兵"]	= 2 ^ 29,
    ["非-古树"]	= 2 ^ 30,
    ["古树"]	= 2 ^ 31,
}


local function convertTargets(data)
	local result = 0

	for name in data:gmatch '%S+' do
		local flag = target_table[name]
		if not flag then
			ecs.debugError('错误的目标允许类型: ' .. name)
		end
		result = result + flag
	end
	return result
end

--初始化
function SkillObj:initialize(handle,ownerHandle,name)
    Entity.initialize(self,nil,name or GetAbilityName(self.id))
    self.handle = handle
    self.id = japi.EXGetAbilityId(handle)
    self.name = name or GetAbilityName(self.id)
    self.owner = Game.curState().engine:getEntityWithHandle(ownerHandle)
    self.removed = false
    if slk.ability[self.id].Buttonpos then        
        local x,y = table.unpack(lume.split(slk.ability[self.id].Buttonpos,','))
        self.slot = (tonumber(x) or 0) + (tonumber(y) or 0) * 4  + 1
    else
        self.slot = 1
    end
   -- 允许技能(War3)
    self.isEnableAbility = true
    self.art = ''
    self.area = nil
    self.range = nil
    self.level = GetUnitAbilityLevel(ownerHandle,self.id)
    self.cost = 0
    self.cool = 0
    self.tip = ''
    self.title= ''
    self.hide_count = 0
    self.targetType = ENUM.TargetType.None
    self._ignore_moving_on_castring = true
    self:add(SkillComp())
end


--设置技能等级
function SkillObj:setLevel(lvl,real)
    self.level = lvl
    if real then
        SetUnitAbilityLevel(self.owner.handle,self.id,lvl)
    end
end

--获取技能等级
function SkillObj:getLevel(real)
    if real then
        return GetUnitAbilityLevel(self.owner.handle,self.id)
    else
        return self.level
    end
end


-- 设置技能图标
function SkillObj:setArt(art)
    if not self.owner or not jass.GetPlayerAlliance(self.owner.player.handle,PlayerObj.static.self.handle, 6) then
        return
    end
    if not self:isVisible() then
        return
    end
    japi.EXSetAbilityString(self.id, self.level, 0xCC, art)
end


--设置标题
function SkillObj:setTitle(title)
    if not self.owner then
        self.title = title
        return
    end
    japi.EXSetAbilityString(self.id, self.level, 0xD7, title)
end

--设置tip
function SkillObj:setTip(tip)
    if not self.owner then
        self.tip = tip
        return
    end
    japi.EXSetAbilityString(self.id, self.level, 0xDA, tip)
end


-- 图标可见
function SkillObj:isVisible()
    return not self.removed and self.id and not self:isHide() and self.isEnableAbility 
end
    
--是否隐藏
function SkillObj:isHide()
    return self.hide_count > 0
end

-- 隐藏技能
function SkillObj:hide()
    if not self.handle then
        ecs.debugError('技能'..self.name..'还未添加到单位')
        return
    end
    self.hide_count = self.hide_count  + 1
    if self.hide_count == 1 then
        japi.EXSetAbilityDataReal(self.handle, 1, 0x6E,
            (self.area and 0x02 or 0x00) + ( 0x00))
    end
end

-- 显示技能
function SkillObj:show()
    if not self.handle then
        ecs.debugError('技能'..self.name..'还未添加到单位')
        return
    end
    self.hide_count = self.hide_count  - 1
    if self.hide_count== 0 then
        japi.EXSetAbilityDataReal(self.handle, 1, 0x6E,
            (self.area and 0x02 or 0x00) + (0x01 ))
    end
end

-- 刷新施法距离
--	[使用指定施法距离]
function SkillObj:setRange(range)
    if not self.handle then
        ecs.debugError('技能'..self.name..'还未添加到单位')
        return
    end
    if  self.passive then
        return
    end
    japi.EXSetAbilityDataReal(self.handle, 1, 0x6B, range or self.range)
end

-- 刷新影响范围
--	[使用指定范围]
function SkillObj:setArea(area)
    if not self.handle  then
        ecs.debugError('技能'..self.name..'还未添加到单位')
        return
    end
    if  self.passive then
        return
    end
    japi.EXSetAbilityDataReal(self.handle, 1, 0x6A, area or self.area)
end

-- 刷新技能耗蓝
--	[使用指定耗蓝]
function SkillObj:setCost(cost)
    -- 不再使用魔兽的扣蓝
    if not self:is_enable() or self.level == 0 then
        return
    end
    cost = cost or self.cost
    -- print(self.name, cost)
    japi.EXSetAbilityDataInteger(self:get_handle(), 1, 0x68, self:get_cost(cost))
end

-- 刷新目标允许
--	[使用指定目标类型]
--	[使用指定目标允许]
--	[使用指定目标选取范围]
function SkillObj:setTarget(target_type, target_data, area)
    if not self.handle then
        ecs.debugError('技能'..self.name..'还未添加到单位')
        return
    end

    local target_type = target_type or self.targetType
    japi.EXSetAbilityDataReal(self.handle, 1, 0x6D, target_type)
    japi.EXSetAbilityDataInteger(self.handle, 1, 0x64, convertTargets(target_data or self.target_data))
    japi.EXSetAbilityDataReal(self.handle, 1, 0x6E,
        ((area or self.area) and 0x02 or 0x00) + ( 0x01 ))

    -- 改一下技能等级以刷新目标允许
    if self:isVisible() then
        self.owner:setAbilityLevel(self.ability_id, 2)
        self.owner:setAbilityLevel(self.ability_id, 1)
    end
end

--获取指令
function SkillObj:getOrder()
    local ability_id = self.id
    if not ability_id then
        return nil
    end
    local ability_data = slk.ability[ability_id]
    if not ability_data then
        return nil
    end

    local order = ability_data['Order']
    if order ~= 'channel' then
        if order == '' then
            return nil
        end
        return order
    end
    local order = ability_data['DataF1']
    if order == '' then
        return nil
    end
    return order
end

function SkillObj:setMaxCool(max_cool)
    if not self.owner then
        self.cool = max_cool
        return
    end
    japi.EXSetAbilityDataReal(self.owner.handle,IdHelp.Str2Id(self.id),self.level,0x69,max_cool)
    -- japi.EXSetAbilityDataReal(self.handle, self.level, 0x69, max_cool)
end
function SkillObj:setCurCool(cool)
    if not self.owner then
        return
    end
    japi.EXSetAbilityState(self.handle, 0x01, cool)
end

function SkillObj:checkDep(id,player)
    id = id or self.id
    local data = slk.ability[id]
    player = player or self.owner.player
    if  tonumber(data.checkDep) ~= 1 or not data.Requires or data.Requires == "" then
        return true
    else
        local r = {}
        if not string.find(data.Requires,",") then
            r[1] = data.Requires
        else
            r = lume.split(data.Requires,",")  
        end 
        for i = 1, #r, 1 do
            if player:getTechCount(r[i] )< (tonumber(data.Requiresamount) or 1) then
                return false
            end 
        end
        return true
    end
end

function SkillObj:fresh()
    if not self.owner then
        return
    end
    IncUnitAbilityLevel(self.owner.handle,IdHelp.Str2Id(self.id))
    DecUnitAbilityLevel(self.owner.handle,IdHelp.Str2Id(self.id))
end

--正在引导
function SkillObj:isCasting()
    return self._is_casting
end

function SkillObj:castingHard()
    return self._ignore_moving_on_castring
end

--升级
function SkillObj:onLevelup()end

--添加
function SkillObj:onAdd()end

--添加
function SkillObj:onRemove()end
--施法指令
function SkillObj:onCastOrder(target)end
--施法开始
function SkillObj:onCastStart(target)
    self._cast_start_time = ac.clock()
    self._is_casting = true
end
--施法打断
function SkillObj:onCastBreak()
    self._is_casting = false
end
-- --施法引导
-- function SkillObj:onCastChannel()end
--施法出手
function SkillObj:onCastShot()
    self._is_casting = false
end

function SkillObj:onUpdate(dt)
    
end

function SkillObj:destroy(removeHandle)
    if removeHandle then
        UnitRemoveAbility(self.owner.handle,IdHelp.Str2Id(self.id))
    end
    Game.curState().engine:removeEntity(self)
end

function SkillObj:onAttack(target)
    
end
function SkillObj:onAttacked(target)
    
end

function SkillObj:onDamage(target,data)
    
end


function SkillObj:onKill(target)
    
end

function SkillObj:onRightClicked()
    
end
-- --施法停止
-- function SkillObj:onCastFinish()end
-- --施法完成
-- function SkillObj:onCastStop()end


return SkillObj