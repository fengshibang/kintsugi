local folderOfThisFile = (...):match("(.-)[^%/%.]+$")..'Restriction.'
local RestrictionSystem = {
    ['定身'] = require(folderOfThisFile..'定身'),
    ['缴械'] = require(folderOfThisFile..'缴械'),
    ['免死'] = require(folderOfThisFile..'免死'),
    ['隐身'] = require(folderOfThisFile..'隐身'),
    ['隐藏'] = require(folderOfThisFile..'隐藏'),
    ['免控'] = require(folderOfThisFile..'免控'),
    ['晕眩'] = require(folderOfThisFile..'晕眩'),
    ['无敌'] = require(folderOfThisFile..'无敌'),
}
return RestrictionSystem
