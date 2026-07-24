--local code = require 'jass.code'
local lume = { _version = "2.3.0" }

local pairs, ipairs = pairs, ipairs
local type, assert, unpack = type, assert, unpack or table.unpack
local tostring, tonumber = tostring, tonumber
local math_floor = math.floor
local math_ceil = math.ceil
local math_atan2 = math.atan2 or math.atan
local math_sqrt = math.sqrt
local math_abs = math.abs

local noop = function()
end

local identity = function(x)
    return x
end

local patternescape = function(str)
    return str:gsub("[%(%)%.%%%+%-%*%?%[%]%^%$]", "%%%1")
end

local absindex = function(len, i)
    return i < 0 and (len + i + 1) or i
end

local iscallable = function(x)
    if type(x) == "function" then return true end
    local mt = getmetatable(x)
    return mt and mt.__call ~= nil
end

local getiter = function(x)
    if lume.isarray(x) then
        return ipairs
    elseif type(x) == "table" then
        return pairs
    end
    error("expected table", 3)
end

local iteratee = function(x)
    if x == nil then return identity end
    if iscallable(x) then return x end
    if type(x) == "table" then
        return function(z)
            for k, v in pairs(x) do
                if z[k] ~= v then return false end
            end
            return trueClamp
        end
    end
    return function(z) return z[x] end
end

function lume.clamp(x, min, max)
    return x < min and min or (x > max and max or x)
end

--四舍五入x到最接近的整数；如果设置increment，则四舍五入到最接近的增量。
--lume.round(2.3) -- Returns 2
--lume.round(123.4567, .1) -- Returns 123.5
function lume.round(x, increment)
    if increment then return lume.round(x / increment) * increment end
    return x >= 0 and math_floor(x + 0.5) or math_ceil(x - 0.5)
end

function lume.sign(x)
    return x < 0 and -1 or 1
end

function lume.max(a, b)
    return a > b and a or b
end

--线性插值
function lume.lerp(a, b, amount)
    return a + (b - a) * lume.clamp(amount, 0, 1)
end

--平滑插值
function lume.smooth(a, b, amount)
    local t = lume.clamp(amount, 0, 1)
    local m = t * t * (3 - 2 * t)
    return a + (b - a) * m
end

--角度平滑缓存插值
function lume.smoothDampAngle(current, target, currentVelocity, smoothTime, maxSpeed, deltaTime)
    local deltaAngle = (target - current) - math.floor((target - current) / 360) * 360
    if (deltaAngle > 180) then
        deltaAngle = deltaAngle - 360
    end

    target = current + deltaAngle
    smoothTime = lume.max(0.0001, smoothTime)
    local omega = 2 / smoothTime

    local x = omega * deltaTime
    local exp = 1 / (1 + x + 0.48 * x * x + 0.235 * x * x * x)
    local change = current - target
    local originalTo = target
    local maxChange = maxSpeed * smoothTime

    change = lume.clamp(change, -maxChange, maxChange)
    target = current - change

    local temp = (currentVelocity + omega * change) * deltaTime
    currentVelocity = (currentVelocity - omega * temp) * exp
    local output = target + (change + temp) * exp

    if ((originalTo - current > 0) == (output > originalTo)) then
        output = originalTo
        currentVelocity = (output - originalTo) / deltaTime
    end

    return output, currentVelocity
end

function lume.pingpong(x)
    return 1 - math_abs(1 - x % 2)
end

function lume.distance(x1, y1, x2, y2, squared)
    local dx = x1 - x2
    local dy = y1 - y2
    local s = dx * dx + dy * dy
    return squared and s or math_sqrt(s)
end

function lume.angle(x1, y1, x2, y2)
    return math_atan2(y2 - y1, x2 - x1)
end

function lume.vector3(angle, magnitude)
    return Vector3(math.cos(angle) * magnitude, math.sin(angle) * magnitude, 0)
end

function lume.random(a, b)
    if not a then a, b = 0, 1 end
    if not b then b = 0 end
    return a + math.random() * (b - a)
end

