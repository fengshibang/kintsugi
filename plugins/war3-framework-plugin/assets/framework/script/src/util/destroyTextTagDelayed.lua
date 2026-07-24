local jass = require 'jass.common'

---延迟销毁漂浮文字（替代 JASS YDWETimerDestroyTextTag）
---@param time number 显示时间（秒）
---@param tt userdata 漂浮文字句柄
return function(time, tt)
    if time <= 0 then time = 0.01 end
    jass.SetTextTagPermanent(tt, false)
    jass.SetTextTagLifespan(tt, time)
    jass.SetTextTagFadepoint(tt, time)
end
