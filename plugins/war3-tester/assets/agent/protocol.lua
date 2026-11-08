-- ============================================================================
-- protocol.lua - War3 LLM Agent 协议定义与消息工厂
-- ============================================================================

local protocol = {}

-- 错误码定义
protocol.ErrorCode = {
    OK = 0,
    TIMEOUT = "TIMEOUT",
    BAD_REQUEST = "BAD_REQUEST",
    INVALID_ACTION = "INVALID_ACTION",
    INVALID_TARGET = "INVALID_TARGET",
    STALE_REF = "STALE_REF",
    NOT_CASTABLE = "NOT_CASTABLE",
    COOLDOWN = "COOLDOWN",
    NO_MANA = "NO_MANA",
    SILENCED = "SILENCED",
    INTERNAL_ERROR = "INTERNAL_ERROR",
    NOT_FROZEN = "NOT_FROZEN",
    ALREADY_FROZEN = "ALREADY_FROZEN"
}

--- 构造成功响应结构
---@param id string 请求 ID
---@param payload table|nil 返回数据载荷
---@return table
function protocol.make_success(id, payload)
    return {
        id = id,
        ok = true,
        payload = payload or {}
    }
end

--- 构造错误响应结构
---@param id string 请求 ID
---@param code string 错误码
---@param message string 错误说明
---@return table
function protocol.make_error(id, code, message)
    return {
        id = id,
        ok = false,
        error = {
            code = code or protocol.ErrorCode.INTERNAL_ERROR,
            message = message or "Unknown error"
        }
    }
end

return protocol
