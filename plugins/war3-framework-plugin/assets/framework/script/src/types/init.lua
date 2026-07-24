-- types/init.lua — 加载 types 层模块
-- 顺序:point(坐标) → Attribute(属性框架)

-- 初始化 Types 表(供 point/Attribute 等挂载)
Types = Types or {}

local folderOfThisFile = (...):match("(.-)[^%/%.]+$")..'types.'

require(folderOfThisFile..'point')
require(folderOfThisFile..'Attribute')
