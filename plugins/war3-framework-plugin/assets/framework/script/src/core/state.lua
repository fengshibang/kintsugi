-- core/state.lua — State 基类
-- 提炼自 rouge_lua core/state.lua
-- 设计:所有游戏状态(Battle/Menu/Lobby 等)继承此基类,实现 OnGameUpdate 等方法

State = class("State")

function State:initialize()
end

function State:OnGameUpdate(dt)
    -- 返回 false 表示状态结束,Game 循环会清空 mCurrentState
    return true
end

function State:update(dt) end
function State:draw() end
function State:load() end
