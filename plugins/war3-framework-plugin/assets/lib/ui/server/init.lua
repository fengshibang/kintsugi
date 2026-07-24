local folderOfThisFile = (...):match("(.-)[^%/%.]+$")
local ui = require(folderOfThisFile .. "util")
require(folderOfThisFile .. "trigger")
require(folderOfThisFile .. "sync")