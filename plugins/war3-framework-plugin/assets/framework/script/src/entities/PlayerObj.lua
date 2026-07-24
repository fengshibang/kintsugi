-- entities/PlayerObj.lua — 玩家实体(桩)
-- 提炼自 rouge_lua entities/PlayerObj.lua,剥 MoeHero 专属(gold/lumber/remoteData/EnemyPlayerComp/PlayerComp)
-- 设计:极简玩家实体,只保留 handle/id/name + 基础方法

local japi = require 'jass.japi'
local jass = require 'jass.common'
local dbg = require 'jass.debug'

PlayerObj = class('PlayerObj', Entity)

function PlayerObj:initialize(handle)
    Entity.initialize(self, nil, japi.EXGetPlayerRealName(handle))
    self.name = japi.EXGetPlayerRealName(handle)
    self.handle = handle
    dbg.handle_ref(self.handle)
    self.id = GetPlayerId(handle) + 1

    if not PlayerObj.static.players then
        PlayerObj.static.players = {}
    end
    -- 忽视所有警戒点
    jass.RemoveAllGuardPositions(self.handle)
    PlayerObj.static.players[self:getId()] = self
    if GetLocalPlayer() == handle then
        PlayerObj.static.self = self
    end
end

function PlayerObj:__tostring()
    return '玩家' .. self:getId()
end

-- 通过 ID 获取玩家
function PlayerObj:getInstanceById(id)
    return PlayerObj.static.players[id]
end

-- 判断是否是本地玩家
function PlayerObj:isSelf()
    return self.handle == GetLocalPlayer()
end

-- 获取 id
function PlayerObj:getId()
    return self.id
end

-- 获取平台昵称(玩家名)
function PlayerObj:getName(real)
    return (real and japi.EXGetPlayerRealName(self.handle)) or self.name
end

-- 设置玩家名字
function PlayerObj:setName(name)
    jass.SetPlayerName(self.handle, name)
end

-- 是否是玩家
function PlayerObj:isPlayer()
    return jass.GetPlayerController(self.handle) == jass.MAP_CONTROL_USER and
           jass.GetPlayerSlotState(self.handle) == jass.PLAYER_SLOT_STATE_PLAYING
end

-- 是否是裁判
function PlayerObj:isObserver()
    return jass.IsPlayerObserver(self.handle)
end

-- 设置颜色
function PlayerObj:setColor(this, c)
    jass.SetPlayerColor(this.handle, c - 1)
end

-- 结盟
function PlayerObj:setAlliance(dest, al, flag)
    return jass.SetPlayerAlliance(self.handle, dest.handle, al, flag)
end

function PlayerObj:setAllianceSimple(dest, flag)
    jass.SetPlayerAlliance(self.handle, dest.handle, 0, flag) -- ALLIANCE_PASSIVE
    jass.SetPlayerAlliance(self.handle, dest.handle, 1, false) -- ALLIANCE_HELP_REQUEST
    jass.SetPlayerAlliance(self.handle, dest.handle, 2, false) -- ALLIANCE_HELP_RESPONSE
    jass.SetPlayerAlliance(self.handle, dest.handle, 3, flag) -- ALLIANCE_SHARED_XP
    jass.SetPlayerAlliance(self.handle, dest.handle, 4, flag) -- ALLIANCE_SHARED_SPELLS
    jass.SetPlayerAlliance(self.handle, dest.handle, 5, flag) -- ALLIANCE_SHARED_VISION
end

-- 获取/设置资源(金币/木材)
function PlayerObj:getGold()
    return jass.GetPlayerState(self.handle, jass.PLAYER_STATE_RESOURCE_GOLD)
end

function PlayerObj:setGold(amount)
    jass.SetPlayerState(self.handle, jass.PLAYER_STATE_RESOURCE_GOLD, amount)
end

function PlayerObj:addGold(amount)
    local cur = self:getGold()
    self:setGold(cur + amount)
end

function PlayerObj:getLumber()
    return jass.GetPlayerState(self.handle, jass.PLAYER_STATE_RESOURCE_LUMBER)
end

function PlayerObj:setLumber(amount)
    jass.SetPlayerState(self.handle, jass.PLAYER_STATE_RESOURCE_LUMBER, amount)
end

function PlayerObj:addLumber(amount)
    local cur = self:getLumber()
    self:setLumber(cur + amount)
end
