-- core/init.lua — 加载 core 层模块
-- 顺序:Game(循环) → GameEvent(事件类) → AssetsManager(工厂) → state(基类) → Selector(选择器)

local folderOfThisFile = (...):match("(.-)[^%/%.]+$")..'core.'

require(folderOfThisFile..'Game')
require(folderOfThisFile..'GameEvent')
require(folderOfThisFile..'AssetsManager')
require(folderOfThisFile..'state')
require(folderOfThisFile..'Selector')
