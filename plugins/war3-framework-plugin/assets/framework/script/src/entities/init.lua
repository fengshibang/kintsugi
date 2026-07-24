-- entities/init.lua — 加载 entities 层模块
-- 提炼自 rouge_lua entities,只含通用 RPG 实体
-- 顺序:PlayerObj(桩) → UnitObj(桩) → BuffObj → AuraObj → EffectObj → SkillObj

local folderOfThisFile = (...):match("(.-)[^%/%.]+$")..'entities.'

require(folderOfThisFile..'PlayerObj')
require(folderOfThisFile..'UnitObj')
require(folderOfThisFile..'BuffObj')
require(folderOfThisFile..'AuraObj')
require(folderOfThisFile..'EffectObj')
require(folderOfThisFile..'SkillObj')
