-- components/init.lua — 加载 components 层模块
-- 提炼自 rouge_lua components,只含通用 RPG 组件

local folderOfThisFile = (...):match("(.-)[^%/%.]+$")..'components.'

require(folderOfThisFile..'BulletComp')
require(folderOfThisFile..'EffectDamageComp')
require(folderOfThisFile..'EquipComp')
require(folderOfThisFile..'HeroComp')
require(folderOfThisFile..'OnDamageComp')
require(folderOfThisFile..'TweenComp')
require(folderOfThisFile..'Restriction')
