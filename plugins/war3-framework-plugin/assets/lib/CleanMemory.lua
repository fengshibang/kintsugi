local jass = require 'jass.common'
local dbg = require 'jass.debug'
local collectgarbage = collectgarbage
local folderOfThisFile = (...):match("(.-)[^%/%.]+$")
if folderOfThisFile == nil then
    folderOfThisFile = ""
end
local log = log


local DebugInfoMap = {}

local type_list = {
    { '+dlb', "button" },
    { '+dlg', "dialog" },
    { '+w3d', "destructable" },
    { '+EIP', "effect" },
    { '+EIm', "effect" },
    { '+rev', "event" },
    { 'alvt', "event" },
    { 'bevt', "event" },
    { 'devt', "event" },
    { 'gevt', "event" },
    { 'gfvt', "event" },
    { 'pcvt', "event" },
    { 'pevt', "event" },
    { 'psvt', "event" },
    { 'tmet', "event" },
    { 'tmvt', "event" },
    { 'uevt', "event" },
    { '+flt', "filter" },
    { '+fgm', "fogmodifier" },
    { '+frc', "force" },
    { '+grp', "group" },
    { 'ghth', "hashtable" },
    { 'item', "item" },
    { '+loc', "location" },
    { '+mdb', "multiboard" },
    { '+ply', "player" },
    { '+rct', "rect" },
    { '+agr', "region" },
    { '+snd', "sound" },
    { '+tmr', "timer" },
    { '+tid', "timerdialog" },
    { '+trg', "trigger" },
    { '+tac', "triggeraction" },
    { 'tcnd', "triggercondition" },
    { '+w3u', "unit" },
    { '+mbi', "multiboarditem" },
}

local type_map = {}
for i, v in ipairs(type_list) do
    type_map[v[1]] = v[2]
end

function display_jass_object()
    local count = dbg.handlemax()
    --统计句柄数量
    local types = {}

    local all_count = 0

    local unit_pos_map = {}
    local effect_pos_map = {}

    for i = 1, count do
        local handle = 0x100000 + i
        local info = dbg.handledef(handle)
        if info and info.type then
            local str = type_map[info.type] or ''
            local num = types[str] or 0
            num = num + 1
            all_count = all_count + 1
            types[str] = num


            --统计单位 跟特效的 出生信息
            local handle_info = DebugInfoMap[handle]
            if handle_info then
                if str == 'unit' then
                    local count = unit_pos_map[handle_info] or 0

                    unit_pos_map[handle_info] = count + 1

                elseif str == 'effect' then
                    local count = effect_pos_map[handle_info] or 0

                    effect_pos_map[handle_info] = count + 1
                end
            end
        end
    end



    print('--------------start------------')
    for k, v in pairs(types) do
        print('类型', k, '数量', v)
    end
    print('统计数量', all_count, '底层获取数量', dbg.handlecount())

    print('--------------end------------')
end


local function aaa()
    collectgarbage("collect")
    local lua_memory = collectgarbage 'count'

    log.info(('定期清理内存[%.3fk]'):format(lua_memory))

    display_jass_object()
end
print('启动内存清理')
ac.loop(30*1000,aaa)