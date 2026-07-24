-- script/init.lua — 框架引导:加载 lib/ + src/
-- 注:已从 rouge_lua 清洗,剥 war3-tester 测试钩子(test_runner / test_reporter)
-- 正常游戏无 auto-test 目录,原 pcall 静默跳过,但为干净分发直接移除
require('script.lib')
require('script.src')
