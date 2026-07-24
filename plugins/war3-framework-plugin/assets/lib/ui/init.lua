local folderOfThisFile = (...):match("(.-)[^%/%.]+$")
require(folderOfThisFile .. "ui.base.init")
require(folderOfThisFile .. "ui.client.init")
require(folderOfThisFile .. "ui.server.init")