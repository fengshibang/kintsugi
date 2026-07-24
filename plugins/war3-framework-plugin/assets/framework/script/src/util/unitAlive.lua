-- 单位存活判定工具
-- 统一 0.405 生命阈值 (对齐 War3 单位死亡判定), 替代各攻击触发器系统中复制的 _unitAlive 私有副本。
local jass = require 'jass.common'

local M = {}

---判断 ECS 单位实体是否存活 (handle 有效且生命值 > 0.405)
---@param entity table UnitObj Entity
---@return boolean
function M.isAlive(entity)
    return entity ~= nil and entity.handle ~= nil and jass.GetWidgetLife(entity.handle) > 0.405
end

return M
