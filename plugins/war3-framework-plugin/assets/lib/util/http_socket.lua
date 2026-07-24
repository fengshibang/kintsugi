-- ============================================================================
-- http_socket.lua - LuaSocket HTTP 客户端
-- ============================================================================
-- 功能：
--   1. 使用 LuaSocket 发送 HTTP 请求
--   2. 不依赖 DzAPI 平台，直接连接 WSL HTTP 服务器
--   3. 支持 POST/GET 方法，超时处理
-- 使用：
--   local http = require('script.lib.util.http_socket')
--   http.post('http://172.30.48.1:8766/result', {test='data'})
-- 注意：
--   本模块使用 LuaSocket 直接连接服务器，不依赖 DzAPI。
--   如需使用网易对战平台的 HTTP 接口，请使用 `script.lib.util.http`
-- ============================================================================

local socket = require("socket")
local json = require('script.lib.util.json')
local http = {}

-- 模块路径前缀（动态获取）
local MODULE_PATH = (...):match("(.-)[^%/%.]+$") or ""

--- HTTP 默认配置
http.config = {
    timeout = 5,  -- 超时时间（秒）
}

--- 解析 URL
---@param url string URL 字符串
---@return string host, number port, string path
local function parse_url(url)
    local host, port, path = url:match("^http://([^:/]+):?(%d*)(/?.*)$")
    if not host then
        error("无效的 URL 格式：" .. url)
    end
    port = port and tonumber(port) or 80
    path = path and path or "/"
    return host, port, path
end

--- 接收 HTTP 响应（公共函数）
---@param tcp table TCP socket
---@return string body 响应体
local function receive_response(tcp)
    local chunks = {}
    while true do
        local chunk, _, partial = tcp:receive("*a")
        if chunk then
            chunks[#chunks + 1] = chunk
            break
        elseif partial and #partial > 0 then
            chunks[#chunks + 1] = partial
        else
            break
        end
    end
    local response = table.concat(chunks, "")

    -- 解析响应，提取 body
    local body_start = response:find("\r\n\r\n")
    if body_start then
        return response:sub(body_start + 4)
    end
    return response
end

--- 发送 HTTP 请求（公共函数）
---@param method string HTTP 方法 ("POST" 或 "GET")
---@param url string 目标 URL
---@param body string|nil 请求体（仅 POST）
---@param timeout number 超时时间
---@return boolean success 是否成功
---@return string|nil response 响应体或错误信息
local function send_request(method, url, body, timeout)
    -- 解析 URL
    local host, port, path = parse_url(url)

    -- 创建 TCP socket
    local tcp = socket.tcp()
    if not tcp then
        return false, "无法创建 TCP socket"
    end

    -- 确保 socket 最终被关闭（异常路径保护）
    local function cleanup()
        pcall(function() tcp:close() end)
    end

    -- 设置超时
    tcp:settimeout(timeout)

    -- 连接服务器
    local ok, err = tcp:connect(host, port)
    if not ok then
        cleanup()
        return false, "连接失败：" .. (err or "unknown error")
    end

    -- 构建 HTTP 请求头
    local request
    if method == "POST" then
        request = string.format(
            "POST %s HTTP/1.1\r\n" ..
            "Host: %s:%d\r\n" ..
            "Content-Type: application/json\r\n" ..
            "Content-Length: %d\r\n" ..
            "Connection: close\r\n" ..
            "\r\n" ..
            "%s",
            path, host, port, #body, body
        )
    else
        request = string.format(
            "GET %s HTTP/1.1\r\n" ..
            "Host: %s:%d\r\n" ..
            "Connection: close\r\n" ..
            "\r\n",
            path, host, port
        )
    end

    -- 发送请求
    local sent, send_err = tcp:send(request)
    if not sent then
        cleanup()
        return false, "发送失败：" .. (send_err or "unknown error")
    end

    -- 接收响应
    local response = receive_response(tcp)

    cleanup()
    return true, response
end

--- 发送 HTTP POST 请求
---@param url string 目标 URL
---@param data table 要发送的数据（会被转换为 JSON）
---@param callback function|nil 回调函数 callback(response, error)
---@param timeout number|nil 超时时间（秒），默认 5 秒
---@return boolean success 是否成功
---@return string|nil result 响应体或错误信息
function http.post(url, data, callback, timeout)
    timeout = timeout or http.config.timeout

    -- 编码 JSON 数据
    local body = json.encode(data)

    local success, result = send_request("POST", url, body, timeout)

    if callback then
        if success then
            callback(result, nil)
        else
            callback(nil, result)
        end
    end

    return success, result
end

--- 发送 HTTP GET 请求
---@param url string 目标 URL
---@param callback function|nil 回调函数 callback(response, error)
---@param timeout number|nil 超时时间（秒），默认 5 秒
---@return boolean success 是否成功
---@return string|nil result 响应体或错误信息
function http.get(url, callback, timeout)
    timeout = timeout or http.config.timeout

    local success, result = send_request("GET", url, nil, timeout)

    if callback then
        if success then
            callback(result, nil)
        else
            callback(nil, result)
        end
    end

    return success, result
end

return http
