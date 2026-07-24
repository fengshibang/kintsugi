-- script/src/init.lua — 脚手架核心加载器
-- ticket 04 产物:从 rouge_lua src/ 提炼+清洗的通用脚手架核心
-- 加载顺序:types(基础类型) → core(循环/事件/工厂/状态/选择器) → model(数值) → entities(玩家/单位桩)
-- 不加载 components/systems/states/界面/Buffs(MoeHero 专属)

local folderOfThisFile = (...):match("(.-)[^%/%.]+$")..'src.'

require(folderOfThisFile..'types')
require(folderOfThisFile..'core')
require(folderOfThisFile..'model')
require(folderOfThisFile..'entities')

-- 标记脚手架已加载(供外部检测)
_G.__framework_scaffold_loaded = true
