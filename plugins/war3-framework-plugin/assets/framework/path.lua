-- path.lua — 设置 package.path,让后续 require 能找到框架文件
-- 注:已从 rouge_lua 清洗,剥本地开发路径硬编码分支(原 is_local + D:\war3项目\wjsg\map\)
-- 仅保留地图相对路径分支,适用于任何 lni 源码地图
package.path = package.path .. ";"
    .. "?\\init.lua;"
    .. "script\\?.lua;"
    .. "script\\?\\init.lua;"
    .. "script\\core\\?.lua;"
    .. "script\\core\\?\\init.lua;"

-- 返回 false 表示"非本地开发路径"(原 rouge_lua 返回 is_local 布尔值,
-- plugin_main.lua 用此值打日志分支;框架分发场景一律为 false)
return false
