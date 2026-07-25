# import-framework skill

本 skill 指导 Claude 完成 `/war3-import-framework` 命令的导入流程。
流程由 Claude 驱动(检测 / 注入 / 拷贝 / 校验),本 skill 是给 Claude 的指令,
不是独立可执行程序。

## 前置检查

1. **确认目标是项目根(workspaceRoot)**
   - **目标语义**:目标是**项目根**(workspaceRoot),不是 `map/` 子目录
   - 必须含 `map/war3map.j`(可编辑文本)——地图源码在 `map/` 子目录内
   - 若目标是 `.w3x` 二进制,提示用户先用 `w2l.exe lni <file.w3x>` 解包(若目标已有 `tools/` 可直接用 `tools/w3x2lni/w2l.exe`,见下文「工具链捆绑」)
   - 若 `map/war3map.j` 不存在或为二进制,停止并报错
   - **兼容旧结构**:若目标根直接有 `war3map.j`(无 `map/` 子目录),提示用户"建议结构:将 war3map.j 等地图文件移入 `map/` 子目录,tools/.vscode 放项目根"。仍可继续导入(此时 `map/` 等同于项目根),但在预览中标注"非标准结构,建议迁移"
   - 正确结构:
     ```
     workspaceRoot/(= 项目根 = 插件目标)
       map/                  # 地图源码(war3map.j + framework/lib/plugin_main/script)
         war3map.j
         plugin_main.lua
         script/
       tools/                # 工具链(map 外,项目根)
       .vscode/              # VS Code 任务(map 外,项目根)
     ```

