-- states/ExampleBattle.lua — 示例战斗状态（教学用途）
-- 设计目的：展示如何用脚手架核心（Game/State/GameEvent/Selector/UnitNumeric）组织一个游戏状态
-- 作者可照此模式写自己的 Battle/Menu/Lobby 等状态
--
-- 【关键概念】
-- 1. State 基类：所有游戏状态继承 core/state.lua，实现 OnGameUpdate(dt)
-- 2. Game 循环：固定帧率 20ms/50fps，每帧调用当前 State 的 OnGameUpdate
-- 3. GameEvent：ECS 事件系统，通过 eventManager:fireEvent 派发
-- 4. Selector：范围/直线选择器，用于选取范围内单位
-- 5. UnitNumeric：数值机制，按 UnitModuleType 分组累加属性
--
-- 【加载方式】
-- 本文件不自动加载（不进入 src/init.lua 主链），用户按需 require：
--   require 'src.states.ExampleBattle'
-- 然后在启动逻辑中：
--   Game.setState(ExampleBattle())

-- ========== 1. 继承 State 基类 ==========
-- 用法：class("状态名", State) 创建子类
-- 说明：State 提供 OnGameUpdate/update/draw/load 等生命周期方法
local ExampleBattle = class("ExampleBattle", State)

-- ========== 2. initialize：状态初始化 ==========
-- 用法：在构造时初始化 engine、eventManager、游戏数据等
-- 说明：这是展示初始化逻辑的示例，作者按需添加自己的字段
function ExampleBattle:initialize()
    -- 调用父类初始化（State:initialize 为空，但保留调用习惯）
    State.initialize(self)

    -- 创建 ECS 引擎和事件管理器
    -- 说明：Engine 管理实体和系统，EventManager 管理事件监听
    -- 注意：Engine/EventManager 来自 lib/ecs/（框架层），非 MoeHero 专属
    self.engine = Engine(EventManager())
    self.eventManager = self.engine.eventManager

    -- 示例游戏数据（作者按需扩展）
    self.gameData = {
        score = 0,              -- 示例：游戏得分
        killCount = 0,          -- 示例：击杀计数
        startTime = Game.Elapsed, -- 记录状态开始时间
    }

    -- 注册事件监听（展示 GameEvent 用法）
    self:registerEvents()

    print("[ExampleBattle] 状态初始化完成")
end

-- ========== 3. registerEvents：注册事件监听 ==========
-- 用法：eventManager:addListener(事件类名, 监听者, 回调函数)
-- 说明：展示如何监听 AnyUnitDeath/AnyUnitDamaged 等事件
function ExampleBattle:registerEvents()
    -- 监听任意单位死亡事件
    -- 参数说明：
    --   "AnyUnitDeath" - 事件类名（字符串，对应 GameEvent.lua 中的类）
    --   self - 监听者（通常是状态自身，回调时作为 self 传入）
    --   function(self, event) - 回调函数，event.info 存储事件参数
    self.eventManager:addListener("AnyUnitDeath", self, function(self, event)
        -- event.info 是事件构造时传入的参数表
        -- AnyUnitDeath(killingUnit, dyingUnit) → event.info = {killingUnit, dyingUnit}
        local killingUnit = event.info[1]
        local dyingUnit = event.info[2]

        -- 示例逻辑：击杀计数 +1，得分 +100
        self.gameData.killCount = self.gameData.killCount + 1
        self.gameData.score = self.gameData.score + 100

        print(string.format("[ExampleBattle] 单位死亡：%s 击杀了 %s（得分：%d）",
            tostring(killingUnit), tostring(dyingUnit), self.gameData.score))
    end)

    -- 监听任意单位伤害事件（展示另一个事件）
    self.eventManager:addListener("AnyUnitDamaged", self, function(self, event)
        -- AnyUnitDamaged(attackUnit, defUnit, damage)
        local attackUnit = event.info[1]
        local defUnit = event.info[2]
        local damage = event.info[3]

        -- 示例逻辑：打印伤害信息（作者可在此实现伤害显示、吸血等）
        if damage > 0 then
            print(string.format("[ExampleBattle] 伤害事件：%s 对 %s 造成 %.1f 伤害",
                tostring(attackUnit), tostring(defUnit), damage))
        end
    end)
end

-- ========== 4. OnGameUpdate：每帧逻辑 ==========
-- 用法：返回 true 继续状态，返回 false 结束状态（Game 循环会清空 mCurrentState）
-- 说明：这是展示 Game 循环 + Selector + UnitNumeric 用法的核心方法
function ExampleBattle:OnGameUpdate(dt)
    -- dt = Game.DeltaTime = 0.02（20ms/50fps）
    -- Game.Elapsed 是从游戏启动到现在的累计时间

    -- 示例 1：使用 Game.Elapsed 判断游戏时间
    -- 说明：作者可用此实现倒计时、阶段切换等
    local elapsed = Game.Elapsed - self.gameData.startTime
    if elapsed >= 60 and not self.gameData.phase2Triggered then
        -- 示例：60 秒后进入第二阶段
        self.gameData.phase2Triggered = true
        print("[ExampleBattle] 进入第二阶段！")
    end

    -- 示例 2：使用 Selector 进行范围选择
    -- 说明：Selector 用于选取范围内单位（AOE 技能、光环等）
    -- 注意：Selector 需要 Game.curState().engine 存在，且实体有 getPoint() 方法
    if self.gameData.phase2Triggered then
        self:exampleSelectorUsage()
    end

    -- 示例 3：使用 UnitNumeric 管理数值
    -- 说明：UnitNumeric 按 UnitModuleType 分组累加属性（Base/Equip/Skill/Rate 等）
    -- 注意：UnitNumeric 通常挂载在实体上（如 unit.numeric），此处仅展示用法
    self:exampleUnitNumericUsage()

    -- 示例 4：调用 engine:update(dt) 驱动所有 System
    -- 说明：Engine:update 会遍历所有注册的 System 并调用 system:update(dt)
    -- 注意：System 是用户自定义的（如 DamageSystem、HeroSystem），脚手架不包含
    self.engine:update(dt)

    -- 返回 true 继续状态，返回 false 结束状态
    -- 示例：按 Esc 键结束状态（作者可自定义结束条件）
    return not self.gameData.shouldExit
