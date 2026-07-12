-- ============================================================================
-- test_nopause.lua - loadlib 探测 + DLL 加载脚本
-- ============================================================================
-- 用途：分两步验证 + 激活
--   ① 探测：本定制 Lua 是否支持 package.loadlib（决定整个方案是否可行）
--   ② 加载：加载 nopause.dll，触发窗口子类化
--
-- 执行方式（任选其一）：
--   方式 A（inspect_game 一行命令，推荐先做）：
--     在游戏运行时，用 war3-tester 的 inspect_game 工具执行：
--       package.loadlib('D:/war3/nopause.dll','luaopen_nopause')()
--     成功返回 true（或无返回），失败会抛错。
--
--   方式 B（完整脚本）：把本文件 require 进地图，或整段贴进 inspect_game 执行。
--
-- ⚠️ 先改下面的 DLL_PATH 为你 nopause.dll 的真实路径（注意用正斜杠 /）
-- ==========================================================================

local DLL_PATH = 'D:/war3/nopause.dll'
local FUNC     = 'luaopen_nopause'

print('================ nopause loadlib 探测 ================')
print('package.loadlib =', type(package.loadlib))
print('package.cpath   =', package.cpath or '(nil)')
print('DLL_PATH        =', DLL_PATH)

---------- 第 0 步：loadlib 本身是否可用 ----------
if type(package.loadlib) ~= 'function' then
    print('❌ [致命] package.loadlib 不可用 —— 本 Lua 沙箱禁止加载 C DLL')
    print('   方案到此为止，require DLL 这条路走不通。只能改用 WFE 独立注入。')
    return
end
print('✅ package.loadlib 可用')

---------- 第 1 步：DLL 文件是否存在 ----------
local f = io.open(DLL_PATH, 'rb')
if not f then
    print('❌ [环境] DLL 文件不存在:', DLL_PATH)
    print('   先把 nopause.c 编译成 nopause.dll 放到该路径，再跑本脚本。')
    print('   编译命令见 README.md')
    return
end
f:close()
print('✅ DLL 文件存在')

---------- 第 2 步：加载 DLL 并调用 luaopen ----------
-- loadlib 返回一个 C 函数；调用它才真正执行 luaopen_nopause
local ok_load, fn = pcall(package.loadlib, DLL_PATH, FUNC)
if not ok_load then
    print('❌ [加载失败] loadlib 报错:', fn)
    print('   常见原因：')
    print('   1) 32/64 位不匹配 —— war3 是 32 位，DLL 必须用 i686 / -m32 编译')
    print('   2) DLL 依赖缺失 —— 加 -static 重编译（见 README）')
    print('   3) 导出函数名不对 —— 用 objdump -p nopause.dll 看 Export Table')
    return
end
print('✅ loadlib 成功取到导出函数:', FUNC)

local ok_call, err = pcall(fn)
if not ok_call then
    print('❌ [luaopen 执行失败]:', err)
    return
end

print('✅✅✅ nopause.dll 已加载并安装子类化')
print('   现在请按 Alt+Tab 切到别的窗口 / 最小化 war3，观察游戏是否还暂停。')
print('   若仍暂停 → war3 不靠窗口消息判断，本方案失效（见 README 的 v2/v3 说明）')
print('   若不暂停 → 成功！后台挂机可用。')
print('======================================================')
