--[[
    unitGetItemOfType - 获取单位背包中指定类型的物品

    功能: 等价于 JASS 的 YDWEGetItemOfTypeFromUnitBJNull 函数
          遍历单位背包(6格),返回第一个匹配的物品句柄,不存在则返回 nil

    用法: local item = unitGetItemOfType(unit, itemId)
]]

local jass = require 'jass.common'

local UnitItemInSlot = jass.UnitItemInSlot
local GetItemTypeId = jass.GetItemTypeId

local BJ_MAX_INVENTORY = 6

local function unitGetItemOfType(whichUnit, itemId)
    if not whichUnit then
        return nil
    end

    for index = 0, BJ_MAX_INVENTORY - 1 do
        local item = UnitItemInSlot(whichUnit, index)
        if GetItemTypeId(item) == itemId then
            return item
        end
    end

    return nil
end

return unitGetItemOfType
