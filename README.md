# kintsugi — Claude Code 插件集合

> 金缮（kintsugi）：用金漆修补破碎之处，让裂痕成为美的一部分。
>
> 本仓库是一个 Claude Code [插件市场（marketplace）](https://code.claude.com/docs/en/plugin-marketplaces)，收录以下插件。

## 收录插件

| 插件 | 说明 |
|------|------|
| **[mentor-kit](plugins/mentor-kit/)** | 师徒试错机制 + eval 框架：师傅监督徒弟改代码，把错误沉淀成 eval case，回归验证。领域中立，任何项目装上即用。 |
| **[war3-tester](plugins/war3-tester/)** | 通用 War3 地图自动测试 MCP 插件：编译地图 → 启动游戏 → 注入测试脚本 → 接收游戏内 HTTP 回传结果。最小契约（`RunAutoTest` + HTTP POST），不限 Lua 框架。 |

## 安装

在 Claude Code 中添加本市场并按需安装插件：

```
/plugin marketplace add fengshibang/kintsugi
/plugin install mentor-kit@kintsugi
/plugin install war3-tester@kintsugi
```

安装 `war3-tester` 后，其 MCP server 会自动注册（声明于 `plugins/war3-tester/.mcp.json`，首次使用走逐服务器审批，用 `/mcp` 查看状态）。

## 目录结构

```
kintsugi/
├── .claude-plugin/marketplace.json   # 市场清单（注册两个插件）
├── plugins/
│   ├── mentor-kit/                   # 师徒试错 + eval 框架
│   └── war3-tester/                  # 通用 War3 测试 MCP
├── LICENSE
└── README.md
```

各插件的安装、配置、使用详见各自目录下的 `README.md`。

## License

见 [LICENSE](LICENSE)。
