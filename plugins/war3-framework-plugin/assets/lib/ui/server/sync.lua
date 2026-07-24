local folderOfThisFile = (...):match("(.-)[^%/%.]+$")
local ui = require(folderOfThisFile .. "util")

local event = {
    on_sync = function(key_hash, event_hash, args)
        local key = ui.get_str(key_hash)
        local event_name = ui.get_str(event_hash)

        if key == nil then
            ecs.debugError('同步错误， 不存在的键值' .. key_hash)
        end
        if event_name == nil then
            ecs.debugError('同步错误， 不存在的事件名' .. event_hash)
        end

        args = args or {}

        local button = ac.sync_key_map[key]
        if button == nil then
            ecs.debugError('同步错误， 不存在的按钮' .. key)
            return
        end

        print('派发同步事件', event_name, table.unpack(args))
        button:event_callback(event_name, ui.player, table.unpack(args))

    end,
}

ui.register_event('sync', event)