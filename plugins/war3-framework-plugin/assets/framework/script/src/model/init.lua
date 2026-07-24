-- model/init.lua — 加载 model 层模块
-- 顺序:enum(枚举) → UnitModelComp(标记) → UnitNumeric(数值) → UnitNumericMap(集合)

local folderOfThisFile = (...):match("(.-)[^%/%.]+$")..'model.'

require(folderOfThisFile..'enum')
require(folderOfThisFile..'UnitModelComp')
require(folderOfThisFile..'UnitNumeric')
require(folderOfThisFile..'UnitNumericMap')
