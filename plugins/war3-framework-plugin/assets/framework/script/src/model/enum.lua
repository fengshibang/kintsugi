-- model/enum.lua — 枚举定义
-- 提炼自 rouge_lua model/enum.lua,剥 MoeHero 专属 UnitAttributeType(攻击/生命/力量/元素等)
-- 保留通用枚举:UnitModuleType(属性模块分组)、TargetType、Quality、TweenStyle、BuffCoverType

local enum = {}
ENUM = {}
setmetatable(ENUM, {
    __index = enum,
    __newindex = function()
        ecs.debugError('枚举类型是只读的，无法修改')
    end
})

local function _enum(tbl, index)
    local enumtbl = {}
    local enumindex = index or 0
    for i, v in ipairs(tbl) do
        enumtbl[v] = enumindex + i
    end
    return enumtbl
end

-- 属性模块类型:用于 UnitNumeric 分组累加
-- Base/Job/Level/Equip/Decorator/Skill 是 flat 累加模块,Rate 是百分比,Other 是固定加成
enum.UnitModuleTypeSrc = {
    'Base',
    'Job',
    'Level',
    'Equip',
    'Decorator',
    'Skill',
    'Rate',
    'Other'
}
enum.UnitModuleType = _enum(enum.UnitModuleTypeSrc)

-- 目标类型
enum.TargetTypeSrc = {
    'None',
    'Unit',
    'Point',
    'UnitOrPoint',
}
enum.TargetType = _enum(enum.TargetTypeSrc, -1)

-- 品质
enum.QualitySrc = {
    '初级',
    '中级',
    '高级',
}
enum.Quality = _enum(enum.QualitySrc)

-- 补间动画样式
enum.TweenStyleSrc = {
    'Once',
}
enum.TweenStyle = _enum(enum.TweenStyleSrc)

-- Buff 覆盖类型
enum.BuffCoverTypeSrc = {
    "按值覆盖",
    "不覆盖",
    "按时间覆盖",
}
enum.BuffCoverType = _enum(enum.BuffCoverTypeSrc)
