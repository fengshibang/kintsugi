-- core/GameEvent.lua — ECS 事件类定义
-- 提炼自 rouge_lua core/GameEvent.lua,剥 MoeHero 专属事件(内力恢复/副本清空/子弹碰撞等)
-- 设计:每个事件类含 info 表存储事件参数;通过 eventManager:fireEvent 派发

-- ========== 单位事件 ==========

--任意单位死亡
AnyUnitDeath = class("AnyUnitDeath")
function AnyUnitDeath:initialize(killingUnit, dyingUnit)
    self.info = { killingUnit, dyingUnit }
end

--任意单位攻击
AnyUnitAttack = class("AnyUnitAttack")
function AnyUnitAttack:initialize(attackUnit, defUnit)
    self.info = { attackUnit, defUnit }
end

--任意单位伤害
AnyUnitDamaged = class("AnyUnitDamaged")
function AnyUnitDamaged:initialize(attackUnit, defUnit, damage)
    -- 简化:直接传 handle,不查 engine(原 rouge_lua 用 getEntityWithHandle,但 Engine 无此方法)
    self.info = { attackUnit, defUnit, damage }
end

--任意单位即将死亡
AnyUnitAboutToDie = class("AnyUnitAboutToDie")
function AnyUnitAboutToDie:initialize(triggerUnit, killer)
    self.info = { triggerUnit, killer }
end

--任意单位提升等级
AnyHeroLevelUp = class("AnyHeroLevelUp")
function AnyHeroLevelUp:initialize(triggerUnit, level)
    self.info = { triggerUnit, level }
end

-- ========== 单位指令事件 ==========

--任意单位发布无目标指令
AnyUnitIssueImmediateOrder = class("AnyUnitIssueImmediateOrder")
function AnyUnitIssueImmediateOrder:initialize(issueUnit, orderStr)
    self.info = { issueUnit, orderStr }
end

--任意单位发布点目标指令
AnyUnitIssuePointOrder = class("AnyUnitIssuePointOrder")
function AnyUnitIssuePointOrder:initialize(issueUnit, orderStr, point)
    self.info = { issueUnit, orderStr, point }
end

--任意单位发布目标指令
AnyUnitIssueTargetOrder = class("AnyUnitIssueTargetOrder")
function AnyUnitIssueTargetOrder:initialize(issueUnit, orderId, target)
    self.info = { issueUnit, orderId, target }
end

-- ========== 技能事件 ==========

--任意单位学习技能
AnyUnitLearnedSkill = class("AnyUnitLearnedSkill")
function AnyUnitLearnedSkill:initialize(learnedUnit, abilityId)
    self.info = { learnedUnit, abilityId }
end

--任意单位开始施法
AnyUnitSpellCast = class("AnyUnitSpellCast")
function AnyUnitSpellCast:initialize(caster, abilityId, target)
    self.info = { caster, abilityId, target }
end

--任意单位发动技能效果
AnyUnitSpellEffect = class("AnyUnitSpellEffect")
function AnyUnitSpellEffect:initialize(spellUnit, abilityId, spellTarget)
    self.info = { spellUnit, abilityId, spellTarget }
end

--任意单位施法出手
AnyUnitSpellFinish = class("AnyUnitSpellFinish")
function AnyUnitSpellFinish:initialize(spellUnit, abilityId, spellTarget)
    self.info = { spellUnit, abilityId, spellTarget }
end

-- ========== 建造/训练事件 ==========

--任意单位完成建造
AnyUnitConstructFinish = class("AnyUnitConstructFinish")
function AnyUnitConstructFinish:initialize(triggerPlayer, constructedStructure)
    self.info = { triggerPlayer, constructedStructure }
end

--任意单位完成训练
AnyUnitTrainFinish = class("AnyUnitTrainFinish")
function AnyUnitTrainFinish:initialize(triggerPlayer, trainedUnit)
    self.info = { triggerPlayer, trainedUnit }
end

