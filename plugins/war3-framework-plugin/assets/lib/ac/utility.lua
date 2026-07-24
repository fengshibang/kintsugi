local jass    = require 'jass.common'
local japi    = require 'jass.japi'
local ai = require 'jass.ai'
local console = require 'jass.console'
local runtime = require 'jass.runtime'

local setmetatable = setmetatable
local tostring     = tostring
local debug        = debug
local rawset       = rawset
local rawget       = rawget
local error        = error

local function warning(msg)
    console.write("---------------------------------------")
    console.write("             LUA WARNING!!             ")
    console.write("---------------------------------------")
    console.write(tostring(msg) .. "\n")
    console.write(debug.traceback())
    console.write("---------------------------------------")
end
print = console.write
local mt = {}
function mt:__index(i)
    if i < 0 or i > 8191 then
        warning('数组索引越界:'..i)
    end
    return rawget(self, '_default')
end

function mt:__newindex(i, v)
    if i < 0 then
        error('数组索引越界:'..i)
    elseif i > 8191 then
        warning('数组索引越界:'..i)
    end
    rawset(self, i, v)
end

function _native_(name)
    return _G[name] or japi[name] or jass[name] or ai[name]
end

function _array_(default)
    return setmetatable({ _default = default }, mt)
end

function _loop_()
    local i = 0
    return function()
        if i > 1000000 then
            error('循环次数太多')
        end
        i = i + 1
        return true
    end
end

function  table.deepCopy(source, target)
    local mark = {}
    local function copy(a, b)
        if type(a) ~= 'table' then
            return a
        end
        if mark[a] then
            return mark[a]
        end
        if not b then
            b = {}
        end
        mark[a] = b
        for k, v in pairs(a) do
            b[copy(k)] = copy(v)
        end
        return b
    end
    return copy(source, target)
end

register_japi(
[[
native  InitGameCache           takes string campaignFile returns gamecache
native  SaveGameCache           takes gamecache whichCache returns boolean

native  EXNetGetTime            takes nothing returns string
native  EXNetSaveRemoteData     takes integer player_id, string Key ,string value returns boolean
native  EXNetLoadRemoteData     takes integer player_id, string Key returns boolean
native  EXGetPlayerRealName     takes player p returns string

native  StoreInteger			takes gamecache cache, string missionKey, string key, integer value returns nothing
native  StoreReal				takes gamecache cache, string missionKey, string key, real value returns nothing
native  StoreBoolean			takes gamecache cache, string missionKey, string key, boolean value returns nothing
native  StoreUnit				takes gamecache cache, string missionKey, string key, unit whichUnit returns boolean
native  StoreString				takes gamecache cache, string missionKey, string key, string value returns boolean

native  SyncStoredInteger       takes gamecache cache, string missionKey, string key returns nothing
native  SyncStoredReal          takes gamecache cache, string missionKey, string key returns nothing
native  SyncStoredBoolean       takes gamecache cache, string missionKey, string key returns nothing
native  SyncStoredUnit          takes gamecache cache, string missionKey, string key returns nothing
native  SyncStoredString        takes gamecache cache, string missionKey, string key returns nothing

native  HaveStoredInteger		takes gamecache cache, string missionKey, string key returns boolean
native  HaveStoredReal			takes gamecache cache, string missionKey, string key returns boolean
native  HaveStoredBoolean		takes gamecache cache, string missionKey, string key returns boolean
native  HaveStoredUnit			takes gamecache cache, string missionKey, string key returns boolean
native  HaveStoredString		takes gamecache cache, string missionKey, string key returns boolean

native  FlushGameCache			takes gamecache cache returns nothing
native  FlushStoredMission		takes gamecache cache, string missionKey returns nothing
native  FlushStoredInteger		takes gamecache cache, string missionKey, string key returns nothing
native  FlushStoredReal			takes gamecache cache, string missionKey, string key returns nothing
native  FlushStoredBoolean		takes gamecache cache, string missionKey, string key returns nothing
native  FlushStoredUnit			takes gamecache cache, string missionKey, string key returns nothing
native  FlushStoredString		takes gamecache cache, string missionKey, string key returns nothing

native  GetStoredInteger		takes gamecache cache, string missionKey, string key returns integer
native  GetStoredReal			takes gamecache cache, string missionKey, string key returns real
native  GetStoredBoolean		takes gamecache cache, string missionKey, string key returns boolean
native  GetStoredString			takes gamecache cache, string missionKey, string key returns string
native  RestoreUnit				takes gamecache cache, string missionKey, string key, player forWhichPlayer, real x, real y, real facing returns unit

native  EXNetConsume            takes player whichPlayer,integer gold returns boolean
native  EXNetCommonConsume      takes player whichPlayer,integer gold returns boolean
native EXNetUseItem  takes player player_id,string itemid,integer amount returns boolean
]]
)

function is_player(player)
    return jass.GetPlayerController(player) == jass.MAP_CONTROL_USER and jass.GetPlayerSlotState(player) ==
               jass.PLAYER_SLOT_STATE_PLAYING
end