---
name: war3-test
description: "通用 War3 地图自动测试入口：编译 → 启动 → 测试 → 结果回传"
---

# /war3-test - War3 地图自动测试

本命令调用 `war3-auto-test` skill，执行通用 War3 地图自动测试流程。

## 使用方式

```
/war3-test [test_name] [test_file]
```

## 流程

1. 调用 `war3-auto-test` skill
2. 按最小契约执行：编译 → 启动游戏 → 注入测试 → HTTP 回传结果
3. 输出测试报告

## 前置条件

- 插件已安装（`/plugin install war3-tester`）
- 目标项目已配置 `config.json`（test_dir / test_module_prefix / compile）
- 测试文件已编写（定义 `RunAutoTest()` + HTTP POST 到 8766）
- WSL 用户需在 Windows 侧启动 `win_proxy.py`

## 示例

```bash
# 运行指定测试
/war3-test test_example test_example.lua

# 仅编译验证
/war3-test --compile-only
```

详细契约说明见 `skills/war3-auto-test/SKILL.md`。
