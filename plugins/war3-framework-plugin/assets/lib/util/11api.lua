local ac = {code = {}}
local japi = require ("jass.japi")
local jass = require ("jass.common")
local player = Player
local GetPlayerId = GetPlayerId
local GetPlayerController = GetPlayerController
local GetPlayerSlotState = GetPlayerSlotState
local MAP_CONTROL_USER = MAP_CONTROL_USER
local PLAYER_SLOT_STATE_PLAYING = PLAYER_SLOT_STATE_PLAYING
local hook = require ("jass.message")

register_japi[[

    native EXNetConsume takes player p,integer consume returns boolean

    native EXNetCommonConsume takes player p,integer consume returns boolean

    native EXGetPlayerRealName takes player p returns string

    native EXNetGetTime takes nothing returns string
    
    native EXNetStatRemoteData takes integer player_id, string key ,string value returns boolean

    native EXNetSaveRemoteData takes integer player_id, string Key ,string value returns boolean

    native EXNetLoadRemoteData takes integer player_id, string Key returns boolean
]]


local is_11Platform = (japi.EXNetGetTime() ~='') and true
local player_uid = {}
for i = 0,3 do
    if jass.Player(i) == GetLocalPlayer() then
            --player_uid[i+1] = japi.GetUserIdEx()
    end
end
if is_11Platform then
    --print('当前环境为11对战平台')
end

-- 获取玩家名字
function hook.GetPlayerName(handle)
    return japi.EXGetPlayerRealName(handle)
end

-- 时间戳
local start_time =is_11Platform and japi.EXNetGetTime() or os.date('%Y')..' '..os.date('%X')
local time_data = {
    ['年'] = '(%d%d%d%d)%-',
    ['月'] = '%-(%d%d)%-',
    ['日'] = '%d%d%d%d%-%d%d%-(%d%d)',
    ['时'] = '(%d%d):',
    ['分'] = ':(%d%d):',
    ['秒'] = '%d%d:%d%d:(%d%d)',
}

-- 获取开始时间戳
function ac.DzAPI_Map_GetGameStartTime()
    return os.time {
        year = start_time:match(time_data['年']),
        month = start_time:match(time_data['月']),
        day = start_time:match(time_data['日']),
        hour = start_time:match(time_data['时']),
        min = start_time:match(time_data['分']),
        sec = start_time:match(time_data['秒']),
    }
end

--RPG积分缓存
local score_gc = japi.InitGameCache("11.x")
--RPG存档缓存
local RPGDataGc = japi.InitGameCache("11.s")

local function get_player_uid(i)
    return player_uid[i]
end

local function get_key(handle)
    return ("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):sub(GetPlayerId(handle) + 1, GetPlayerId(handle) + 1)
end

local localPlayer
local frist_player

local function YDWEWriteToReplay(table, key, data)
    if not frist_player then
        localPlayer = GetLocalPlayer()
        for index = 0, 15 do
            local handle = player(index)
            if GetPlayerController(handle) == MAP_CONTROL_USER and GetPlayerSlotState(handle) == PLAYER_SLOT_STATE_PLAYING then
                frist_player = handle
            end
        end
    end
    japi.StoreInteger(score_gc, table, key, tonumber(data) or 0)
    if frist_player == localPlayer then --由这名玩家发起同步
        japi.SyncStoredInteger(score_gc, table, key)
    end
end

local record_data = {}

--- 获取积分对象
local function getRecord(handle)
    if not record_data[handle] then
        if GetPlayerController(handle) == MAP_CONTROL_USER and GetPlayerSlotState(handle) == PLAYER_SLOT_STATE_PLAYING then
            record_data[handle] = japi.InitGameCache("11billing@" .. get_key(handle))
        else
            record_data[handle] = japi.InitGameCache("")
        end
    end
    return record_data[handle]
end

local register = {}
local RPGITEM = {}

-- 基础
function ac.InitRPGData(key) register[key] = {key .. 'V1', key .. 'V2'} end
function ac.InitRPGItem(WY, YY) RPGITEM[WY] = YY end

-- 保存积分
function ac.YDWERPGSetKey(handle, key, value)
    if not is_11Platform then return  end
    YDWEWriteToReplay(get_key(handle) .. "=" , key , value)
end

-- 读取积分
function ac.YDWERPGGetKey(handle, key)
    if not is_11Platform then return 0 end
    return japi.GetStoredInteger(score_gc, get_key(handle), key)
end

-- 结算积分
function ac.YDWERPGGameEnd()
    if not is_11Platform then return end
    YDWEWriteToReplay("$" , "GameEnd" , 0)
end

-- 保存服务器存档
function ac.DzAPI_Map_SaveServerValue(handle, key, value)
    local boolean = false
    if not is_11Platform then return boolean end
    local pid = GetPlayerId(handle)
    if register[key] then
        local len = #value
        boolean = japi.EXNetSaveRemoteData(pid, register[key][1], value:sub(1, 32))
        if len > 32 then
            japi.EXNetSaveRemoteData(pid, register[key][2], value:sub(33, len))
        else
            japi.EXNetSaveRemoteData(pid, register[key][2], '')
        end
    else
        boolean = japi.EXNetSaveRemoteData(pid, key, value)
    end
    return boolean
end

ac.DzAPI_Map_SaveServerArchive = ac.DzAPI_Map_SaveServerValue

-- 读取服务器存档
function ac.DzAPI_Map_GetServerValue(handle, key)
    local value = ''
    
    if not is_11Platform then return value end
    local pid = GetPlayerId(handle)
    if register[key] then
        japi.EXNetLoadRemoteData(pid, register[key][1])
        value = japi.GetStoredString(RPGDataGc, japi.EXGetPlayerRealName(handle), register[key][1])
        if value and #value == 32 then
            japi.EXNetLoadRemoteData(pid, register[key][2])
            value = value .. japi.GetStoredString(RPGDataGc, japi.EXGetPlayerRealName(handle), register[key][2])
        end
    else
        japi.EXNetLoadRemoteData(pid, key)
        value = japi.GetStoredString(RPGDataGc, japi.EXGetPlayerRealName(handle), key)
    end
    return value or ''
end

-- 是否拥有商城道具
function ac.DzAPI_Map_HasMallItem(handle, key)
    if not is_11Platform then return false end
    if not RPGITEM[key] then
        print('DzAPI_Map_HasMallItem - 获取出错,没有注册Key', key)
        return false
    end
    return japi.HaveStoredInteger(getRecord(handle), "状态", RPGITEM[key])
end

-- 获取商城道具数量
function ac.DzAPI_Map_GetMallItemCount(handle, key)
    if not is_11Platform then return 0 end
    if not RPGITEM[key] then
        print('DzAPI_Map_GetMallItemCount - 获取出错,没有注册Key', key)
        return 0
    end
    return japi.GetStoredInteger(getRecord(handle), "道具", RPGITEM[key])
end

-- 扣除玩家一个次数类道具
function ac.DzAPI_Map_ConsumeMallItem(handle, key, value)
    if not is_11Platform then return  end
    if not RPGITEM[key] then
        print('DzAPI_Map_ConsumeMallItem - 获取出错,没有注册Key', key)
        return false
    end
    return japi.EXNetUseItem(handle, RPGITEM[key], value)
end

ac.DzAPI_Map_ServerArchive = ac.DzAPI_Map_GetServerValue

-- 获取全局存档
function ac.DzAPI_Map_Global_GetStoreString(key)
    return japi.GetStoredString(RPGDataGc, "config", key)
end



return ac