--任意单位升级建造
AnyUnitUpgradeFinish = class("AnyUnitUpgradeFinish")
function AnyUnitUpgradeFinish:initialize(triggerPlayer, triggerUnit)
    self.info = { triggerPlayer, triggerUnit }
end

-- ========== 玩家事件 ==========

--任意玩家输入字符串
AnyPlayerChat = class("AnyPlayerChat")
function AnyPlayerChat:initialize(player, msg)
    self.info = { player, msg }
end

--任意玩家选择单位
AnyPlayerSelectUnit = class("AnyPlayerSelectUnit")
function AnyPlayerSelectUnit:initialize(player, unit)
    self.info = { player, unit }
end

--任意玩家选择英雄
AnyPlayerPickHero = class("AnyPlayerPickHero")
function AnyPlayerPickHero:initialize(player, hero)
    self.info = { player, hero }
end

--任意玩家离开游戏
AnyPlayerLeave = class("AnyPlayerLeave")
function AnyPlayerLeave:initialize(player)
    self.info = { player }
end

--任意玩家按下 esc 键
AnyPlayerEsc = class("AnyPlayerEsc")
function AnyPlayerEsc:initialize(player)
    self.info = { player }
end

--任意玩家按下按键
AnyPlayerKeyDown = class("AnyPlayerKeyDown")
function AnyPlayerKeyDown:initialize(player, keystr)
    self.info = { player, keystr }
end

-- ========== 物品事件 ==========

--任意单位使用物品
AnyUnitUseItem = class("AnyUnitUseItem")
function AnyUnitUseItem:initialize(unit, item)
    self.info = { unit, item }
end

--任意单位捡取物品
AnyUnitPickUpItem = class("AnyUnitPickUpItem")
function AnyUnitPickUpItem:initialize(unit, item)
    self.info = { unit, item }
end

--任意单位丢弃物品
AnyUnitDropItem = class("AnyUnitDropItem")
function AnyUnitDropItem:initialize(unit, item)
    self.info = { unit, item }
end

--任意单位出售道具
AnyUnitSellItem = class("AnyUnitSellItem")
function AnyUnitSellItem:initialize(unit, item, buyingUnit, soldItem, sellingUnit)
    self.info = { unit, item, buyingUnit, soldItem, sellingUnit }
end

--任意单位出售单位
AnyUnitSellUnit = class("AnyUnitSellUnit")
function AnyUnitSellUnit:initialize(unit, soldUnit, buyingUnitHandle, soldUnitHandle)
    self.info = { unit, soldUnit, buyingUnitHandle, soldUnitHandle }
end

-- ========== 区域事件 ==========

--任意单位进入可用地图区域
AnyUnitEnterRect = class("AnyUnitEnterRect")
function AnyUnitEnterRect:initialize(unit)
    self.info = { unit }
end

--任意单位进入不规则区域
AnyUnitEnterRegion = class("AnyUnitEnterRegion")
function AnyUnitEnterRegion:initialize(unit, region)
    self.info = { unit, region }
end

--任意单位离开不规则区域
AnyUnitLeaveRegion = class("AnyUnitLeaveRegion")
function AnyUnitLeaveRegion:initialize(unit, region)
    self.info = { unit, region }
end

-- ========== 属性事件 ==========

--任意单位设置属性
AnyUnitAttributeChanged = class("AnyUnitAttributeChanged")
function AnyUnitAttributeChanged:initialize(unit, unitAttributeType, unitModuleType, delta)
    self.info = { unit, unitAttributeType, unitModuleType, delta }
end

--任意伤害获取属性
AnyDamageAttribute = class("AnyDamageAttribute")
function AnyDamageAttribute:initialize(source, target, damage)
    self.info = { source, target, damage }
end

-- ========== 路径事件 ==========

--路径节点通知
PathNodeNotify = class("PathNodeNotify")
function PathNodeNotify:initialize(pathNode)
    self.info = { pathNode }
end

--路径终点通知
PathEndedNotify = class("PathEndedNotify")
function PathEndedNotify:initialize(entity)
    self.info = { entity }
end
