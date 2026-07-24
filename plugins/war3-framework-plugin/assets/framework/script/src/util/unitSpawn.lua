-- 单位生成工具：在矩形区域中心创建单位（朝向指定单位）
-- 替代各 system 中复制的 createUnitAtRect 私有副本（对齐 unitAlive/fourcc/textTag 收敛模式）
local jass = require 'jass.common'

local function createUnitAtRect(unitId, player, rect, facingUnit)
    local rectCenter = jass.GetRectCenter(rect)
    local facingLoc = jass.GetUnitLoc(facingUnit)
    local unit = jass.CreateUnitAtLoc(player, unitId, rectCenter, jass.GetUnitFacing(facingUnit))
    jass.RemoveLocation(rectCenter)
    jass.RemoveLocation(facingLoc)
    return unit
end

return createUnitAtRect
