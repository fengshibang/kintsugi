-- core/Game.lua — 固定帧率游戏循环
-- 提炼自 rouge_lua core/Game.lua,剥 MoeHero 专属状态切换逻辑
-- 设计:20ms/50fps 固定帧率,通过 ac.loop 驱动;每帧调用当前 State 的 OnGameUpdate

Game = {}

local mCurrentState = nil

Game.DeltaTime = 0.02  -- 20ms = 50fps
Game.Elapsed = 0

function Game.curState()
    return mCurrentState
end

function Game.setState(state)
    mCurrentState = state
end

function Game.OnGameUpdate()
    local dt = Game.DeltaTime
    if mCurrentState ~= nil then
        Game.Elapsed = Game.Elapsed + dt
        if not mCurrentState:OnGameUpdate(dt) then
            mCurrentState = nil
        end
    end
end

-- 启动固定帧率循环(单位毫秒)
-- 注:ac.loop 在 lib/ac/timer.lua 定义,需确保 ac 已加载
if ac and ac.loop then
    ac.loop(Game.DeltaTime * 1000, Game.OnGameUpdate)
end
