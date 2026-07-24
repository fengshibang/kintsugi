local jass =require'jass.common'
IdHelp = {}
--转换256进制整数
local ids1 = {}
local ids2 = {}

local function _id(a)
    local r = ('>I4'):pack(a)
    ids1[a] = r
    ids2[r] = a
    return r
end

function IdHelp.Id2Str(a)
    return ids1[a] or _id(a)
end

local function __id2(a)
    local r = ('>I4'):unpack(a)
    ids2[a] = r
    ids1[r] = a
    return r
end

function IdHelp.Str2Id(a)
    return ids2[a] or __id2(a)
end

IdHelp.id2Order = setmetatable({}, {__index = function(self, k)
    local order = jass.OrderId2String(k)
    if order then
        self[k] = order
    else
        self[k] = ''
    end
    return order
end})
for k, v in pairs(order2id) do
    IdHelp.id2Order[v] = k
end


return IdHelp