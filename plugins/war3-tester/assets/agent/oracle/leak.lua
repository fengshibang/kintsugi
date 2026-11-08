-- ============================================================================
-- oracle/leak.lua - 泄漏监测 Oracle
-- ============================================================================

local oracle = require 'script.src.auto-test.agent.oracle.init'

local timer_samples = {} -- { { time = ..., count = ... } }
local SAMPLE_WINDOW_SEC = 60.0

oracle.register({
    name = "leak.timers",
    interval = 5.0,
    severity = "medium",
    check = function(ctx)
        if not (ac and ac.timer_size) then return nil end

        local cur_count = ac.timer_size()
        local now_sec = ctx.sec

        table.insert(timer_samples, { time = now_sec, count = cur_count })

        -- 清理超过 60 秒的样本
        while #timer_samples > 0 and (now_sec - timer_samples[1].time > SAMPLE_WINDOW_SEC) do
            table.remove(timer_samples, 1)
        end

        if #timer_samples >= 10 then
            local oldest = timer_samples[1].count
            local diff = cur_count - oldest
            -- 60 秒内净增长超过 100 个计时器
            if diff > 100 then
                return {
                    {
                        subject = "global_timers",
                        msg = "检测到计时器持续泄漏 (60s 内净增 " .. diff .. ")",
                        data = { current = cur_count, diff_60s = diff }
                    }
                }
            end
        end
        return nil
    end
})
