// initializePlugin.j — 注入到目标 war3map.j 的 JASS 引导函数
// 来源:rouge_lua war3map.j:38019-38025 的 initializePlugin 结构
// 用途:由 main 在 call InitBlizzard() 之后直接调用,激活 YDWE exec-lua 桥
//   - StartCampaignAI(Player(PLAYER_NEUTRAL_AGGRESSIVE), "callback")
//     加载 YDWE 触发器混淆 JASS 文件 callback(属于触发器机制,非 Lua 加载器)
//   - AbilityId("exec-lua:plugin_main")
//     YDWE 运行时 hook 了 AbilityId,遇到 "exec-lua:NAME" 前缀就加载 NAME.lua
//     这是 JASS 引导 Lua 的唯一入口约定
function initializePlugin takes nothing returns integer
    call ExecuteFunc("DoNothing")
    call StartCampaignAI(Player(PLAYER_NEUTRAL_AGGRESSIVE), "callback")
    call ExecuteFunc("DoNothing")
    call AbilityId("exec-lua:plugin_main")
    return 0
endfunction