function lume.randomchoice(t)
    return t[math.random(#t)]
end

function lume.weightedchoice(t)
    local sum = 0
    for _, v in pairs(t) do
        assert(v >= 0, "weight value less than zero")
        sum = sum + v
    end
    assert(sum ~= 0, "all weights are zero")
    local rnd = lume.random(sum)
    for k, v in pairs(t) do
        if rnd < v then return k end
        rnd = rnd - v
    end
end

function lume.isarray(x)
    return type(x) == "table" and x[1] ~= nil
end

--将所有给定值t压入表的末尾并返回压入的值。无值将被忽略。
function lume.push(t, ...)
    local n = select("#", ...)
    for i = 1, n do
        t[#t + 1] = select(i, ...)
    end
    return ...
end

function lume.remove(t, x)
    local iter = getiter(t)
    for i, v in iter(t) do
        if v == x then
            if lume.isarray(t) then
                table.remove(t, i)
                break
            else
                t[i] = nil
                break
            end
        end
    end
    return x
end

function lume.clear(t)
    local iter = getiter(t)
    for k in iter(t) do
        t[k] = nil
    end
    return t
end

--将所有字段从源表复制到表中t并返回t。如果多个表中都存在键，则使用最右边的表的值。
function lume.extend(t, ...)
    for i = 1, select("#", ...) do
        local x = select(i, ...)
        if x then
            for k, v in pairs(x) do
                t[k] = v
            end
        end
    end
    return t
end

--对数组洗牌
function lume.shuffle(t)
    local rtn = {}
    for i = 1, #t do
        local r = math.random(i)
        if r ~= i then
            rtn[i] = rtn[r]
        end
        rtn[r] = t[i]
    end
    return rtn
end

--对数组排序
--lume.sort({ 1, 4, 3, 2, 5 }) -- Returns { 1, 2, 3, 4, 5 }
--lume.sort({ {z=2}, {z=3}, {z=1} }, "z") -- Returns { {z=1}, {z=2}, {z=3} }
--lume.sort({ 1, 3, 2 }, function(a, b) return a > b end) -- Returns { 3, 2, 1 }
function lume.sort(t, comp)
    local rtn = lume.clone(t)
    if comp then
        if type(comp) == "string" then
            table.sort(rtn, function(a, b) return a[comp] < b[comp] end)
        else
            table.sort(rtn, comp)
        end
    else
        table.sort(rtn)
    end
    return rtn
end

--迭代提供的迭代器，并返回一个填充有值的数组。
--lume.array(string.gmatch("Hello world", "%a+")) -- Returns {"Hello", "world"}
function lume.array(...)
    local t = {}
    for x in ... do t[#t + 1] = x end
    return t
end

--迭代表t
--lume.each({1, 2, 3}, print) -- Prints "1", "2", "3" on separate lines
--lume.each({a, b, c}, "move", 10, 20) -- Does x:move(10, 20) on each value
function lume.each(t, fn, ...)
    local iter = getiter(t)
    if type(fn) == "string" then
        for _, v in iter(t) do v[fn](v, ...) end
    else
        for _, v in iter(t) do fn(v, ...) end
    end
    return t
end

--将函数应用于fn表中的每个值，t并返回包含结果值的新表。
--lume.map({1, 2, 3}, function(x) return x * 2 end) -- Returns {2, 4, 6}
function lume.map(t, fn)
    fn = iteratee(fn)
    local iter = getiter(t)
    local rtn = {}
    for k, v in iter(t) do rtn[k] = fn(v) end
    return rtn
end


function lume.reduce(t, fn, first)
    local acc = first
    local started = first and true or false
    local iter = getiter(t)
    for _, v in iter(t) do
        if started then
            acc = fn(acc, v)
        else
            acc = v
            started = true
        end
    end
    assert(started, "reduce of an empty table with no first value")
    return acc
end

function lume.unique(t)
    local rtn = {}
    for k in pairs(lume.invert(t)) do
        rtn[#rtn + 1] = k
    end
    return rtn
end

function lume.filter(t, fn, retainkeys)
    fn = iteratee(fn)
    local iter = getiter(t)
    local rtn = {}
    if retainkeys then
        for k, v in iter(t) do
            if fn(v) then rtn[k] = v end
        end
    else
        for _, v in iter(t) do
            if fn(v) then rtn[#rtn + 1] = v end
        end
    end
    return rtn
end

function lume.reject(t, fn, retainkeys)
    fn = iteratee(fn)
    local iter = getiter(t)
    local rtn = {}
    if retainkeys then
        for k, v in iter(t) do
            if not fn(v) then rtn[k] = v end
        end
    else
        for _, v in iter(t) do
            if not fn(v) then rtn[#rtn + 1] = v end
        end
    end
    return rtn
end

--合并多个表，如果多个表中存在相同的Key，则使用最右边表的值。
--lume.merge({a=1, b=2, c=3}, {c=8, d=9}) -- Returns {a=1, b=2, c=8, d=9}
function lume.merge(...)
    local rtn = {}
    for i = 1, select("#", ...) do
        local t = select(i, ...)
        local iter = getiter(t)
        for k, v in iter(t) do
            rtn[k] = v
        end
    end
    return rtn
end

function lume.concat(...)
    local rtn = {}
    for i = 1, select("#", ...) do
        local t = select(i, ...)
        if t ~= nil then
            local iter = getiter(t)
            for _, v in iter(t) do
                rtn[#rtn + 1] = v
            end
        end
    end
    return rtn
end

function lume.find(t, value)
    local iter = getiter(t)
    for k, v in iter(t) do
        if v == value then return k end
    end
    return nil
end

function lume.match(t, fn)
    fn = iteratee(fn)
    local iter = getiter(t)
    for k, v in iter(t) do
        if fn(v) then return v, k end
    end
    return nil
end

function lume.count(t, fn)
    local count = 0
    local iter = getiter(t)
    if fn then
        fn = iteratee(fn)
        for _, v in iter(t) do
            if fn(v) then count = count + 1 end
        end
    else
        if lume.isarray(t) then
            return #t
        end
        for _ in iter(t) do count = count + 1 end
    end
    return count
end

function lume.slice(t, i, j)
    i = i and absindex(#t, i) or 1
    j = j and absindex(#t, j) or #t
    local rtn = {}
    for x = i < 1 and 1 or i, j > #t and #t or j do
        rtn[#rtn + 1] = t[x]
    end
    return rtn
end

function lume.first(t, n)
    if not n then return t[1] end
    return lume.slice(t, 1, n)
end

function lume.last(t, n)
    if not n then return t[#t] end
    return lume.slice(t, -n, -1)
end

function lume.invert(t)
    local rtn = {}
    for k, v in pairs(t) do rtn[v] = k end
    return rtn
end

function lume.pick(t, ...)
    local rtn = {}
    for i = 1, select("#", ...) do
        local k = select(i, ...)
        rtn[k] = t[k]
    end
    return rtn
end

function lume.keys(t)
    local rtn = {}
    local iter = getiter(t)
    for k in iter(t) do rtn[#rtn + 1] = k end
    return rtn
end

function lume.clone(t)
    local rtn = {}
    for k, v in pairs(t) do rtn[k] = v end
    return rtn
end

function lume.fn(fn, ...)
    assert(iscallable(fn), "expected a function as the first argument")
    local args = { ... }
    return function(...)
        local a = lume.concat(args, { ... })
        return fn(unpack(a))
    end
end

function lume.once(fn, ...)
    local f = lume.fn(fn, ...)
    local done = false
    return function(...)
        if done then return end
        done = true
        return f(...)
    end
end

local memoize_fnkey = {}
local memoize_nil = {}

function lume.memoize(fn)
    local cache = {}
    return function(...)
        local c = cache
        for i = 1, select("#", ...) do
            local a = select(i, ...) or memoize_nil
            c[a] = c[a] or {}
            c = c[a]
        end
        c[memoize_fnkey] = c[memoize_fnkey] or { fn(...) }
        return unpack(c[memoize_fnkey])
    end
end

function lume.combine(...)
    local n = select('#', ...)
    if n == 0 then return noop end
    if n == 1 then
        local fn = select(1, ...)
        if not fn then return noop end
        assert(iscallable(fn), "expected a function or nil")
        return fn
    end
    local funcs = {}
    for i = 1, n do
        local fn = select(i, ...)
        if fn ~= nil then
            assert(iscallable(fn), "expected a function or nil")
            funcs[#funcs + 1] = fn
        end
    end
    return function(...)
        for _, f in ipairs(funcs) do f(...) end
    end
end

function lume.call(fn, ...)
    if fn then
        return fn(...)
    end
end

function lume.time(fn, ...)
    local start = os.clock()
    local rtn = { fn(...) }
    return (os.clock() - start), unpack(rtn)
end

local lambda_cache = {}

function lume.lambda(str)
    if not lambda_cache[str] then
        local args, body = str:match([[^([%w,_ ]-)%->(.-)$]])
        assert(args and body, "bad string lambda")
        local s = "return function(" .. args .. ")\nreturn " .. body .. "\nend"
        lambda_cache[str] = lume.dostring(s)
    end
    return lambda_cache[str]
end

local serialize

local serialize_map = {
    ["boolean"] = tostring,
    ["nil"    ] = tostring,
    ["string"] = function(v) return string.format("%q", v) end,
    ["number"] = function(v)
        if    v ~= v    then return "0/0"      --  nan
        elseif v == 1 / 0 then return "1/0"      --  inf
        elseif v == -1 / 0 then return "-1/0" end  -- -inf
        return tostring(v)
    end,
    ["table"] = function(t, stk)
        stk = stk or {}
        if stk[t] then error("circular reference") end
        local rtn = {}
        stk[t] = true
        for k, v in pairs(t) do
            rtn[#rtn + 1] = "[" .. serialize(k, stk) .. "]=" .. serialize(v, stk)
        end
        stk[t] = nil
        return "{" .. table.concat(rtn, ",") .. "}"
    end
}

setmetatable(serialize_map, {
    __index = function(_, k) error("unsupported serialize type: " .. k) end
})

serialize = function(x, stk)
    return serialize_map[type(x)](x, stk)
end

function lume.serialize(x)
    return serialize(x)
end


function lume.deserialize(str)
    return lume.dostring("return " .. str)
end


function lume.split(str, sep)
    if not sep then
        return lume.array(str:gmatch("([%S]+)"))
    else
        assert(sep ~= "", "empty separator")
        local psep = patternescape(sep)
        return lume.array((str .. sep):gmatch("(.-)(" .. psep .. ")"))
    end
end


function lume.trim(str, chars)
    if not chars then return str:match("^[%s]*(.-)[%s]*$") end
    chars = patternescape(chars)
    return str:match("^[" .. chars .. "]*(.-)[" .. chars .. "]*$")
end


function lume.wordwrap(str, limit)
    limit = limit or 72
    local check
    if type(limit) == "number" then
        check = function(s) return #s >= limit end
    else
        check = limit
    end
    local rtn = {}
    local line = ""
    for word, spaces in str:gmatch("(%S+)(%s*)") do
        local s = line .. word
        if check(s) then
            table.insert(rtn, line .. "\n")
            line = word
        else
            line = s
        end
        for c in spaces:gmatch(".") do
            if c == "\n" then
                table.insert(rtn, line .. "\n")
                line = ""
            else
                line = line .. c
            end
        end
    end
    table.insert(rtn, line)
    return table.concat(rtn)
end


function lume.format(str, vars)
    if not vars then return str end
    local f = function(x)
        return tostring(vars[x] or vars[tonumber(x)] or "{" .. x .. "}")
    end
    return (str:gsub("{(.-)}", f))
end


function lume.trace(...)
    local info = debug.getinfo(2, "Sl")
    local t = { info.short_src .. ":" .. info.currentline .. ":" }
    for i = 1, select("#", ...) do
        local x = select(i, ...)
        if type(x) == "number" then
            x = string.format("%g", lume.round(x, 0.01))
        end
        t[#t + 1] = tostring(x)
    end
    print(table.concat(t, " "))
end


function lume.dostring(str)
    return assert((loadstring or load)(str))()
end


function lume.uuid()
    local fn = function(x)
        local r = math.random(16) - 1
        r = (x == "x") and (r + 1) or (r % 4) + 9
        return ("0123456789abcdef"):sub(r, r)
    end
    return (("xxxxxxxx-xxxx-4xxx"):gsub("[xy]", fn))
end

-- function lume.uuid()
--     local fn = function(x)
--         local r = math.random(16) - 1
--         r = (x == "x") and (r + 1) or (r % 4) + 9
--         return ("0123456789abcdef"):sub(r, r)
--     end
--     return (("xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx"):gsub("[xy]", fn))
-- end

function lume.hotswap(modname)
    local oldglobal = lume.clone(_G)
    local updated = {}
    local function update(old, new)
        if updated[old] then return end
        updated[old] = true
        local oldmt, newmt = getmetatable(old), getmetatable(new)
        if oldmt and newmt then update(oldmt, newmt) end
        for k, v in pairs(new) do
            if type(v) == "table" then update(old[k], v)
            else old[k] = v end
        end
    end
    local err = nil
    local function onerror(e)
        for k in pairs(_G) do _G[k] = oldglobal[k] end
        err = lume.trim(e)
    end
    local ok, oldmod = pcall(require, modname)
    oldmod = ok and oldmod or nil
    xpcall(function()
        package.loaded[modname] = nil
        local newmod = require(modname)
        if type(oldmod) == "table" then update(oldmod, newmod) end
        for k, v in pairs(oldglobal) do
            if v ~= _G[k] and type(v) == "table" then
                update(v, _G[k])
                _G[k] = v
            end
        end
    end, onerror)
    package.loaded[modname] = oldmod
    if err then return nil, err end
    return oldmod
end


local ripairs_iter = function(t, i)
    i = i - 1
    local v = t[i]
    if v ~= nil then
        return i, v
    end
end

function lume.ripairs(t)
    return ripairs_iter, t, (#t + 1)
end


function lume.color(str, mul)
    mul = mul or 1
    local r, g, b, a
    r, g, b = str:match("#(%x%x)(%x%x)(%x%x)")
    if r then
        r = tonumber(r, 16) / 255
        g = tonumber(g, 16) / 255
        b = tonumber(b, 16) / 255
        a = 1
    elseif str:match("rgba?%s*%([%d%s%.,]+%)") then
        local f = str:gmatch("[%d.]+")
        r = (f() or 0) / 255
        g = (f() or 0) / 255
        b = (f() or 0) / 255
        a = f() or 1
    else
        error(("bad color string '%s'"):format(str))
    end
    return r * mul, g * mul, b * mul, a * mul
end


local chain_mt = {}
chain_mt.__index = lume.map(lume.filter(lume, iscallable, true),
function(fn)
    return function(self, ...)
        self._value = fn(self._value, ...)
        return self
    end
end)
chain_mt.__index.result = function(x) return x._value end

function lume.chain(value)
    return setmetatable({ _value = value }, chain_mt)
end

setmetatable(lume, {
    __call = function(_, ...)
        return lume.chain(...)
    end
})


local mSeed = 66
local BIG_PRIME = 65537
local MAX_RATIO = 1 / BIG_PRIME

--不能在异步环境使用
function math.random(m, n)
    local seed = mSeed
    if not seed then return m end

    if seed == 0 then seed = 1 end
    seed = (seed * 67) % BIG_PRIME
    mSeed = seed

    local min = 0
    local max = 0
    local isFloor = false

    if m and n then
        min = m
        max = n
        isFloor = true
    elseif m then
        min = 1
        max = m
        isFloor = true
    end

    local result = min + seed * MAX_RATIO * (max - min + 1)
    if isFloor then result = math.floor(result) end
    return result
end

function string:up()
    local path = {}
    for i in string.gmatch(self, '.[^.]*') do
        table.insert(path, i)
    end
    table.remove(path, #path)
    table.remove(path, #path)
    return table.concat(path)
end

--修复随机数可能导致的异步

if (code) then
    function code.GetRandomInt(lowBound, highBound)
        return math.random(lowBound, highBound)
    end
end

return lume