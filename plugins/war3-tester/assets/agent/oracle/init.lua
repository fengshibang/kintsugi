-- ============================================================================
-- oracle/init.lua - Bug Oracle 框架与调度中心
-- ============================================================================

local oracle = {}
local events = require 'script.src.auto-test.agent.events'

local registered_oracles = {}
local dedup_cache = {} -- key -> { last_time = ..., count = ... }
local DEDUP_WINDOW_SEC = 10.0

--- 注册一个 Oracle 检测器
---@param def table
function oracle.register(def)
    if not def or not def.name or not def.check then return end
    table.insert(registered_oracles, {
        name = def.name,
        interval = def.interval or 1.0,
        severity = def.severity or "medium",
        check = def.check,
        last_check_time = 0
    })
end

--- 检查去重窗口
local function is_dedup(key, now)
    local entry = dedup_cache[key]
    if not entry then
        dedup_cache[key] = { last_time = now, count = 1 }
        return false, 1
    end

    if now - entry.last_time < DEDUP_WINDOW_SEC then
        entry.count = entry.count + 1
        return true, entry.count
    else
        local prev_count = entry.count
        entry.last_time = now
        entry.count = 1
        return false, prev_count
    end
end

--- 周期性调度检测
function oracle.tick()
    local now_clock = ac and ac.clock and ac.clock() or 0
    local now_sec = now_clock / 1000.0

    local ctx = {
        clock = now_clock,
        sec = now_sec
    }

    for _, o in ipairs(registered_oracles) do
        if o.interval > 0 and (now_sec - o.last_check_time >= o.interval) then
            o.last_check_time = now_sec

            local ok, violations = pcall(o.check, ctx)
            if not ok then
                events.push('oracle_crash', {
                    oracle = o.name,
                    error = tostring(violations)
                })
            elseif violations and type(violations) == 'table' then
                for _, v in ipairs(violations) do
                    local subject = v.subject or "global"
                    local dedup_key = o.name .. ":" .. tostring(subject)
                    local dup, count = is_dedup(dedup_key, now_sec)

                    if not dup then
                        events.push('violation', {
                            oracle = o.name,
                            severity = o.severity,
                            msg = v.msg or "Violation detected",
                            data = v.data or {},
                            repeat_count = count,
                            frame = now_clock
                        })
                    end
                end
            end
        end
    end
end

-- 加载首批内置 Oracle
pcall(require, 'script.src.auto-test.agent.oracle.runtime_error')
pcall(require, 'script.src.auto-test.agent.oracle.numeric')
pcall(require, 'script.src.auto-test.agent.oracle.consistency')
pcall(require, 'script.src.auto-test.agent.oracle.leak')
pcall(require, 'script.src.auto-test.agent.oracle.stuck')

return oracle
