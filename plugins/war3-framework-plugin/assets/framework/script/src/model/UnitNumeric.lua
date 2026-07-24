-- model/UnitNumeric.lua — 单位数值(多模块累加)
-- 提炼自 rouge_lua model/UnitNumeric.lua
-- 设计:每个属性(UnitNumeric)按 UnitModuleType 分组存储(Base/Job/Level/Equip/Decorator/Skill/Rate/Other)
-- get() 无参时:sum(flat) * (1 + Rate/100) + Other

UnitNumeric = class('UnitNumeric')

---@param t string 属性类型(如 '攻击'/'护甲',由用户在 Attribute Defs 注册)
---@param map UnitNumericMap 属性集合
function UnitNumeric:initialize(t, map)
    self.onUpdate = nil
    self.type = t
    self.value = nil

    -- private
    self.map = map
    -- 分组不同模块数值
    self.values = {}

    local umt = ENUM.UnitModuleType
    for k, v in pairs(umt) do
        local key = tonumber(v)
        if key then
            self.values[key] = 0
        end
    end
end

-- 读取属性值
-- @param umt UnitModuleType(可选) 指定模块;无参返回总值
function UnitNumeric:get(umt)
    if umt then
        return self:getValue(umt)
    else
        local res = 0
        for k, v in pairs(self.values) do
            if k ~= tonumber(ENUM.UnitModuleType.Rate) and k ~= tonumber(ENUM.UnitModuleType.Other) then
                res = res + v
            end
        end
        res = res * (self:get(ENUM.UnitModuleType.Rate) / 100 + 1)
        res = res + self:get(ENUM.UnitModuleType.Other)
        return res
    end
end

function UnitNumeric:set(umt, value)
    return self:setValue(umt, value)
end

function UnitNumeric:getValue(module)
    return self.values[tonumber(module)]
end

function UnitNumeric:setValue(module, value)
    self.values[tonumber(module)] = value
    self:update()
end

function UnitNumeric:update()
    local result = 0
    for k, v in pairs(self.values) do
        result = result + v
    end
    self.value = result
    if self.onUpdate then
        self:onUpdate()
    end
end

function UnitNumeric:reset()
    self.values = {}
    self:update()
end
