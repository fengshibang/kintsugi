--=====================================================================
-- AuraComp / AuraObj: 光环实体（由技能/物品管理生命周期）
--
-- 设计：光环是独立实体（非挂在英雄身上的组件），贴合现有 BuffObj 范式。
--   - 技能学习/物品使用 → engine:addEntity(AuraObj{...} + AuraComp)
--   - 技能结束/施放者死亡 → engine:removeEntity(auraObj)
--   - AuraSystem 周期检测范围内单位，投放/刷新短时 buff（复用 UnitObj:addBuff
--     的"按时间覆盖/addStack 续期"机制，buff 到期 onRemove 自动撤销属性）
--
-- AuraComp 字段（光环配置，由投放端设置）:
--   range           光环半径
--   buffName        投放的 buff 类名（须在 buffTable 注册）
--   buffValue       buff 数值（初始值，若 abilityId 已设置则动态计算）
--   duration        buff 持续时间（秒，建议 = 检测周期 1.5s × 1.5~2，防断档）
--   attribute       影响的属性名（单属性光环用，传给 buff）
--   isPercent       是否百分比加成（单属性光环用）
--   allyOnly        是否只影响友军（默认 true）
--   abilityId       光环源技能 ID（可选，用于动态读取等级计算 buffValue）
--   levelMultiplier 每级加成系数（可选，buffValue = level * levelMultiplier）
--   enemyOnly       是否只影响敌人（默认 false）
--   modifiers       D8 多属性数组（可选，每元素 {attribute, value, isPercent, levelMultiplier?}）
--
-- AuraObj 实体字段（位置）:
--   followTarget  跟随单位(UnitObj)，nil 则用 position
--   position      固定位置（Types.point），followTarget 为 nil 时用
--=====================================================================
local auraCompFields = {'range', 'buffName', 'buffValue', 'duration', 'attribute', 'isPercent', 'allyOnly', 'abilityId', 'levelMultiplier', 'enemyOnly', 'modifiers'}
local auraCompDefaults = {duration = 2.5, isPercent = false, allyOnly = true, enemyOnly = false}

AuraComp = Component.create('AuraComp', auraCompFields, auraCompDefaults)

-- D8: 覆盖 initialize 同时支持位置参数（现有29光环零改动）和表参数（新双属性光环）
-- 位置式: AuraComp(900, '光环护甲加成', level*5, 2.5, '护甲', false, true, ...)
-- 表参数式: AuraComp{range=900, buffName='光环迟缓', modifiers={{...}}, enemyOnly=true}
AuraComp.initialize = function(self, ...)
    local first = ...
    if type(first) == 'table' then
        -- 表参数路径
        for _, field in ipairs(auraCompFields) do
            self[field] = first[field]
            if self[field] == nil then
                self[field] = auraCompDefaults[field]
            end
        end
    else
        -- 位置参数路径（向后兼容）
        local args = {...}
        for index, field in ipairs(auraCompFields) do
            self[field] = args[index]
            if self[field] == nil then
                self[field] = auraCompDefaults[field]
            end
        end
    end
end

AuraObj = class('AuraObj', Entity)

function AuraObj:initialize(data)
    Entity.initialize(self, nil, data.name or 'Aura')
    self.followTarget = data.followTarget   -- 跟随单位(UnitObj)，nil 则用 position
    self.position = data.position           -- 固定位置(Types.point)
end

return AuraObj
