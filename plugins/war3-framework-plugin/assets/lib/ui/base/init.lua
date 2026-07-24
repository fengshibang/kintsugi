local folderOfThisFile = (...):match("(.-)[^%/%.]+$")
require(folderOfThisFile .. "controls.init")
require(folderOfThisFile .. "detail.init")
