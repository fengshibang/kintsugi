// initializePlugin.j — 注入到目标 war3map.j 的 JASS 引导函数
// 来源:rouge_lua war3map.j:38019-38025 的 initializePlugin 结构
// 实证:wzns(map/war3map.j:1484)逐字对齐,函数体与量产成品一致
// 用途:激活 YDWE exec-lua 桥,是 JASS 引导 Lua 的唯一入口约定
// 调用时机(wzns 实证):由 main 在函数体顶部调用,位于 call InitBlizzard() 之前
//   ⚠ 非原始注释所述"InitBlizzard() 之后"——量产地图(main 第 1 行)即在
//     YDWE 生成的 CreateRegions/相机/昼夜 调用之前、JASS InitBlizzard 之前执行,
//     保证 plugin_main.lua 尽早接管后续初始化。
//
// 函数体逐调用说明(对齐 wzns 成品,保留勿删):
//   - StartCampaignAI(Player(PLAYER_NEUTRAL_AGGRESSIVE), "callback")
//     加载 YDWE 触发器混淆 JASS 文件 callback(属于触发器机制,非 Lua 加载器)
//   - AbilityId("exec-lua:plugin_main")
//     YDWE 运行时 hook 了 AbilityId,遇到 "exec-lua:NAME" 前缀就加载 NAME.lua
//     这是 JASS 引导 Lua 的唯一入口约定。勿改用 ExecuteFunc 桥——那是反向的
//     (Lua 侧 native.lua 拦截 JASS 调用),不是 JASS->Lua 引导。
//   - ExecuteFunc("DoNothing")
//     YDWE 生成的空操作/防内联泥浆(遍布量产 war3map.j),无害,随成品保留。
function initializePlugin takes nothing returns integer
    call ExecuteFunc("DoNothing")
    call StartCampaignAI(Player(PLAYER_NEUTRAL_AGGRESSIVE), "callback")
    call ExecuteFunc("DoNothing")
    call AbilityId("exec-lua:plugin_main")
    return 0
endfunction