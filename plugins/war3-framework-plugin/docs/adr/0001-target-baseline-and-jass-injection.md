# 目标基线与 JASS 引导注入

支持两种目标基线:YDWE-Lua 地图与纯 JASS 地图。纯 JASS 地图通过往 `war3map.j` 注入 `initializePlugin` 函数(含 `call AbilityId("exec-lua:plugin_main")` 与 `StartCampaignAI(...,"callback")`)激活 YDWE Lua,而非要求用户在 YDWE 编辑器侧"开 Lua"--因为 YDWE 的 exec-lua 桥是运行时对 `AbilityId` 的 hook,注入 JASS 一行 + 拷文件即可起,目标只需在 YDWE 下运行。文档原称 `call ExecuteFunc("plugin_main")` 是误述,实际是 `exec-lua:` 前缀桥。
