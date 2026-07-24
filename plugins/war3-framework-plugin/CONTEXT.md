# War3 Lua 框架导入插件

把 rouge_lua 的 Lua+JASS 协作框架(`lib/` 层 + 引导链)提取成 Claude 插件,往无框架或框架不全的 war3 自定义地图里导入。决策记录见 `docs/adr/`。

## Language

### 引导机制

**exec-lua 桥**:
YDWE 运行时 hook 了 `AbilityId`,遇到 `"exec-lua:NAME"` 前缀的调用就加载 `NAME.lua` 文件。JASS 引导 Lua 的唯一入口约定。
_Avoid_: ExecuteFunc 桥(那是反向的、Lua 侧的)

**initializePlugin**:
`war3map.j` 中 YDWE 注入的引导函数,函数体含 `StartCampaignAI(...,"callback")` 与 `AbilityId("exec-lua:plugin_main")`。框架在 JASS 侧的起点。

**callback**:
YDWE 触发器运行时的混淆 JASS 文件,由 `StartCampaignAI(...,"callback")` 加载。属于触发器机制,不是 Lua 引导。
_Avoid_: 把它当 Lua 加载器

**引导链**:
框架启动路径:`war3map.j`(initializePlugin / exec-lua) -> `plugin_main.lua` -> `path.lua`(设 `package.path`) -> `script/init.lua` -> `lib/` + `src/`。

**native.lua 反向桥**:
`lib/ac/native.lua` 的 `ExecuteFunc(name)`--JASS 触发器 `call ExecuteFunc("Fn")` 经 YDWE hook 可调 Lua 全局函数 `Fn`;native.lua 提供 Lua 侧分派(Lua 优先,无则回退 `jass.ExecuteFunc`)。Lua 拦截 JASS 调用的机制。

### 范围

**框架**:
指 `lib/` 层(ac/ecs/ui/util/Fsm)+ 引导链(plugin_main / path / native.lua)。可复用基础设施,区别于 `src/` 游戏逻辑。

**目标地图**:
被导入框架的 war3 自定义地图。

**基线**:
目标地图导入前的运行时起点。两档:**YDWE-Lua**(已有 jass.* 运行时 + initializePlugin)与**纯 JASS**(war3map.j 无 exec-lua,需注入 initializePlugin)。

### 格式与模块

**lni 源码**:
w3x2lni 解包后的地图源码格式(`war3map.j` 为可编辑文本)。插件操作的目标格式;用户自行用 w2l 解包/编译,插件不捆绑 w2l。

**脚手架**(scaffold):
插件**新写**的极简通用 `src/`(Game 循环 / State / Selector / GameEvent / UnitNumeric 机制 + UnitObj/PlayerObj 桩 + 示例 Battle 状态),剥掉 MoeHero 专属属性与实体。区别于 `lib/`(框架,原样拷)与 rouge_lua 的 `src/`(MoeHero 游戏内容,不照搬)。

**可选模块**:
核心框架外、默认全装的功能簇:**HTTP/远程数据**(socket.dll + libwinpthread-1.dll + http/http_socket/pcrypt/remote_data/11api/skyapi)、**字体**(fonts.ttf)、**品牌**(wenhao_plugin.tga)、**DzApi**(dzapi.lua)。可手动排除。

**冲突策略**(layered):
目标已有部分框架时的按类处理:`lib/` 覆盖(权威);脚手架存在则跳过(目标会改);入口文件(plugin_main/path/script-init)存在则合并、否则新建;`war3map.j` 仅缺失时注入;assets(dll/字体)存在则跳过。
