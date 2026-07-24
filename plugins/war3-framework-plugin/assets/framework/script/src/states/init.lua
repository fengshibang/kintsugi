-- states/init.lua — 加载示例状态
-- 设计：加载脚手架提供的示例状态（教学用途）
-- 注意：本文件不自动加载（不进入 src/init.lua 主链），用户按需 require

local folderOfThisFile = (...):match("(.-)[^%/%.]+$")..'states.'

-- 加载示例 Battle 状态
require(folderOfThisFile..'ExampleBattle')
