-- entities/UnitObj.lua — 单位实体(桩)
-- 提炼自 rouge_lua entities/UnitObj.lua,剥 MoeHero 专属(skills/buffs/items/upgrades/attribute/applyBuffModifiers 等)
-- 设计:极简单位实体,只保留 handle/id/name/player + 基础方法

local japi = require 'jass.japi'
local jass = require 'jass.common'
local dbg = require 'jass.debug'
local slk = require 'jass.slk'

UnitObj = class("UnitObj", Entity)

function UnitObj:initialize(handle, player)
    Entity.initialize(self, nil, GetUnitName(handle))
    self.name = GetUnitName(handle)
    self.handle = handle
    self.id = GetUnitTypeId(handle)
    self.player = player
    self._is_alive = true
end

function UnitObj:__tostring()
    return self.name .. '(' .. self.id .. ')'
end

-- 判断是否存活
function UnitObj:isAlive()
    return self._is_alive
end

function UnitObj:isDead()
    return not self._is_alive
end

-- 设置存活状态(供死亡事件调用)
function UnitObj:setAlive(alive)
    self._is_alive = alive
end

-- 获取坐标
function UnitObj:getPoint()
    local x, y = GetUnitX(self.handle), GetUnitY(self.handle)
    return Types.point(x, y, 0)
end

-- 设置坐标
function UnitObj:setPoint(p)
    local x, y = p:get()
    SetUnitPosition(self.handle, x, y)
end

-- 获取朝向
function UnitObj:getFacing()
    return GetUnitFacing(self.handle)
end

-- 设置朝向
function UnitObj:setFacing(facing)
    SetUnitFacing(self.handle, facing)
end

-- 获取队伍
function UnitObj:getTeam()
    return GetPlayerId(GetOwningPlayer(self.handle))
end

-- 发布指令(无目标)
function UnitObj:issueOrder(order)
    return jass.IssueImmediateOrder(self.handle, order)
end

-- 发布目标指令
function UnitObj:issueTargetOrder(order, target)
    if target.player then
        -- 目标是玩家(单位)
        return jass.IssueTargetOrder(self.handle, order, target.handle)
    else
        -- 目标是点
        local x, y
        if target:isInstanceOf(Types.point) then
            x, y = target:get()
        else
            x, y = target:getPoint():get()
        end
        return jass.IssuePointOrder(self.handle, order, x, y)
    end
end

-- 杀死单位
function UnitObj:kill()
    self._is_alive = false
    jass.KillUnit(self.handle)
end

-- 移除单位
function UnitObj:remove()
    jass.RemoveUnit(self.handle)
end
