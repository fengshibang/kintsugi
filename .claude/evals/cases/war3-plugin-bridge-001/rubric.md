# Rubric — war3-plugin-bridge-001

被测会话应产出一份能对接 wzns 测试框架、且规避 3 个静默失效陷阱的引导适配器 `run_auto_test.lua`。

## CHECK skill-invoked            [layer=logic]
被测是否调用 `Skill` 工具加载 `war3-auto-test`（war3-tester 插件的领域 skill）。
判定依据：评审「被测会话调用的工具」列表里出现 `Skill`（且与 war3 测试/插件开发相关）。
（baseline `--disallowedTools Skill` 应为 fail → baseline delta 即 skill 触发增量。）

## RED require-dotted-path        [layer=static]
引导适配器加载 `_target_test` 必须用 wzns 的点分完整路径，**禁裸名 require**。
裸名 `require('_target_test')` 在 wzns 打包路径下找不到模块 → `__auto_test_mode` 被置 false →
测试被静默跳过（崩溃级静默失效）。

auto-fail（命中即 fail，在 product/ 下执行，引用 $CHANGED_FILES）:
```
grep -rnE "require\(\s*['\"]_target_test['\"]\s*\)" $CHANGED_FILES | grep -vE ":\s*--" | grep -q .
```
（产出含非注释的裸名 require → exit0 → fail；注释里的说明文字被 `grep -vE ":\s*--"` 排除。
必须用 `script.src.auto-test._target_test` 点分路径。）

## RED module-prefix-once         [layer=logic]
`test_module` 字段（base，不含前缀）与 `test_module_prefix` 的拼接**只发生一次**，禁双重前缀。
判定依据：产出的 module 拼接逻辑——`test_module` 用作 base，`test_module_prefix` 拼其前；
不得出现「把已含前缀的完整路径再拼一次前缀」。师傅 LLM 对照 prompt 陷阱 2 的正解判定（二元可判）。

## CHECK http-host-from-config    [layer=static]
HTTP 上报地址（host/port）从 `_target_test.lua` 的 `http_host`/`http_port` 读取，禁硬编码端口。

auto-pass（在 product/ 下执行）:
```
grep -rqE "http_host|http_port" $CHANGED_FILES
```

## CHECK silent-degrade          [layer=logic]
`_target_test.lua` 不存在时（正常游戏），引导适配器必须静默降级：pcall 包裹 require、
失败则 `_G.__auto_test_mode = false` 后 `return`，不抛错、不阻断游戏加载。
判定依据：产出含 pcall 包裹 + 失败 return 的降级路径。

## CHECK runtime-end-to-end      [layer=run]
运行验证：用产出替换 `examples/wzns/run_auto_test.framework.lua` 后，实跑 `test_commit`
（test_skill_a00d）应收到 HTTP 200 + 测试结果（非超时）。待用户回填。
