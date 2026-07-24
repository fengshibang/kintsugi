--[[
    unitHasItem - 检查单位是否持有指定类型的物品

    功能: 等价于 JASS 的 YDWEUnitHasItemOfTypeBJNull 函数
          遍历单位背包(6格),检查是否存在指定 ID 的物品

    用法: local hasItem = unitHasItem(unit, itemId)
]]

local jass = require 'jass.common'

local UnitItemInSlot = jass.UnitItemInSlot
local GetItemTypeId = jass.GetItemTypeId

local BJ_MAX_INVENTORY = 6

local function unitHasItem(whichUnit, itemId)
    if not whichUnit or itemId == 0 then
        return false
    end

    for index = 0, BJ_MAX_INVENTORY - 1 do
        local item = UnitItemInSlot(whichUnit, index)
        if GetItemTypeId(item) == itemId then
            return true
        end
    end

    return false
end

return unitHasItem
