-- ============================================================================
-- bridge.lua - C 模块 (luaopen_agent_bridge) 与 FFI 双模接口绑定及通道收发封装
-- ============================================================================

local bridge = {
    available = false,
    broken = false,
    mode = nil, -- 'cmod' | 'ffi'
}

local json = require 'script.lib.util.json'
local protocol = require 'script.src.auto-test.agent.protocol'

-- 1. 优先尝试标准 Lua C 模块 require('agent_bridge')（兼容 War3 内置 yd_lua_engine）
local cmod_ok, cmod = pcall(require, 'agent_bridge')
if cmod_ok and type(cmod) == 'table' and type(cmod.version) == 'function' then
    bridge.available = true
    bridge.mode = 'cmod'
    bridge.cmod = cmod
end

-- 2. 回退尝试 FFI (ffi.load)
local ffi = nil
local lib = nil
local DEFAULT_CAP = 65536
local buf_cap = DEFAULT_CAP
local cmd_buf = nil

if not bridge.available then
    local ffi_ok, ffi_mod = pcall(require, 'ffi')
    if ffi_ok and ffi_mod then
        local cdef_ok = pcall(function()
            ffi_mod.cdef[[
            int  AB_Version(void);
            int  AB_Init(const char* pipe_name);
            int  AB_InstanceId(void);
            int  AB_WaitCommand(char* buf, int cap, int timeout_ms);
            int  AB_PendingSize(void);
            int  AB_PushResult(const char* json);
            int  AB_PushEvent(const char* json);
            int  AB_Log(const char* msg);
            int  AB_RequestCapture(int max_w, int max_h, int quality);
            int  AB_CaptureStatus(void);
            ]]
        end)
        if cdef_ok then
            local lib_ok, loaded_lib = pcall(ffi_mod.load, 'agent_bridge.asi')
            if lib_ok and loaded_lib then
                ffi = ffi_mod
                lib = loaded_lib
                cmd_buf = ffi.new('char[?]', buf_cap)
                bridge.available = true
                bridge.mode = 'ffi'
                bridge.lib = lib
            end
        end
    end
end

if not bridge.available then
    return bridge
end

--- 初始化管道
---@param pipe_name string|nil
---@return boolean
function bridge.init(pipe_name)
    if bridge.broken or not bridge.available then return false end
    if bridge.mode == 'cmod' then
        local ok, res = pcall(bridge.cmod.init, pipe_name)
        if not ok or (type(res) == 'number' and res < 0) then
            bridge.broken = true
            return false
        end
        return true
    else
        local ok, res = pcall(lib.AB_Init, pipe_name)
        if not ok or res < 0 then
            bridge.broken = true
            return false
        end
        return true
    end
end

--- 获取模块实例 ID
---@return number
function bridge.instance_id()
    if not bridge.available then return 0 end
    if bridge.mode == 'cmod' then
        local ok, id = pcall(bridge.cmod.instance_id)
        return ok and id or 0
    else
        local ok, id = pcall(lib.AB_InstanceId)
        return ok and id or 0
    end
end

--- 获取版本
---@return number
function bridge.version()
    if not bridge.available then return 0 end
    if bridge.mode == 'cmod' then
        local ok, ver = pcall(bridge.cmod.version)
        return ok and ver or 0
    else
        local ok, ver = pcall(lib.AB_Version)
        return ok and ver or 0
    end
end

--- 写入调试日志
---@param msg string
function bridge.log(msg)
    if not bridge.available or bridge.broken then return end
    if bridge.mode == 'cmod' then
        pcall(bridge.cmod.log, tostring(msg))
    else
        pcall(lib.AB_Log, tostring(msg))
    end
end

--- 轮询/阻塞拉取命令
---@param timeout_ms number
---@return table|nil command
function bridge.poll(timeout_ms)
    if not bridge.available or bridge.broken then return nil end

    local str = nil
    if bridge.mode == 'cmod' then
        local ok, res_str = pcall(bridge.cmod.wait_command, timeout_ms or 0)
        if not ok then
            bridge.broken = true
            return nil
        end
        if type(res_str) ~= 'string' or #res_str == 0 then
            return nil
        end
        str = res_str
    else
        local ok, n = pcall(lib.AB_WaitCommand, cmd_buf, buf_cap, timeout_ms or 0)
        if not ok then
            bridge.broken = true
            return nil
        end
        if n == -2 then -- AB_E_BUF_SMALL
            local needed = lib.AB_PendingSize()
            if needed > 0 then
                buf_cap = needed + 1024
                cmd_buf = ffi.new('char[?]', buf_cap)
                ok, n = pcall(lib.AB_WaitCommand, cmd_buf, buf_cap, 0)
                if not ok or n <= 0 then return nil end
            else
                return nil
            end
        elseif n <= 0 then
            return nil
        end
        str = ffi.string(cmd_buf, n)
    end

    local data, decode_ok = json.decode(str)
    if not decode_ok then
        bridge.log("[Bridge] JSON decode error: " .. tostring(str))
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

    if bridge.mode == 'cmod' then
        local push_ok, res = pcall(bridge.cmod.push_result, json_str)
        return push_ok and (res >= 0)
    else
        local push_ok, res = pcall(lib.AB_PushResult, json_str)
        return push_ok and (res >= 0)
    end
end

--- 推送事件到 ASI 环形缓冲
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

    if bridge.mode == 'cmod' then
        local ok, res = pcall(bridge.cmod.push_event, json_str)
        return ok and (res >= 0)
    else
        local ok, res = pcall(lib.AB_PushEvent, json_str)
        return ok and (res >= 0)
    end
end

return bridge
