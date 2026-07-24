local fs = require 'bee.filesystem'

local function for_directory(path, f)
    for p in path:list_directory() do
        if fs.is_directory(p) then
            for_directory(p, f)
        else
            f(p)
        end
    end
end

local function compilation(path)
    local succeed, failed = 0, 0
    local res = ''
    for_directory(path, function(filename)
        if filename:extension():string():lower() ~= '.lua' then
            return
        end
        local r, e = loadfile(filename:string(), 't')
        if not r then
            failed = failed + 1
            res = res .. e .. '\n'
        else
            succeed = succeed + 1
        end
    end)
    return res, succeed, failed
end

local root = fs.path(arg[1])
local res, succeed, failed = compilation(root)
print(res)
print(string.format('成功 %d 个, 失败 %d 个', succeed, failed))
