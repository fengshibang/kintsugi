-- types/Attribute.lua — 单位属性框架(三类属性:direct/flat/percent/readonly)
-- 提炼自 rouge_lua types/Attribute.lua,剥 MoeHero 专属 Defs(攻击/护甲/生命/马甲技能 A258 等)
-- 设计:
--   1. direct   当前值属性(如 生命/魔法),读写原生
--   2. flat     数值加成(如 攻击/护甲),add 累加 flat 表,sync 同步到原生
--   3. percent  百分比加成(如 攻速/移速),add 累加 percent 表,sync 同步到原生
--   4. readonly 只读原生(如 白字攻击)
--
-- 用户通过 Attribute.register(name, def) 注册自己的属性定义
-- 对外接口:add(name, value) / set(name, value) / get(name) / syncToNative(name)

local Attribute = class("Attribute")
Types = Types or {}
Types.Attribute = Attribute

-- 属性定义表(用户通过 register 注册)
local Defs = {}

-- 注册属性定义
-- @param name 属性名(如 '攻击'/'护甲')
-- @param def 定义表 { kind='flat'|'direct'|'percent'|'readonly', get, set, sync, resync, key }
function Attribute.register(name, def)
    Defs[name] = def
end

-- 获取属性定义(供外部查询)
function Attribute.getDef(name)
    return Defs[name]
end

function Attribute:initialize(owner)
    self.owner = owner
    self.flat = {}       -- 数值加成账本: { [key] = 累加值 }
    self.percent = {}    -- 百分比加成账本: { [key] = 累加值 }
end

-- 加成 / 扣减(对称:负值即撤销)
function Attribute:add(name, value)
    local def = Defs[name]
    if not def then
        ecs.debugError("错误的属性名:" .. tostring(name))
        return
    end
    if def.kind == 'direct' then
        def.set(self, def.get(self) + value)
    elseif def.kind == 'flat' then
        local k = def.key or name
        self.flat[k] = (self.flat[k] or 0) + value
        if def.sync then def.sync(self, self.flat[k]) end
    elseif def.kind == 'percent' then
        local k = def.key or name
        self.percent[k] = (self.percent[k] or 0) + value
        if def.sync then def.sync(self, self.percent[k]) end
        if def.resync then self:syncToNative(def.resync) end
    end
end

-- 直接设值(direct 类设当前值;加成类设累加绝对值)
function Attribute:set(name, value)
    local def = Defs[name]
    if not def then
        ecs.debugError("错误的属性名:" .. tostring(name))
        return
    end
    if def.set then
        def.set(self, value)
    elseif def.kind == 'flat' then
        local k = def.key or name
        self.flat[k] = value
        if def.sync then def.sync(self, value) end
    elseif def.kind == 'percent' then
        local k = def.key or name
        self.percent[k] = value
        if def.sync then def.sync(self, value) end
    end
end

-- 读取
function Attribute:get(name)
    local def = Defs[name]
    if not def then
        ecs.debugError("错误的属性名:" .. tostring(name))
        return 0
    end
    return def.get(self) or 0
end

-- 重新同步某属性到原生(供 percent 属性的 resync 调用)
function Attribute:syncToNative(name)
    local def = Defs[name]
    if not def or not def.sync then return end
    if def.kind == 'flat' then
        def.sync(self, self.flat[def.key or name] or 0)
    elseif def.kind == 'percent' then
        def.sync(self, self.percent[def.key or name] or 0)
    end
end

return Attribute
