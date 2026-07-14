# examples/minimal — 最小纯逻辑项目（通用性验证床）

本目录展示「无任何 Lua 框架依赖的纯逻辑项目」如何接入 war3-tester 插件。
用于验证插件的桌面单测层（M2）对**任意项目**通用，不依赖 wzns 或其他特定框架。

## 项目特点

| 特性 | 说明 |
|------|------|
| **零 jass 依赖** | 不调用任何 War3 原生函数（CreateUnit、GetUnitName 等） |
| **零框架依赖** | 不 require 任何 wzns/ecs/其他框架模块 |
| **纯 Lua 5.3** | 可在桌面解释器直接运行，秒级反馈 |
| **最小契约** | 测试文件定义 `RunAutoTest()` + 设 `_G.__test_result` |

## 目录结构

```
minimal/
├── src/
│   └── math_utils.lua        # 纯逻辑模块（阶乘/斐波那契/GCD/素数/字符串）
├── tests/
│   ├── test_math_utils.lua   # 桌面单测（unit 层）
│   └── test_fail_demo.lua    # 故意失败的测试（验证失败路径）
├── .gitignore                # 忽略 _war3_tester/（运行时产物）
└── README.md                 # 本文件
```

> **注意**：`tests/_war3_tester/` 目录**不进版本控制**。
> 它是 `run_unit_test` 运行时自动注入的产物（从插件 `server/` 拷贝
> `jass_mock.lua`/`assertions.lua`/`desktop_bootstrap.lua` 到
> `test_dir/_war3_tester/`）。详见下方「运行桌面单测」。

## 接入 war3-tester

### config.json 配置

```json
{
  "test": {
    "test_dir": "tests",
    "test_module_prefix": "",
    "test_bootstrap_template": null
  },
  "compile": {
    "enabled": false
  }
}
```

- `test_dir`: 测试文件目录（相对 source_dir）
- `test_module_prefix`: 空字符串（测试文件用裸名 require）
- `test_bootstrap_template`: null（不需要自定义引导，用插件默认）
- `compile.enabled`: false（纯逻辑项目无需编译地图）

### 运行桌面单测

```bash
# 方式 1：通过 MCP 工具（推荐，自动注入 _war3_tester/ 产物）
run_unit_test(test_name="test_math_utils", source_dir="<path_to_minimal>")

# 方式 2：手动命令行（需先注入产物，见下方说明）
lua5.3 tests/_war3_tester/desktop_bootstrap.lua test_math_utils <source_dir> <test_dir>
```

#### 手动运行前置步骤

`run_unit_test` 会自动把插件 `server/` 下的 3 个产物注入到
`test_dir/_war3_tester/`。若手动运行，需先执行注入：

```bash
# 1. 创建产物目录
mkdir -p tests/_war3_tester

# 2. 拷贝插件产物（server/ 路径取决于插件安装位置）
cp <plugin>/server/jass_mock.lua       tests/_war3_tester/
cp <plugin>/server/assertions.lua      tests/_war3_tester/
cp <plugin>/server/desktop_bootstrap.lua tests/_war3_tester/

# 3. 运行测试（注意 desktop_bootstrap.lua 在 tests/_war3_tester/ 下）
lua5.3 tests/_war3_tester/desktop_bootstrap.lua test_math_utils <source_dir> <test_dir>

# 参数说明：
#   test_module: test_math_utils（裸名，由 package.path 相对 test_dir 解析）
#   source_dir:  minimal/src（让 require('math_utils') 能解析）
#   test_dir:    minimal/tests（让 require('_war3_tester.xxx') 能解析）
```

> **为什么产物在 `tests/_war3_tester/` 而非项目根？**
> `desktop_bootstrap.lua` 的 `package.path` 配置为从 `test_dir` 查找，
> `require('_war3_tester.assertions')` 会解析为 `test_dir/_war3_tester/assertions.lua`。
> 产物注入位置由 `desktop_runner.py` 第 145 行 `wt_dir = test_dir / '_war3_tester'` 决定。

## 通用性验证

本目录用于验证：
1. **插件通用性**：war3-tester 不依赖特定 Lua 框架
2. **最小契约**：只需 `RunAutoTest()` + `_G.__test_result` 即可工作
3. **桌面单测层**：M2 功能对任意项目可用

## 与 examples/wzns/ 的对比

| 维度 | examples/minimal/ | examples/wzns/ |
|------|-------------------|----------------|
| 框架依赖 | 无 | wzns ECS 框架 |
| 测试引导 | 插件默认 | 自定义框架适配器 |
| require 路径 | 裸名 `test_xxx` | 点分 `script.src.auto-test.test_xxx` |
| 适用场景 | 纯逻辑模块、算法库 | 完整游戏项目 |
| 编译需求 | 无 | 需编译地图 |

## 测试文件契约

测试文件必须满足最小契约：

```lua
-- 1. 定义全局 RunAutoTest 函数
function RunAutoTest()
    -- 2. 执行测试逻辑
    local success, err = pcall(function()
        -- 测试代码
    end)

    -- 3. 设 _G.__test_result 供 desktop_bootstrap 解析
    _G.__test_result = {
        success = success,
        test_name = 'test_xxx',
        details = success and 'all passed' or tostring(err),
        cases = {},
    }
end
```

## 断言库使用

插件内置断言库由 `desktop_bootstrap` 注入到 `_G.__war3_tester_assertions`：

```lua
local assert_lib = _G.__war3_tester_assertions or {}
local assertEquals = assert_lib.assertEquals or function(a, b, msg) error(msg or 'assertion failed') end
local assertTrue = assert_lib.assertTrue or function(cond, msg) if not cond then error(msg or 'assertTrue failed') end end

-- 使用
assertEquals(1, 1, '1 应等于 1')
assertTrue(true, '条件应为真')
```

## 下一步

1. 运行 `run_unit_test(test_name="test_math_utils")` 验证桌面单测层
2. 运行 `run_unit_test(test_name="test_fail_demo")` 验证失败路径
3. 修改 `math_utils.lua` 故意引入 bug，观察测试失败
4. 添加新测试用例，验证 TDD 循环
