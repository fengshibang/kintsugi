local folderOfThisFile = (...):match("(.-)[^%/%.]+$")..'Restriction.'

require(folderOfThisFile..'StopMoveComp')
require(folderOfThisFile..'StunComp')
require(folderOfThisFile..'AbunComp')
require(folderOfThisFile..'InvulnerableComp')
require(folderOfThisFile..'OneDamageComp')
require(folderOfThisFile..'AvoidDeathComp')
require(folderOfThisFile..'HideComp')
require(folderOfThisFile..'StealthComp')
require(folderOfThisFile..'ControlFreeComp')
