local folderOfThisFile = (...):match("(.-)[^%/%.]+$")
require(folderOfThisFile .. "util")
require(folderOfThisFile .. "sync")