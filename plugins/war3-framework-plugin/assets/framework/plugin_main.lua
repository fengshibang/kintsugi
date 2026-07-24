-- plugin_main.lua — Lua 入口,由 JASS 侧 initializePlugin 通过 exec-lua 桥调用
-- 注:已从 rouge_lua 清洗,剥 MoeHero 专属的 japi.SetOwner('问号')
local bool, res = pcall(require, 'path')
console = require 'jass.console'
print = console.write

if res then
    print('本地路径')
else
    print('地图内路径')
end

print('初始化')
xpcall(function ()
    require 'script'
end, function (msg)
    print(msg, '\n', debug.traceback())
end)
