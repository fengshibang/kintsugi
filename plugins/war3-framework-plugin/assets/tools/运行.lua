local fs = require 'bee.filesystem'
local registry = require 'bee.registry'
local ydwe = require 'tools.ydwe'
local subprocess = require 'bee.subprocess'
if not ydwe then
    return
end

local function get_debugger()
    local path = fs.path(os.getenv('USERPROFILE')) / '.vscode' / 'extensions'
    for extpath in path:list_directory() do
        if fs.is_directory(extpath) and extpath:filename():string():sub(1, 20) == 'actboy168.lua-debug-' then
            local dbgpath = extpath / 'windows' / 'x86' / 'debugger.dll'
            if fs.exists(dbgpath) then
                return dbgpath
            end
        end
    end
end

local root = fs.path(arg[1])
local map_name = arg[2]
if not map_name then
    for p in root:list_directory() do
        if not fs.is_directory(p) and p:extension():string():lower() == '.w3x' then
            map_name = p:filename():string()
            break
        end
    end
end
if not map_name then
    print('未找到 .w3x 地图文件，可通过第二个参数指定')
    return
end
local map_path = root / map_name
if not fs.exists(map_path) then
    print('地图不存在', map_path)
    return
end
if get_debugger() then
    --command = command .. ' -debugger 4278'
end
subprocess.spawn {
    ydwe / 'ydwe.exe',
    '-war3',
    '-loadfile', map_path,
}
