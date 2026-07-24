game = {}
local folderOfThisFile = (...):match("(.-)[^%/%.]+$")
require(folderOfThisFile .. "timer")
require(folderOfThisFile .. "game")
require(folderOfThisFile .. "keyboard")
require(folderOfThisFile .. "template")  -- [UBERTIP 诊断] 禁掉加载期 load_fdf/LoadToc，验证是否为 ubertip 变小元凶