end

-- ========== 5. exampleSelectorUsage：展示 Selector 用法 ==========
-- 说明：Selector 提供 inRange（圆形范围）和 inLine（直线范围）两种选择
function ExampleBattle:exampleSelectorUsage()
    -- 获取所有带 UnitModelComp 组件的实体（单位实体）
    -- 说明：UnitModelComp 是标记组件，标识"这是一个单位实体"
    local heroEntity = self:getExampleHero()
    if not heroEntity then return end

    -- 示例 A：圆形范围选择（AOE 技能）
    -- 用法：Selector():inRange(中心点, 半径, 组件列表, 回调)
    -- 说明：
    --   - 中心点可以是 entity（自动调用 getPoint()）或 point
    --   - 半径是数值（如 500）
    --   - 组件列表用于过滤（如 {UnitModelComp} 表示只选单位）
    --   - 回调返回 true 中断遍历
    local selector = Selector()
    selector:inRange(heroEntity, 500, {UnitModelComp}, function(target)
        -- 示例逻辑：对范围内敌人造成伤害
        if target:getTeam() ~= heroEntity:getTeam() then
            print(string.format("[ExampleBattle] AOE 选中目标：%s", tostring(target)))
            -- 实际用法：target:takeDamage(heroEntity, 100)
        end
        return false -- 返回 false 继续遍历，返回 true 中断
    end)

    -- 示例 B：直线范围选择（直线技能）
    -- 用法：Selector():inLine(起点, 方向, 最大距离, 宽度, 回调, 组件列表)
    -- 说明：
    --   - 起点可以是 entity 或 point
    --   - 方向是 Vector3（会自动归一化）
    --   - 宽度和最大距离是数值
    local direction = Types.point(1, 0, 0) -- 示例：X 轴正方向
    selector:inLine(heroEntity, direction, 800, 200, function(target)
        if target:getTeam() ~= heroEntity:getTeam() then
            print(string.format("[ExampleBattle] 直线选中目标：%s", tostring(target)))
        end
        return false
    end, {UnitModelComp})
end

-- ========== 6. exampleUnitNumericUsage：展示 UnitNumeric 用法 ==========
-- 说明：UnitNumeric 用于管理单位属性（攻击/护甲/攻速等），支持多模块累加
function ExampleBattle:exampleUnitNumericUsage()
    -- 示例：创建一个 UnitNumericMap 管理多个属性
    -- 说明：UnitNumericMap 是属性集合，每个属性类型对应一个 UnitNumeric
    local vm = {} -- 示例：视图模型（实际用法中由实体管理）
    local numericMap = UnitNumericMap(vm)

    -- 设置基础攻击（Base 模块）
    -- 用法：numericMap:get(属性名):set(UnitModuleType, 值)
    -- 说明：UnitModuleType 包括 Base/Job/Level/Equip/Decorator/Skill/Rate/Other
    local attack = numericMap:get("攻击")
    attack:set(ENUM.UnitModuleType.Base, 100) -- 基础攻击 100
    attack:set(ENUM.UnitModuleType.Equip, 50) -- 装备加成 50
    attack:set(ENUM.UnitModuleType.Rate, 20)  -- 百分比加成 20%

    -- 读取总攻击值
    -- 公式：sum(flat) * (1 + Rate/100) + Other
    -- 示例：(100 + 50) * (1 + 20/100) = 180
    local totalAttack = attack:get()
    print(string.format("[ExampleBattle] 总攻击：%.1f", totalAttack))

    -- 读取特定模块值
    local baseAttack = attack:get(ENUM.UnitModuleType.Base)
    print(string.format("[ExampleBattle] 基础攻击：%.1f", baseAttack))
end

-- ========== 7. 辅助方法 ==========

-- 获取示例英雄（实际用法中由用户实现）
function ExampleBattle:getExampleHero()
    -- 示例：从 engine 中获取第一个带 UnitModelComp 的实体
    local entities = self.engine:getEntitiesWithComponent(UnitModelComp)
    for _, entity in pairs(entities) do
        return entity -- 返回第一个实体作为示例
    end
    return nil
end

-- ========== 8. 其他生命周期方法（可选） ==========

-- load：加载资源（如创建单位、初始化地图）
-- 说明：在 setState 后、首次 OnGameUpdate 前调用
function ExampleBattle:load()
    print("[ExampleBattle] 加载资源...")
    -- 示例：创建玩家和单位
    -- local player = AssetsManager.singleton:createPlayer(1)
    -- local hero = AssetsManager.singleton:createUnitAtPos('H001', player, 0, 0, 0)
end

-- update：备用更新方法（通常用 OnGameUpdate）
-- 说明：State 基类提供 update/draw 桩，作者按需实现
function ExampleBattle:update(dt)
    -- 通常不需要实现，逻辑放在 OnGameUpdate
end

-- draw：绘制逻辑（如 UI）
-- 说明：在 Engine:draw() 中调用
function ExampleBattle:draw()
    -- 示例：绘制 UI（实际用法中由 UI 系统管理）
end

-- 返回状态类
return ExampleBattle
