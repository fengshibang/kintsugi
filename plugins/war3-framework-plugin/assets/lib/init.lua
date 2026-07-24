local folderOfThisFile = (...)..'.'
require(folderOfThisFile..'ac')
-- require(folderOfThisFile..'重载函数')
-- require(folderOfThisFile..'重载平台函数')
-- require(folderOfThisFile..'Fsm')
local ecs =  require(folderOfThisFile..'ecs')
ecs.initialize()
require(folderOfThisFile..'ui')
require(folderOfThisFile..'CleanMemory')

