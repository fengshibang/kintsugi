-- ============================================================================
-- bridge.lua - 标准 Lua 5.3 C 模块 (luaopen_agent_bridge) 绑定及命名管道收发封装
-- ============================================================================

local bridge = {
    available = false,
    broken = false,
    mode = nil,
}

local json = require 'script.lib.util.json'

-- 加载标准 Lua C 模块 require('agent_bridge') -> map/agent_bridge.dll (luaopen_agent_bridge)
local cmod_ok, cmod = pcall(require, 'agent_bridge')
if cmod_ok and type(cmod) == 'table' and type(cmod.version) == 'function' then
    bridge.available = true
    bridge.mode = 'cmod'
    bridge.cmod = cmod
end

if not bridge.available then
    return bridge
end

--- 初始化命名管道
---@param pipe_name string|nil
---@return boolean
function bridge.init(pipe_name)
    if bridge.broken or not bridge.available then return false end
    local ok, res = pcall(bridge.cmod.init, pipe_name)
    if not ok or (type(res) == 'number' and res < 0) then
        bridge.broken = true
        return false
    end
    return true
end

--- 获取模块实例 ID
---@return number
function bridge.instance_id()
    if not bridge.available then return 0 end
    local ok, id = pcall(bridge.cmod.instance_id)
    return ok and id or 0
end

--- 获取版本
---@return number
function bridge.version()
    if not bridge.available then return 0 end
    local ok, ver = pcall(bridge.cmod.version)
    return ok and ver or 0
end

--- 写入调试日志 (map/agent_bridge.log)
---@param msg string
function bridge.log(msg)
    if not bridge.available or bridge.broken then return end
    pcall(bridge.cmod.log, tostring(msg))
end

--- 轮询/阻塞拉取命令
---@param timeout_ms number
---@return table|nil command
function bridge.poll(timeout_ms)
    if not bridge.available or bridge.broken then return nil end

    local ok, res_str = pcall(bridge.cmod.wait_command, timeout_ms or 0)
    if not ok then
        bridge.broken = true
        return nil
    end
    if type(res_str) ~= 'string' or #res_str == 0 then
        return nil
    end

    local data, decode_ok = json.decode(res_str)
    if not decode_ok then
        bridge.log("[Bridge] JSON decode error: " .. tostring(res_str))
        return nil
    end
    return data
end

--- 发送响应
---@param id string
---@param ok boolean
---@param payload_or_err any
---@return boolean
function bridge.reply(id, ok, payload_or_err)
    if not bridge.available or bridge.broken then return false end

    local json_str
    if ok then
        local str_ok, p_str = pcall(json.encode, payload_or_err or {})
        if not str_ok or not p_str then p_str = "{}" end
        json_str = '{"id":' .. json.encode(tostring(id)) .. ',"ok":true,"payload":' .. p_str .. '}'
    else
        local err_code = "INTERNAL_ERROR"
        local err_msg = tostring(payload_or_err)
        if type(payload_or_err) == 'table' then
            err_code = payload_or_err.code or err_code
            err_msg = payload_or_err.message or err_msg
        end
        local str_ok, e_str = pcall(json.encode, { code = err_code, message = err_msg })
        if not str_ok or not e_str then e_str = '{"code":"INTERNAL_ERROR"}' end
        json_str = '{"id":' .. json.encode(tostring(id)) .. ',"ok":false,"error":' .. e_str .. '}'
    end

    local push_ok, res = pcall(bridge.cmod.push_result, json_str)
    return push_ok and (res >= 0)
end

--- 推送事件到环形缓冲
---@param kind string 事件类型
---@param data table 数据
---@return boolean
function bridge.event(kind, data)
    if not bridge.available or bridge.broken then return false end

    local evt = data or {}
    evt.kind = kind
    if ac and ac.clock then
        evt.frame = ac.clock()
        evt.game_time = ac.clock() / 1000.0
    end

    local enc_ok, json_str = pcall(json.encode, evt)
    if not enc_ok or not json_str then
        return false
    end

    local ok, res = pcall(bridge.cmod.push_event, json_str)
    return ok and (res >= 0)
end

return bridge
