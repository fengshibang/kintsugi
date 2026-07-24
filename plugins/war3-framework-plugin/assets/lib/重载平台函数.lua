local code = require 'jass.code'
local hook = require 'jass.hook'
local jass = require 'jass.common'
local japi = require 'jass.japi'
local g = require 'jass.globals'
local dbg = require 'jass.debug'
local slk = require 'jass.slk'



if g.Current_Platform == g.Platform_11 then
    function code.DzAPI_Map_SaveServerValue(whichPlayer,  key,  value)
        code.YDWESaveRemoteData(whichPlayer,  key,  value)
        return true
    end

    function code.DzAPI_Map_GetServerValue(whichPlayer,  key)
        return code.YDWERPGGetRemoteData(whichPlayer,  key)
    end

    function code.DzAPI_Map_GetStoredInteger(whichPlayer,  key)
        return code.YDWERPGGetKey(whichPlayer,  key)
    end

    function code.DzAPI_Map_StoreInteger(whichPlayer,  key,value)
        code.YDWERPGSetKey(whichPlayer,  key,value)
    end
end