2. **读取 CONTEXT.md 与 docs/adr/**
   - 术语表 `CONTEXT.md`
   - ADR-0001(目标基线与 JASS 注入)
   - ADR-0002(lni 源码格式)
   - ADR-0003(src/ 新写脚手架而非照搬)
   - ADR-0004(自包含打包)

## 基线检测

读目标 `map/war3map.j`,判断基线类型。

### 检测锚点(三组 grep)

```bash
# A 组:initializePlugin 函数定义(非调用)
grep -nE "^function[[:space:]]+initializePlugin[[:space:]]+takes" map/war3map.j

# B 组:exec-lua 桥调用(YDWE 运行时 hook AbilityId 加载 plugin_main.lua)
grep -nE 'AbilityId\("exec-lua:plugin_main"\)' map/war3map.j

# C 组:callback 加载(YDWE 触发器混淆 JASS,与 exec-lua 桥配对)
grep -nE 'StartCampaignAI\(.*"callback"\)' map/war3map.j

# 辅助锚点(定位 main 函数,注入用)
grep -nE "^function[[:space:]]+main[[:space:]]+takes" map/war3map.j
grep -nE "call[[:space:]]+InitBlizzard\(\)" map/war3map.j
```

### 基线判定规则(组合判定,非单 grep)

| 锚点组合 | 判定 | 处理路径 |
|---|---|---|
| **A + B 同时命中**(C 可选) | **YDWE-Lua 基线** | 跳过 war3map.j 注入,仅拷文件 + 入口合并 |
| **A、B 均未命中** | **纯 JASS 基线** | 执行完整注入流程 |
| **A 命中但 B 未命中** | **异常/半初始化** | 报错停止,提示用户检查 war3map.j 是否被手动改坏 |
| **A 未命中但 B 命中** | **异常/非标准 YDWE** | 报错停止,提示用户可能用了非 YDWE 官方 Lua 桥 |

**为什么必须 A + B 组合**:
- 单 A(`initializePlugin` 函数定义)可能只是用户手写同名函数(无 exec-lua 桥则不是 YDWE-Lua 引导)
- 单 B(`exec-lua:plugin_main` 字符串)可能是注释/字符串常量(无函数定义则无法调用)
- A + B 同时成立 = 真有 YDWE-Lua 引导函数且会执行 exec-lua 桥 = 框架可复用该引导

### YDWE-Lua 基线处理流程(跳过注入)

检测到 YDWE-Lua 基线后,**绝对不动 war3map.j**:

1. **不注入** `initializePlugin` 函数定义(目标已有)
2. **不插入** `call initializePlugin()` 调用(目标 main 已有)
3. **不修改** war3map.j 任何一行(避免破坏目标已有的引导链/触发器/物编引用)
4. 直接进入「拷贝框架文件」节(见下文),按冲突策略处理入口合并
5. 在改动预览中明确标注:"检测到 YDWE-Lua 基线,war3map.j 保持不变"

### 纯 JASS 基线处理流程(完整注入)

按「注入 initializePlugin」节执行完整注入。

### 两档基线差异报告(预览阶段向用户展示)

| 项 | YDWE-Lua 基线 | 纯 JASS 基线 |
|---|---|---|
| war3map.j 修改 | **不动**(跳过注入) | 注入 initializePlugin 定义 + 调用 |
| plugin_main.lua | 合并(保留用户定制) | 新建 |
| path.lua | 覆盖(框架权威) | 新建 |
| script/init.lua | 合并(保留用户定制) | 新建 |
| script/lib/ | 覆盖(框架权威) | 新建 |
| callback / (key) | 跳过(目标已有) | 新建 |
| 引导链起点 | 复用目标已有的 initializePlugin + exec-lua 桥 | 插件新注入 |

## 部分框架检测

基线检测判定 war3map.j 状态(YDWE-Lua / 纯 JASS)。部分框架检测判定**目标目录其他文件的状态**——目标可能已有部分 lib/、部分 src/、部分入口、部分 assets。导入时必须识别这些状态，按分层冲突策略处理，避免误覆盖用户定制。

### 检测锚点(四组)

```bash
# D 组:lib/ 框架层 — 检测关键框架文件是否存在(map/ 子目录内)
ls <workspaceRoot>/map/script/lib/ac/init.lua        # ac 框架核心
ls <workspaceRoot>/map/script/lib/ecs/Engine.lua     # ecs 框架核心
ls <workspaceRoot>/map/script/lib/ui/init.lua        # ui 框架核心
ls <workspaceRoot>/map/script/lib/ac/native.lua      # JASS↔Lua 桥
ls <workspaceRoot>/map/script/lib/util/middleclass.lua  # 第三方依赖
# 统计 lib/ 下文件数
find <workspaceRoot>/map/script/lib/ -type f -name '*.lua' | wc -l

# E 组:src/ 脚手架/游戏逻辑 — 检测脚手架与用户定制(map/ 子目录内)
ls <workspaceRoot>/map/script/src/init.lua           # src 入口(脚手架 or 用户定制)
ls <workspaceRoot>/map/script/src/core/Game.lua      # 脚手架核心
ls <workspaceRoot>/map/script/src/entities/          # 脚手架/用户实体
ls <workspaceRoot>/map/script/src/components/        # 用户组件(脚手架不含)
ls <workspaceRoot>/map/script/src/systems/           # 用户系统(脚手架不含)
# 统计 src/ 下文件数
find <workspaceRoot>/map/script/src/ -type f -name '*.lua' | wc -l

# F 组:入口文件 — 检测引导链文件(map/ 子目录内)
ls <workspaceRoot>/map/plugin_main.lua               # Lua 入口
ls <workspaceRoot>/map/path.lua                      # package.path 设置
ls <workspaceRoot>/map/script/init.lua               # 脚本引导
ls <workspaceRoot>/map/callback                      # YDWE 触发器
ls <workspaceRoot>/map/'(key)'                       # YDWE key

# G 组:assets — 检测二进制/可选资源(map/ 子目录内) + 工具链(项目根)
ls <workspaceRoot>/map/socket.dll                    # HTTP socket
ls <workspaceRoot>/map/libwinpthread-1.dll           # socket 依赖
ls <workspaceRoot>/map/fonts.ttf                     # 中文字体
ls <workspaceRoot>/tools/w3x2lni/w2l.exe             # 工具链(项目根,非 map/)
ls <workspaceRoot>/.vscode/tasks.json                # VS Code 任务(项目根)
```

### 部分框架状态判定

根据四组检测结果，判定目标处于以下哪种部分框架状态:

| 状态 | 特征 | 典型场景 |
|---|---|---|
| **全新地图** | D/E/F/G 全空 | 从未导入过框架 |
| **仅入口** | F 部分有(map/plugin_main + map/path)，D/E/G 空 | 用户手动写过引导 |
| **仅 lib/** | D 有，E/F 空 | 导入过 lib/ 但未完成引导链 |
| **仅 src/** | E 有，D/F 空 | 用户写过游戏逻辑但没用框架 |
| **入口 + lib/** | D + F 有，E 空 | 框架导入过但没写游戏逻辑 |
| **入口 + src/** | E + F 有，D 空 | 用户有引导 + 游戏逻辑，缺框架 |
| **lib/ + src/** | D + E 有，F 部分空 | 框架 + 游戏逻辑都有，引导链不全 |
| **完整框架** | D + E + F 全有 | 已导入过完整框架(升级场景) |
| **部分 lib/** | D 部分有(如只有 ac/ 没有 ecs/) | 旧版框架 / 手动拷过部分文件 |

### 部分 lib/ 特殊处理

当 D 组检测显示 lib/ **部分存在**时(文件数 < 框架全量 75 文件):

1. **不区分哪些是"旧的"哪些是"新的"** — lib/ 整体按框架权威处理
2. **整目录覆盖策略**:框架 lib/ 全量拷贝覆盖目标 script/lib/
   - 若目标 lib/ 有框架不包含的自定义文件 → 报告标注"目标自定义文件保留"(不删除)
   - 若目标 lib/ 有与框架同名但内容不同的文件 → 框架覆盖(权威)
3. **理由**:lib/ 是框架层，用户不应在 lib/ 内做定制(应在 src/ 做)。部分存在说明之前导入不完整或旧版，全量覆盖保证一致性

### 部分 src/ 特殊处理

当 E 组检测显示 src/ **部分存在**时:

1. **script/src/init.lua 存在** → 跳过(目标会改，见下文冲突策略)
2. **script/src/core/ 存在** → 跳过整个 core/ 目录(目标可能已定制 Game/State/Selector)
3. **script/src/entities/ 或 components/ 或 systems/ 存在** → 跳过这些目录(用户游戏逻辑)
4. **script/src/ 存在但为空** → 正常新建脚手架
5. **理由**:src/ 是用户游戏逻辑所在，任何已存在的内容都可能是用户定制，绝不能覆盖

## 改动预览与确认

注入前向用户展示改动清单。**根据基线检测结果分两档展示**，并结合部分框架检测结果给出**逐文件处理计划**。

### 完整改动计划模板(部分框架地图)

**执行前必须展示逐文件处理计划，用户确认后才执行**:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
完整改动计划(执行前确认)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

目标项目:<workspaceRoot>
基线类型:YDWE-Lua / 纯 JASS
部分框架状态:<状态名，如"入口 + lib/" / "部分 lib/" / "完整框架">

【war3map.j 处理】
  map/war3map.j — [保持不变(跳过 JASS 注入)] / [注入 initializePlugin 定义 + 调用]

【入口文件处理】
  map/plugin_main.lua — [已存在 → 合并:追加 require 'script'] / [不存在 → 新建]
  map/path.lua — [已存在 → 覆盖(框架权威)] / [不存在 → 新建]
  map/script/init.lua — [已存在 → 合并:追加 require('script.lib') + require('script.src')] / [不存在 → 新建]

【框架层处理】
  map/script/lib/* — 整目录覆盖(框架权威，<N> 文件)
    - 若目标 lib/ 有自定义文件 → 保留不删除(报告标注)

【脚手架/游戏逻辑处理】
  map/script/src/init.lua — [已存在 → 跳过] / [不存在 → 新建]
  map/script/src/core/ — [已存在 → 跳过整个目录] / [不存在 → 新建脚手架]
  map/script/src/entities/ — [已存在 → 跳过] / [不存在 → 新建]
  map/script/src/components/ — [已存在 → 跳过] / [不存在 → 新建]
  map/script/src/systems/ — [已存在 → 跳过] / [不存在 → 新建]

【YDWE 触发器处理】
  map/callback — [已存在 → 跳过] / [不存在 → 新建]
  map/(key) — [已存在 → 跳过] / [不存在 → 新建]

【assets 处理】
  map/socket.dll — [已存在 → 跳过] / [不存在 → 拷贝]
  map/libwinpthread-1.dll — [已存在 → 跳过] / [不存在 → 拷贝]
  map/fonts.ttf — [已存在 → 跳过] / [不存在 → 拷贝]

【工具链处理】
  tools/ — [已存在 → 跳过整个目录] / [不存在 → 拷贝]

【VS Code 配置处理】
  .vscode/ — [已存在 → 跳过] / [不存在 → 拷贝]

【可选模块处理】
  默认全装，排除:<用户指定排除的模块> / 无

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠ 确认后将按上述计划执行，不会覆盖用户定制(src/ + 入口合并)
⚠ 若目标 lib/ 有自定义文件，将保留不删除
⚠ war3map.j [保持不变 / 将被注入 initializePlugin]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

是否继续? [y/N]
```

**用户确认后才执行导入**。若用户拒绝，停止并保留目标原状。

### YDWE-Lua 基线预览模板(简化版)

```
检测到 YDWE-Lua 基线(map/war3map.j 已含 initializePlugin + exec-lua:plugin_main)
✓ map/war3map.j 保持不变(跳过 JASS 注入,复用目标已有引导链)

将拷贝以下文件到目标项目:
  - map/plugin_main.lua — [已存在 → 合并引导逻辑] / [不存在 → 新建]
  - map/path.lua — [已存在 → 覆盖(框架权威)] / [不存在 → 新建]
  - map/script/init.lua — [已存在 → 合并引导逻辑] / [不存在 → 新建]
  - map/script/src/init.lua — [已存在 → 跳过] / [不存在 → 新建]
  - map/script/lib/* — 覆盖(框架层,75 文件)
  - map/callback — [已存在 → 跳过] / [不存在 → 新建]
  - map/(key) — [已存在 → 跳过] / [不存在 → 新建]
  - 可选模块(默认全装,见下文「可选模块」节)
  - 工具链 tools/ — [已存在 → 跳过] / [不存在 → 新建]
  - VS Code 配置 .vscode/ — [已存在 → 跳过] / [不存在 → 新建]

入口合并策略(见下文「入口合并具体实现」节):
  - map/plugin_main.lua 已存在:追加 require 'script' 引导(若缺失)
  - map/script/init.lua 已存在:追加 require('script.lib') + require('script.src')(若缺失)
```

### 纯 JASS 基线预览模板(简化版)

```
检测到纯 JASS 基线(map/war3map.j 无 initializePlugin + exec-lua 桥)
⚠ 将注入 JASS 引导函数到 map/war3map.j

将往 map/war3map.j 注入:
  - initializePlugin 函数定义(在 main 之前)
  - call initializePlugin() 调用(在 main 的 call InitBlizzard() 之后)

将拷贝以下文件到目标项目:
  - map/plugin_main.lua — 新建
  - map/path.lua — 新建
  - map/script/init.lua — 新建
  - map/script/src/init.lua — 新建
  - map/script/lib/* — 新建(框架层,75 文件)
  - map/callback — 新建
  - map/(key) — 新建
  - 可选模块(默认全装,见下文「可选模块」节)
  - 工具链 tools/ — [已存在 → 跳过] / [不存在 → 新建]
  - VS Code 配置 .vscode/ — [已存在 → 跳过] / [不存在 → 新建]
```

等待用户确认后继续。

## 注入 initializePlugin

### 步骤 1:插入函数定义

在目标 `map/war3map.j` 中找到 `function main takes nothing returns nothing` 行,
在该行**之前**插入 `jass/initializePlugin.j` 的内容(含前后空行分隔)。

### 步骤 2:插入调用

在目标 `map/war3map.j` 中找到 `main` 函数体内的 `call InitBlizzard()` 行,
在该行**之后**插入 `    call initializePlugin()`(4 空格缩进)。

### 锚点找不到时

- 找不到 `function main`:报错"目标 map/war3map.j 缺 main 函数,非标准 WE 生成地图",停止
- 找不到 `call InitBlizzard()`:报错"目标 main 缺 InitBlizzard 调用,非标准 WE 生成地图",停止
- 已存在 `initializePlugin`:按 YDWE-Lua 基线处理(跳过注入)

## 拷贝框架文件

从插件 `assets/` 拷贝到目标项目:

| 源(插件 assets/) | 目标(目标项目) |
|---|---|
| `framework/plugin_main.lua` | `map/plugin_main.lua` |
| `framework/path.lua` | `map/path.lua` |
| `framework/script/init.lua` | `map/script/init.lua` |
| `framework/script/src/init.lua` | `map/script/src/init.lua` |
| `lib/*` | `map/script/lib/*`(全量 75 文件) |
| `framework/callback` | `map/callback` |
| `framework/(key)` | `map/(key)` |

### 分层冲突策略(按 CONTEXT.md layered 策略)

根据部分框架检测结果，对每类文件按以下精确规则处理:

| 文件类别 | 冲突策略 | 粒度 | 理由 |
|---|---|---|---|
| **script/lib/** | **整目录覆盖**(框架权威) | 目录级 | lib/ 是框架层，用户不应定制；部分存在说明导入不完整，全量覆盖保证一致性 |
| **script/src/init.lua** | **存在则跳过** | 文件级 | 脚手架入口，目标会改(可能已定制加载顺序) |
| **script/src/core/** | **存在则跳过整个目录** | 目录级 | 脚手架核心(Game/State/Selector)，目标可能已定制 |
| **script/src/entities/components/systems/** | **存在则跳过整个目录** | 目录级 | 用户游戏逻辑，绝不能覆盖 |
| **plugin_main.lua** | **存在则合并(追加 require)** | 文件级 | 入口文件，保留用户定制 |
| **path.lua** | **存在则覆盖** | 文件级 | package.path 必须包含框架路径，框架权威 |
| **script/init.lua** | **存在则合并(追加 require)** | 文件级 | 入口文件，保留用户定制 |
| **callback / (key)** | **存在则跳过** | 文件级 | YDWE 触发器机制，目标已有则不动 |
| **war3map.j** | **仅缺失 initializePlugin 才注入** | 文件级 | 纯 JASS 基线才注入，YDWE-Lua 基线不动 |
| **socket.dll / fonts.ttf 等 assets** | **存在则跳过** | 文件级 | 二进制资源，目标已有则不动 |
| **tools/** | **存在则跳过** | 目录级 | 工具链，目标已有则不动(见 ticket 09) |

#### 覆盖粒度说明

**整目录覆盖(script/lib/)**:
- 框架 lib/ 全量拷贝到目标 script/lib/
- 同名文件直接覆盖(框架权威)
- 目标 lib/ 有框架不包含的自定义文件 → **保留不删除**(报告标注)
- 理由:lib/ 是框架层，用户定制应在 src/，lib/ 内自定义属于误用

**目录级跳过(script/src/core/ 等)**:
- 若目标整个目录存在 → 跳过该目录所有文件
- 若目标目录不存在 → 新建该目录并拷贝脚手架
- 理由:src/ 是用户游戏逻辑，目录存在说明用户已定制

**文件级合并(plugin_main.lua / script/init.lua)**:
- 检测是否已含框架引导(见下文"入口合并具体实现")
- 已含 → 跳过合并
- 不含 → 在文件末尾追加引导逻辑(不修改现有内容)
- 理由:保留用户定制(japi.SetOwner / 自定义 console 等)

### 入口合并具体实现(YDWE-Lua 基线核心)

当目标已有入口文件时,**追加框架引导逻辑,不覆盖用户定制**。
合并策略基于 rouge_lua 真实入口结构(见 `map/plugin_main.lua`):

#### plugin_main.lua 合并策略

**目标已有 plugin_main.lua 时的合并规则**:

1. **检测是否已含框架引导**:
   ```bash
   grep -nE "require\s+['\"]script['\"]" <workspaceRoot>/map/plugin_main.lua
   ```
   - 若已含 `require 'script'` → 跳过合并(目标已引导框架)
   - 若不含 → 进入追加流程

2. **追加引导逻辑**(在文件末尾追加,不修改现有内容):
   ```lua
   -- [框架导入追加] 引导 lib/ + src/
   xpcall(function ()
       require 'script'
   end, function (msg)
       print(msg, '\n', debug.traceback())
   end)
   ```

3. **不删除/不修改目标已有的**:
   - `pcall(require, 'path')` 调用(目标可能有自己的 path 处理)
   - `console = require 'jass.console'` 重定义
   - `japi.SetOwner('问号')` 等用户定制
   - 任何其他 require / 业务逻辑

4. **path.lua 处理**:
   - 若目标已有 path.lua → **覆盖**(框架权威,package.path 必须包含框架路径)
   - 框架 path.lua 已剥本地开发路径硬编码,适用于任何 lni 源码地图
   - 若用户有特殊 path 需求,在合并报告中提示手动调整

#### script/init.lua 合并策略

**目标已有 script/init.lua 时的合并规则**:

1. **检测是否已含框架引导**:
   ```bash
   grep -nE "require\(['\"]script\.lib['\"]\)" <workspaceRoot>/map/script/init.lua
   grep -nE "require\(['\"]script\.src['\"]\)" <workspaceRoot>/map/script/init.lua
   ```
   - 若已含 `require('script.lib')` + `require('script.src')` → 跳过合并
   - 若不含 → 进入追加流程

2. **追加引导逻辑**(在文件末尾追加):
   ```lua
   -- [框架导入追加] 加载 lib/ + src/
   require('script.lib')
   require('script.src')
   ```

3. **不删除/不修改目标已有的**:
   - war3-tester 测试钩子(若目标有,保留)
   - 任何其他 require / 业务逻辑

#### 合并报告(向用户展示)

合并完成后,报告:
```
入口合并结果:
  plugin_main.lua — [已追加 require 'script' 引导] / [已含引导,跳过]
  path.lua — [已覆盖(框架权威)]
  script/init.lua — [已追加 require('script.lib') + require('script.src')] / [已含引导,跳过]

⚠ 若目标 plugin_main.lua 有特殊定制(如 japi.SetOwner / 自定义 console),
  框架追加的引导逻辑在文件末尾,不影响现有逻辑。
  若启动后框架未加载,检查 xpcall 错误输出。
```

## 可选模块

可选模块定义在 `assets/optional-modules.json`,包含 6 个模块:

1. **http** — HTTP/远程数据(socket.dll + libwinpthread-1.dll + 6 个 lua)
2. **fonts** — 中文字体(fonts.ttf)
3. **brand** — wenhao_plugin.tga(改名 YDWE 插件 dll,加载界面注入)→ `resource/`(项目根,map 外)
4. **dzapi** — DzApi 平台接口(dzapi.lua)
5. **util** — 通用工具集(9 个 lua):EventPool/fourcc/textTag/destroyTextTagDelayed/rushSlide/unitAlive/unitGetItemOfType/unitHasItem/unitSpawn。SelfCheck(MoeHero 专属)不在此模块
6. **system-entity-component** — 通用 RPG 实体层(DamageSystem/BuffSystem/SkillSystem 等 + AuraObj/BuffObj/EffectObj/SkillObj + 6 通用组件 + Restriction 控制类)。依赖脚手架核心(ticket 04)

### 默认行为

**默认全装**:用户未指定排除时,拷贝所有可选模块。

### 排除机制

用户可通过以下方式排除模块:

**方式 1:命令参数**
```
/war3-import-framework --exclude http,fonts
```

**方式 2:交互式确认**
改动预览阶段询问用户:
```
可选模块(默认全装,输入要排除的模块名,多个用逗号分隔,回车跳过):
  - http: HTTP/远程数据(socket.dll + libwinpthread-1.dll + 6 个 lua)
  - fonts: 中文字体(fonts.ttf)
  - brand: wenhao_plugin.tga(改名 YDWE 插件 dll)→ resource/
  - dzapi: DzApi 平台接口(dzapi.lua)
  - util: 通用工具集(9 个 lua):EventPool/fourcc/textTag/destroyTextTagDelayed/rushSlide/unitAlive/unitGetItemOfType/unitHasItem/unitSpawn
  - system-entity-component: 通用 RPG 实体层(System/Entity/Component,依赖脚手架核心)

排除: [等待用户输入]
```

### 排除时的处理逻辑

**HTTP 模块特殊处理**:
- 排除 HTTP 时,**不拷贝** `socket.dll` / `libwinpthread-1.dll` / 6 个 lua 文件
- 若目标 `script/lib/util/` 已存在这些 lua 文件,**保留不删除**(用户可能手动依赖)
- 在报告中标注:"HTTP 模块已排除,目标已存在的 HTTP lua 文件未删除,如不再需要请手动移除"

**其他模块**:
- fonts:不拷贝 `fonts.ttf`
- brand:不拷贝 wenhao_plugin.tga
- dzapi:不拷贝 `dzapi.lua`,已存在则保留

### 拷贝步骤

按 `assets/optional-modules.json` 的 `modules` 定义,对每个未排除的模块:

1. 遍历 `files` 数组
2. 对每个文件:
   - `type: "binary"` → 从 `assets/<src>` 拷贝到目标 `<workspaceRoot>/map/<dest>`
   - `type: "lua"` → 从 `assets/<src>` 拷贝到目标 `<workspaceRoot>/map/<dest>`
3. 冲突策略:
   - `binary` — **存在则跳过**(assets 定义)
   - `lua` — **存在则覆盖**(框架层权威)

### 关键约束

**二进制 dll 位置**:
- `socket.dll` / `libwinpthread-1.dll` **必须**放目标 `map/`(与 `map/war3map.j` 同级)
- **不能**放 `script/` 下,否则 HTTP/socket 静默失效(ticket 01 运行层卡住根因之一)
- `fonts.ttf` 同理,放 `map/`

## 工具链捆绑

插件捆绑了完整的 w3x2lni 工具链(见 ADR-0002 修订 + ADR-0004 自包含),导入时拷到目标 `tools/`(项目根,非 map/ 内),让目标无需另备 w2l 即可自编译。

### 捆绑内容

从插件 `assets/tools/` 拷到目标 `<workspaceRoot>/tools/`(项目根,map 外):

| 源(插件 assets/tools/) | 目标(目标项目) | 说明 |
|---|---|---|
| `w3x2lni/` | `tools/w3x2lni/` | w2l.exe + bin/ + config.ini + data/ + script/ + template/ |
| `jasshelper/` | `tools/jasshelper/` | 4 exe + sfmpq.dll + blizzard.j + common.j + jasshelper.conf |
| `rsa/` | `tools/rsa/` | lua + dll + pub(签名用) |
| `filewatch.dll` | `tools/filewatch.dll` | 语法检查监听 |
| `运行.lua` | `tools/运行.lua` | YDWE 启动脚本 |
| `语法检查.lua` | `tools/语法检查.lua` | 语法检查脚本 |
| `配置.lua` | `tools/配置.lua` | 配置脚本 |
| `ydwe.lua` | `tools/ydwe.lua` | YDWE 配置 |

### 冲突策略

- **目标 `tools/` 已存在**:
  - 若已含 `w3x2lni/w2l.exe` → **跳过**(用户可能已自定义或升级)
  - 若不含 → **全量拷贝**
- **部分存在**:按文件粒度跳过已存在的(避免覆盖用户定制)

### 拷贝步骤

1. 检查目标 `<workspaceRoot>/tools/w3x2lni/w2l.exe` 是否存在
2. 若存在 → 报告"目标已有 tools/,跳过工具链拷贝(用户可手动删除后重导)"
3. 若不存在 → 从 `assets/tools/` 全量拷到 `<workspaceRoot>/tools/`
4. 报告拷贝的文件清单 + 大小

### 关键约束

**工具链位置**:
- **必须**放目标 `<workspaceRoot>/tools/`(项目根,与 `map/` 平级,**不**在 map/ 内)
- **不能**放 `map/tools/` 或 `script/` 下,否则路径引用失败(运行.lua/语法检查.lua 硬编码 `tools/` 相对路径,VS Code tasks.json 用 `${workspaceRoot}/tools/`)
- `w3x2lni/config.ini` 含通用配置(无项目特定路径),可直接用

## VS Code 配置捆绑

插件捆绑了 VS Code 配置(extensions.json/launch.json/settings.json/tasks.json),导入时拷到目标 `.vscode/`(项目根,非 map/ 内),让目标开箱即用 VS Code 任务。

### 捆绑内容

从插件 `assets/.vscode/` 拷到目标 `<workspaceRoot>/.vscode/`(项目根,map 外):

| 源(插件 assets/.vscode/) | 目标(目标项目) | 说明 |
|---|---|---|
| `extensions.json` | `.vscode/extensions.json` | 推荐扩展(lua-debug/中文语言包/tasks) |
| `launch.json` | `.vscode/launch.json` | Lua 调试配置(attach 4279 端口) |
| `settings.json` | `.vscode/settings.json` | Lua diagnostics 全局变量(ac/fs/base/war3) |
| `tasks.json` | `.vscode/tasks.json` | VS Code 任务(运行/语法检查/Obj/Lni/Slk/🔍 watch) |

### 清洗 MoeHero 硬编码

`assets/.vscode/tasks.json` 已清洗 MoeHero 硬编码:
- `MoeHero.w3x` → `<地图名>.w3x`(参数化占位符,用户导入后按实际地图名替换)
- `运行.lua` 已参数化(扫 `${workspaceRoot}` 下 `*.w3x`,无需硬编码)
- `Obj`/`Lni`/`Slk` 任务用 `for /f %f in ('dir /b *.w3x')` 自动发现

**导入后提示**:
- 若 `.vscode/tasks.json` 中仍有 `<地图名>.w3x` 占位符,提示用户替换为实际地图名(如 `MoeHero.w3x`)
- 或保持占位符,运行.lua 会自动发现第一个 `.w3x`

### 冲突策略

- **目标 `.vscode/` 已存在**:
  - 若已含 `tasks.json` → **跳过**(用户可能已自定义任务)
  - 若不含 → **全量拷贝**
- **部分存在**:按文件粒度跳过已存在的(避免覆盖用户定制)

### 拷贝步骤

1. 检查目标 `<workspaceRoot>/.vscode/tasks.json` 是否存在
2. 若存在 → 报告"目标已有 .vscode/,跳过 VS Code 配置拷贝(用户可手动删除后重导)"
3. 若不存在 → 从 `assets/.vscode/` 全量拷到 `<workspaceRoot>/.vscode/`
4. 报告拷贝的文件清单

### 关键约束

**VS Code 配置位置**:
- **必须**放目标 `<workspaceRoot>/.vscode/`(项目根,与 `map/` 平级,**不**在 map/ 内)
- **不能**放 `map/.vscode/`,否则 VS Code 无法识别任务
- tasks.json 中 `${workspaceRoot}` 由 VS Code 自动解析为项目根

## 校验

导入后执行校验。**根据基线类型分两档校验**:

### 导入后报告模板(部分框架地图)

**导入完成后必须输出逐文件状态报告，与实际处理一致**:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
导入完成报告
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

目标项目:<workspaceRoot>
基线类型:YDWE-Lua / 纯 JASS
部分框架状态:<状态名>

【注入】
  map/war3map.j — [已注入 initializePlugin] / [保持不变(YDWE-Lua 基线)]

【拷贝】
  map/plugin_main.lua — [已新建] / [已合并:追加 require 'script']
  map/path.lua — [已新建] / [已覆盖(框架权威)]
  map/script/init.lua — [已新建] / [已合并:追加 require('script.lib') + require('script.src')]
  map/script/lib/* — 已拷贝 <N> 文件(框架权威)
  map/callback — [已新建] / [已存在,跳过]
  map/(key) — [已新建] / [已存在,跳过]
  map/socket.dll — [已拷贝] / [已存在,跳过]
  map/libwinpthread-1.dll — [已拷贝] / [已存在,跳过]
  map/fonts.ttf — [已拷贝] / [已存在,跳过]

【跳过】
  map/script/src/init.lua — [已存在,跳过(目标定制)] / [已新建脚手架]
  map/script/src/core/ — [已存在,跳过整个目录] / [已新建脚手架]
  map/script/src/entities/ — [已存在,跳过] / [已新建]
  map/script/src/components/ — [已存在,跳过] / [已新建]
  map/script/src/systems/ — [已存在,跳过] / [已新建]
  tools/ — [已存在,跳过] / [已拷贝]
  .vscode/ — [已存在,跳过] / [已拷贝]

【合并】
  map/plugin_main.lua — [已追加 require 'script' 引导] / [已含引导,跳过合并]
  map/script/init.lua — [已追加 require('script.lib') + require('script.src')] / [已含引导,跳过合并]

【保留的目标自定义文件】
  map/script/lib/<自定义文件> — 保留(框架不包含,未删除)
  (若无则标注"无")

【统计】
  注入:1 文件(map/war3map.j) / 0 文件(YDWE-Lua 基线)
  拷贝:<N> 文件
  跳过:<M> 文件(目标已有)
  合并:<K> 文件(入口追加引导)

【后续步骤】
  1. 用 w2l.exe slk <workspaceRoot> 编译地图
  2. 用 YDWE 启动测试
  3. inspect 读 _G.__framework_booted == true 或 _G.__framework_scaffold_loaded == true 应为真

⚠ 若目标 map/plugin_main.lua 有特殊定制(如 japi.SetOwner / 自定义 console),
  框架追加的引导逻辑在文件末尾,不影响现有逻辑。
  若启动后框架未加载,检查 xpcall 错误输出。
```

**报告必须与实际处理一致**:
- 报告"已跳过"的文件必须实际未修改
- 报告"已覆盖"的文件必须实际被框架版本替换
- 报告"已合并"的文件必须实际追加了引导逻辑(在末尾)
- 报告"保留的目标自定义文件"必须实际未删除

### 导入后 Lua 语法校验(两档通用,必做)

**导入完成、让用户编译启动前,必须对所有拷进去的 .lua 做语法检查,避免带语法炸弹进游戏**(如 `:` 方法引用误用导致 `function arguments expected`,地图直接起不来)。这是运行层兜底:不管提炼/sync 是否引入语法错,导入后立刻验,有错当场拦。

判定工具:用目标项目的 Lua 解释器对 `map/script/` 下每个 .lua 跑 `loadfile`(只解析语法不执行,不需框架依赖):

```bash
# 优先用 tools 模块的解释器;用户没选 tools 模块则找目标项目任意 lua5.x/luajit
LUA="<workspaceRoot>/tools/w3x2lni/bin/w3x2lni-lua.exe"
[ -f "$LUA" ] || LUA=$(which lua 2>/dev/null) || LUA=$(which luajit 2>/dev/null)
ROOT="<workspaceRoot>/map/script"
# git bash 路径 /c/ -> C:/ (Lua loadfile 用 Windows 路径)
files=$(find "$ROOT" -name '*.lua' | sed 's|^/\([a-zA-Z]\)/|\1:/|')
"$LUA" -e "
local errs = 0
for i = 1, #arg do
  local fn, err = loadfile(arg[i])
  if not fn then errs = errs + 1; print('SYNTAX ERR: ' .. arg[i] .. '\n  => ' .. err) end
end
print(string.format('=== %d 文件, %d 语法错误 ===', #arg, errs))
os.exit(errs > 0 and 1 or 0)
" $files
```

- **任一语法错 → 报错停止,列文件名+行号+错误信息,不输出"导入完成报告"的成功分支**。修好或回报插件维护者后再重导。绝不让用户带着语法炸弹进 YDWE 启动。
- **常见根因**:`obj:method` 是方法调用语法,必须 `obj:method(args)` 紧跟参数;单独取方法引用要用点号 `obj.method`。写成 `if x and obj:method and ...` 会报 `function arguments expected near 'and'`(冒号后期待参数,却遇关键字)。lib/ 原样拷自源项目已实跑验证,语法错几乎只在人工提炼的 src/。
- **解释器兜底**:目标项目无任何 lua 解释器、用户也没选 tools 模块 → 提示用户选 tools 模块重导(它含 w3x2lni-lua.exe),或本地装 lua。
- **Lua 版本注记**:w3x2lni-lua.exe 可能是 Lua 5.4,War3 运行时是 LuaJIT(5.1)。5.4 拒绝某些 LuaJIT 合法写法(lib/ 偶见位运算 `//`/`~`)会对 lib/ 误报;人工提炼的 src/ 是纯 5.1 语法,5.4 通过即 LuaJIT 通过。若 lib/ 报错而该文件是源项目原样拷、本就跑得通 → 标为"已知 5.4 误报,非真实错误",不阻断。

校验通过才进下两档的基线静态校验,并在导入报告【统计】标注 `Lua 语法校验:通过(N 文件)`。

### YDWE-Lua 基线校验

1. **静态校验**
   - `grep -nE "^function[[:space:]]+initializePlugin[[:space:]]+takes" map/war3map.j` 应有结果(目标原有,未删除)
   - `grep -nE 'AbilityId\("exec-lua:plugin_main"\)' map/war3map.j` 应有结果(目标原有,未删除)
   - `map/war3map.j` 文件 hash 应与导入前一致(未修改)
   - 目标项目应存在 `map/plugin_main.lua` / `map/path.lua` / `map/script/init.lua` / `map/script/src/init.lua` / `map/script/lib/` / `map/callback` / `map/(key)` / `tools/` / `.vscode/`
   - `map/plugin_main.lua` 应含 `require 'script'` 引导(若合并则追加在末尾)
   - `map/script/init.lua` 应含 `require('script.lib')` + `require('script.src')`(若合并则追加在末尾)
   - `map/path.lua` 不应含 `D:\war3项目` 硬编码
   - `map/script/src/init.lua` 应含 `_G.__framework_scaffold_loaded = true`(脚手架)或 `_G.__framework_booted = true`(极简)

2. **报告**
   - 列出所有新增 / 修改的文件
   - 明确标注:"map/war3map.j 保持不变(YDWE-Lua 基线)"
   - 提示用户用 `w2l.exe slk <workspaceRoot>` 编译,再用 YDWE 启动
   - 启动后 inspect 读 `_G.__framework_booted == true` 或 `_G.__framework_scaffold_loaded == true` 应为真

### 纯 JASS 基线校验

1. **静态校验**
   - `grep -nE "^function[[:space:]]+initializePlugin[[:space:]]+takes" map/war3map.j` 应有结果(新注入)
   - `grep -nE "call[[:space:]]+initializePlugin\(\)" map/war3map.j` 应有结果(新注入,在 main 内)
   - 目标项目应存在 `map/plugin_main.lua` / `map/path.lua` / `map/script/init.lua` / `map/script/src/init.lua` / `map/script/lib/` / `map/callback` / `map/(key)` / `tools/` / `.vscode/`
   - `map/script/src/init.lua` 应含 `_G.__framework_scaffold_loaded = true`(脚手架)或 `_G.__framework_booted = true`(极简)
   - `map/path.lua` 不应含 `D:\war3项目` 硬编码
   - `map/script/init.lua` 不应含 `test_runner` / `test_reporter`

2. **报告**
   - 列出所有新增 / 修改的文件
   - 明确标注:"map/war3map.j 已注入 initializePlugin(纯 JASS 基线)"
   - 提示用户用 `w2l.exe slk <workspaceRoot>` 编译,再用 YDWE 启动
   - 启动后 inspect 读 `_G.__framework_booted == true` 或 `_G.__framework_scaffold_loaded == true` 应为真

## 错误处理

- 目标非 lni 格式 → 提示先解包
- 目标 main 缺 InitBlizzard → 报错停止
- 注入过程中断 → 提示用户从备份恢复(导入前应建议用户备份)
- lib/ 拷贝失败 → 报错并列出缺失文件

## 不在本票范围

- 完整脚手架 src/(Game 循环 / State / Selector / GameEvent / UnitNumeric)→ ticket 04
- sync 脚本(从 rouge_lua 同步框架更新)→ 后续票
