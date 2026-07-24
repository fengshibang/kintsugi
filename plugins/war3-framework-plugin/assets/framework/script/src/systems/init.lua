-- systems/init.lua — 加载 systems 层模块
-- 提炼自 rouge_lua systems,只含通用 RPG 系统

local folderOfThisFile = (...):match("(.-)[^%/%.]+$")..'systems.'

require(folderOfThisFile..'Restriction')
require(folderOfThisFile..'DamageSystem')
require(folderOfThisFile..'BuffSystem')
require(folderOfThisFile..'EquipSystem')
require(folderOfThisFile..'SkillSystem')
require(folderOfThisFile..'BulletSystem')
require(folderOfThisFile..'TweenSystem')
require(folderOfThisFile..'EffectSystem')
