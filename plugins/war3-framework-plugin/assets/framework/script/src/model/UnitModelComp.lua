-- model/UnitModelComp.lua — 纯标记组件(标识"这是一个单位实体")
-- 提炼自 rouge_lua model/UnitModelComp.lua
-- 设计:退化为纯标记,供 System 的 requires() 过滤单位实体
-- 属性职责由 types/Attribute 承担(唯一权威)

UnitModelComp = Component.create('UnitModelComp')

return UnitModelComp
