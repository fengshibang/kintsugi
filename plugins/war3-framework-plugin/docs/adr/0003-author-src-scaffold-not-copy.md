# src/ 新写脚手架而非照搬

插件导入 `lib/` 原样作框架,但 `src/` **不照搬** rouge_lua 的--而是新写一份极简通用脚手架(Game 循环 / State / Selector / GameEvent / UnitNumeric 机制 + UnitObj/PlayerObj 桩 + 示例 Battle 状态)。因为 rouge_lua 的 `src/` 与 MoeHero 实体/属性(PlayerObj/UnitObj、攻击/生命/力量/元素等)深度纠缠,且 `src/init.lua` 把 types/core/model/entities/components/systems/states/界面/Buffs 作为整体加载,没有可直接拷的通用部分;照搬会泄漏游戏特定内容、把"游戏"当"框架"分发。
