-- ============================================================================
-- oracle/runtime_error.lua - 运行时 Lua 错误 Oracle
-- ============================================================================

local oracle = require 'script.src.auto-test.agent.oracle.init'

local pending_errors = {}

function _G.__agent_record_lua_error(msg, traceback)
    table.insert(pending_errors, {
        msg = tostring(msg),
        traceback = tostring(traceback)
    })
end

oracle.register({
    name = "runtime.lua_error",
    interval = 0.5,
    severity = "high",
    check = function(ctx)
        if #pending_errors == 0 then return nil end

        local violations = {}
        for _, err in ipairs(pending_errors) do
            table.insert(violations, {
                subject = err.msg,
                msg = "Lua 运行时错误: " .. err.msg,
                data = {
                    error = err.msg,
                    traceback = err.traceback
                }
            })
        end
        pending_errors = {}
        return violations
    end
})
