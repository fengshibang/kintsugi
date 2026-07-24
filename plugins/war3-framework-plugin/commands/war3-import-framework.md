# /war3-import-framework

把 Lua+JASS 协作框架导入到目标 war3 自定义地图。

## 用法

```
/war3-import-framework <目标地图 lni 源码目录>
```

## 流程

详见 `skills/import-framework/` 下的指令 markdown。本命令是入口,触发 Claude 按
skill 指令执行:检测目标基线 -> 展示改动并确认 -> 注入 initializePlugin ->
拷贝引导链 + lib/ -> 校验。

## 前置

- 目标必须是 **lni 源码格式**(w3x2lni 解包后的目录,含可编辑 `war3map.j`)。
  若目标是 `.w3x` 二进制,提示用户先用 `w2l.exe lni` 解包。
- 目标地图作者需自备 w2l 编译与 YDWE 启动能力(本票 MVP 暂未捆绑 w2l;ticket 09 将推翻 ADR-0002、捆绑 w3x2lni/w2l + jasshelper + rsa 工具链)。

## 产出

导入成功后目标目录新增/改动:
- `war3map.j` — 注入 `initializePlugin` 函数定义 + `main` 中的调用
- `plugin_main.lua` — 顶层 Lua 入口
- `path.lua` — `package.path` 设置(已剥本地开发路径硬编码)
- `script/init.lua` — 引导 `lib/` + `src/`(已剥 war3-tester 钩子)
- `script/src/init.lua` — 极简脚手架哨兵(设 `_G.__framework_booted = true`)
- `script/lib/` — 框架层(ac/ecs/ui/util/Fsm + CleanMemory + 重载函数)

## 验收

导入后 YDWE 启动地图,inspect 读 `_G.__framework_booted == true` 应为真。
