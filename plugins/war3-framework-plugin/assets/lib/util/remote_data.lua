local player = require 'ac.player'
local plat = require 'util.11api'
local log = require 'base.log'
local pcrypt = require 'util.pcrypt'
local http = require 'util.http'
local base64 = require 'util.base64'

local string = string
local math = math

local rdata = {}
-- 每5秒生成一个全局通讯Key
ac.loop(5000, function()
    rdata.lastKey = rdata.Key or math.random(10000)
    rdata.Key = math.random(10000)
end)

local archive_keys = {
    -- 设置
    ['A0'] = 1,
    -- 等级1-1位,签到2-3位，通关4-7位,累计成就分 8-9位, 剩余成就分 10-11位
    ['A1'] = 1,
    -- 神秘彩蛋
    ['A2'] = 1,
    -- 名将录
    ['A3'] = 1,
    -- 成就项
    ['A4'] = 1,
    -- 成就商店 1-3位
    ['A5'] = 1,
    -- 通关次数 1-2 N1 3-4 N2 5-6 N3 7-8 N4 9-10 N5 11-12 N6 13-14N7 15-16N8
    ['A6'] = 1

}
local socre_keys = {
    ['S1'] = 1,
    ['S2'] = 1

}
local item_keys = {
    ['I1'] = 1234568
}
---key,value
function player.__index:SaveArchiveData(key, value)
    if not self.remote_data or not self.remote_data.archives or self.remote_data.archives[key] == nil then
        log.error('不能在存档读完前进行写入操作')
        return
    end
    self.remote_data.archives[key] = value
    local id = key:gsub("%D+", "")
    local str = (base64.encode('type=archive&id='..id..'&playername=' .. self:getBaseName() .. '&key='..key..'&value='..value))
    http.post(str)
    return plat.DzAPI_Map_SaveServerValue(self.handle, key, value)
end
function player.__index:GetArchiveData(key)
    self:initArchive()
    self.remote_data.archives[key] = self.remote_data.archives[key] or plat.DzAPI_Map_GetServerValue(self.handle, key)
    return self.remote_data.archives[key]
end
function player.__index:ReadArchiveData(key, index, n)
    self:GetArchiveData(key)
    if not self.remote_data.archives[key] then
        return
    end
    local tmp = pcrypt.decode(self.remote_data.archives[key], self:getBaseName())
    if not n or type(n) ~= 'number' then
        return string.byte(tmp:sub(index, index))
    else
        return get_bool(tmp:sub(index, index), n) and 1 or 0
    end
end
function player.__index:SaveScoreData(key, value)
    if not self.remote_data or not self.remote_data.socres or self.remote_data.socres[key] == nil then
        log.error('不能在存档读完前进行写入操作')
    end
    self.remote_data.socres[key] = value
    return plat.YDWERPGSetKey(self.handle, key, value)
end
function player.__index:GetScoreData(key)
    self:initSocres()
    self.remote_data.socres[key] = self.remote_data.socres[key] or plat.YDWERPGGetKey(self.handle, key)
    return self.remote_data.socres[key]
end
function player.__index:initArchive()
    if not self.remote_data then
        self.remote_data = {}
    end
    if not self.remote_data.archives then
        self.remote_data.archives = {}
    end
end
function player.__index:initSocres()
    if not self.remote_data then
        self.remote_data = {}
    end
    if not self.remote_data.socres then
        self.remote_data.socres = {}
    end
end
function player.__index:DzAPI_Map_HasMallItem(key)
    return plat.DzAPI_Map_HasMallItem(self.handle, key)
end
function player.__index:DzAPI_Map_GetMallItemCount(key)
    return plat.DzAPI_Map_GetMallItemCount(self.handle, key)
end
function player.__index:DzAPI_Map_ConsumeMallItem(key)
    return plat.DzAPI_Map_ConsumeMallItem(self.handle, key)
end

function get_bool(str, n)
    if n > 8 then
        return
    end
    local num = string.byte(str)
    return (1 << (8 - n)) & num ~= 0
end
function set_bool(str, n, b)
    local num = string.byte(str)
    if b and b ~= 0 then
        return string.char(1 << (8 - n) | num)
    else
        return string.char(~(1 << (8 - n)) & num)
    end
end
local function main()
    for i = 1, 4 do
        if player[i]:is_player() then
            for k, v in pairs(archive_keys) do
                if v == 2 then
                    plat.InitRPGData(k)
                end
                player[i]:GetArchiveData(k)
            end
            for k, v in pairs(socre_keys) do
                player[i]:GetScoreData(k)
            end
            for k, v in pairs(item_keys) do
                plat.InitRPGItem(k, v)
            end
            -- 存档更改
            player[i]:event '存档-存档更改'(function(trg, key, index, n, value, code, upload)
                if code ~= rdata.Key and code ~= rdata.lastKey then
                    log.error('状态码错误，拒绝存档')
                    return
                end
                if not player[i].remote_data or not player[i].remote_data.archives or
                    player[i].remote_data.archives[key] == nil then
                    log.error('不能在存档读完前进行写入操作')
                    return
                end
                local tmp = pcrypt.decode(player[i].remote_data.archives[key], player[i]:getBaseName())
                local str = ''
                local _value = value
                if not n or type(n) ~= 'number' then
                    if value > 255 then
                        log.error('存档值超出255')
                        return
                    end
                else
                    if value and value ~= 0 then
                        _value = 1 << (8 - n) | string.byte(tmp:sub(index, index))
                    else
                        _value = ~(1 << (8 - n)) & string.byte(tmp:sub(index, index))
                    end
                end
                if string.len(tmp) < 24 then
                    str = string.rep(string.char(0), index - 1) .. string.char(_value) ..
                              string.rep(string.char(0), 24 - index)
                else
                    str = tmp:sub(1, index - 1) .. string.char(_value) .. tmp:sub(index - 24)
                end
                str = pcrypt.encode(str, player[i]:getBaseName())
                if upload then
                    player[i]:SaveArchiveData(key, str)
                else
                    player[i].remote_data.archives[key] = value
                end
            end)

        end
    end

    -- 读取当前难度通关次数
    ac.game:event '游戏-难度选择完成'(function(trg, dif)
        for i = 1, 4 do
            local count = player[i]:ReadArchiveData('A6', dif * 2 - 1) * 256 + player[i]:ReadArchiveData('A6', dif * 2)
            player[i].pass_cur_dif_count = count
        end
    end)

end

return rdata
