-- ============================================================================
-- jass_mock.lua - jass 原生函数 mock 表（war3-tester 插件内置）
-- ============================================================================
-- 功能：stub 高频 jass 函数，返回假 handle（用 table 模拟 lightuserdata），
--       记录调用日志供断言。让含 jass 调用的纯逻辑在游戏内测试时不真创单位。
--
-- 使用方式（require 路径取决于项目配置的 test_module_prefix）：
--   local jmock = require('<your_test_module_prefix>_war3_tester.jass_mock')
--   jmock.install()  -- 安装 mock 到全局环境
--   -- 之后代码调用 CreateUnit 等会走 mock
--   jmock.calls('CreateUnit')  -- 查看调用日志
--   jmock.reset()              -- 清空调用日志
--   jmock.uninstall()          -- 恢复原始全局函数
--
-- 假 handle 约定：
--   每个 mock 返回的 handle 是 table，含 _mock_type / _mock_id 字段，
--   便于断言识别。不同 mock 函数返回的 handle 类型不同。
--
-- mock 范围基于 wzns 项目高频 jass 调用统计（2026-07-13）：
--   高频(>30): Player(102), DisplayTextToPlayer(49), GetUnitTypeId(45),
--              CreateTrigger(42), CreateGroup(33), ForGroup(31)
--   中频(10-30): RemoveUnit(20), GetUnitX/Y(19), GetTriggerUnit(16),
--                GetLocalPlayer(13), SetUnitState(12)
--   低频(1-9): GetUnitState(9), SetUnitX/Y(5), UnitAddAbility/RemoveAbility(4),
--              IssuePointOrder/TargetOrder(3), IssueImmediateOrder(2),
--              KillUnit(1), GetOwningPlayer(1)
-- 零调用（不 mock）：定时器原生、随机数原生、IsUnitAlive/Dead、
--                    游戏缓存、BlzGetLocalPlayer、GroupAddUnit、
--                    GetRectCenter/RemoveRect/CameraSetup
-- ============================================================================

local JassMock = {}

-- 内部状态
local _installed = false
local _originals = {}   -- 保存原始全局函数，uninstall 时恢复
local _call_log = {}    -- func_name -> [{args={...}, ret=handle, time=os.clock()}, ...]
local _handle_counter = 0

--- 生成唯一假 handle（table 模拟 lightuserdata）
---@param mock_type string handle 类型标识（如 'unit', 'trigger', 'player'）
---@param extra table|nil 额外字段（如 unitTypeId 等）
---@return table handle 假 handle
local function make_handle(mock_type, extra)
    _handle_counter = _handle_counter + 1
    local h = {
        _mock_type = mock_type,
        _mock_id = _handle_counter,
        _mock_alive = true,
    }
    if extra then
        for k, v in pairs(extra) do
            h[k] = v
        end
    end
    return h
end

--- 记录调用日志
local function log_call(func_name, args, ret)
    if not _call_log[func_name] then
        _call_log[func_name] = {}
    end
    table.insert(_call_log[func_name], {
        args = args,
        ret = ret,
        time = os.clock(),
    })
end

-- ============================================================================
-- Mock 函数定义
-- ============================================================================
-- 对照 wzns 高频 jass 调用确定 mock 范围。
-- 函数签名尽量对齐 jass 原生参数顺序。
-- 不确定的标 TODO: 验证。

local mock_functions = {}

-- --------------------------------------------------------------------------
-- 高频（>30 调用）
-- --------------------------------------------------------------------------

--- Player - 返回假 player handle
---@param playerId integer 玩家 ID（0-27）
function mock_functions.Player(playerId)
    local h = make_handle('player', { playerId = playerId })
    log_call('Player', { playerId }, h)
    return h
end

--- DisplayTextToPlayer - 显示文本给玩家（mock 只记录日志）
---@param toPlayer table player handle
---@param x number X 坐标（屏幕位置）
---@param y number Y 坐标
---@param message string 消息文本
function mock_functions.DisplayTextToPlayer(toPlayer, x, y, message)
    log_call('DisplayTextToPlayer', { toPlayer, x, y, message }, nil)
end

--- GetUnitTypeId - 返回 unit 的类型 ID
---@param whichUnit table unit handle
function mock_functions.GetUnitTypeId(whichUnit)
    log_call('GetUnitTypeId', { whichUnit }, whichUnit and whichUnit.unitTypeId)
    if type(whichUnit) == 'table' and whichUnit._mock_type == 'unit' then
        return whichUnit.unitTypeId or 0
    end
    return 0  -- TODO: 验证 - 非 mock handle 时返回 0 是否合理
end

--- CreateTrigger - 返回假 trigger handle
function mock_functions.CreateTrigger()
    local h = make_handle('trigger')
    log_call('CreateTrigger', {}, h)
    return h
end

--- DestroyTrigger - 销毁 trigger
---@param whichTrigger table trigger handle
function mock_functions.DestroyTrigger(whichTrigger)
    if type(whichTrigger) == 'table' then
        whichTrigger._mock_alive = false
    end
    log_call('DestroyTrigger', { whichTrigger }, nil)
end

--- CreateGroup - 返回假 group handle
function mock_functions.CreateGroup()
    local h = make_handle('group', { units = {} })
    log_call('CreateGroup', {}, h)
    return h
end

--- ForGroup - 对 group 中每个 unit 执行回调（mock 遍历 group.units）
---@param whichGroup table group handle
---@param callback function 回调函数
function mock_functions.ForGroup(whichGroup, callback)
    if type(whichGroup) == 'table' and whichGroup._mock_type == 'group' then
        for _, u in ipairs(whichGroup.units) do
            -- jass 原生 ForGroup 通过 GetEnumUnit() 获取当前单位
            -- mock 简化：直接传 unit 给 callback（TODO: 验证是否需模拟 GetEnumUnit）
            if type(callback) == 'function' then
                callback(u)
            end
        end
    end
    log_call('ForGroup', { whichGroup, callback }, nil)
end

-- --------------------------------------------------------------------------
-- 中频（10-30 调用）
-- --------------------------------------------------------------------------

--- RemoveUnit - 移除 unit
---@param whichUnit table unit handle
function mock_functions.RemoveUnit(whichUnit)
    if type(whichUnit) == 'table' then
        whichUnit._mock_alive = false
    end
    log_call('RemoveUnit', { whichUnit }, nil)
end

--- GetUnitX - 获取 unit X 坐标
---@param whichUnit table unit handle
function mock_functions.GetUnitX(whichUnit)
    local x = 0
    if type(whichUnit) == 'table' and whichUnit._mock_type == 'unit' then
        x = whichUnit.x or 0
    end
    log_call('GetUnitX', { whichUnit }, x)
    return x
end

--- GetUnitY - 获取 unit Y 坐标
---@param whichUnit table unit handle
function mock_functions.GetUnitY(whichUnit)
    local y = 0
    if type(whichUnit) == 'table' and whichUnit._mock_type == 'unit' then
        y = whichUnit.y or 0
    end
    log_call('GetUnitY', { whichUnit }, y)
    return y
end

--- GetTriggerUnit - 返回触发器单位（mock 返回 nil，需测试自行设置）
function mock_functions.GetTriggerUnit()
    log_call('GetTriggerUnit', {}, nil)
    return nil  -- TODO: 验证 - 测试中通常需 mock 设置返回值
end

--- GetLocalPlayer - 返回本地玩家
function mock_functions.GetLocalPlayer()
    local h = make_handle('player', { playerId = 0 })
    log_call('GetLocalPlayer', {}, h)
    return h
end

--- SetUnitState - 设置 unit 状态（如生命值、魔法值）
---@param whichUnit table unit handle
---@param whichState integer 状态类型 ID
---@param value number 新值
function mock_functions.SetUnitState(whichUnit, whichState, value)
    if type(whichUnit) == 'table' and whichUnit._mock_type == 'unit' then
        if not whichUnit.states then whichUnit.states = {} end
        whichUnit.states[whichState] = value
    end
    log_call('SetUnitState', { whichUnit, whichState, value }, nil)
end

-- --------------------------------------------------------------------------
-- 低频（1-9 调用）
-- --------------------------------------------------------------------------

--- GetUnitState - 获取 unit 状态
---@param whichUnit table unit handle
---@param whichState integer 状态类型 ID
function mock_functions.GetUnitState(whichUnit, whichState)
    local val = 0
    if type(whichUnit) == 'table' and whichUnit._mock_type == 'unit' then
        val = (whichUnit.states and whichUnit.states[whichState]) or 0
    end
    log_call('GetUnitState', { whichUnit, whichState }, val)
    return val
end

--- SetUnitX - 设置 unit X 坐标
---@param whichUnit table unit handle
---@param x number X 坐标
function mock_functions.SetUnitX(whichUnit, x)
    if type(whichUnit) == 'table' and whichUnit._mock_type == 'unit' then
        whichUnit.x = x
    end
    log_call('SetUnitX', { whichUnit, x }, nil)
end

--- SetUnitY - 设置 unit Y 坐标
---@param whichUnit table unit handle
---@param y number Y 坐标
function mock_functions.SetUnitY(whichUnit, y)
    if type(whichUnit) == 'table' and whichUnit._mock_type == 'unit' then
        whichUnit.y = y
    end
    log_call('SetUnitY', { whichUnit, y }, nil)
end

--- UnitAddAbility - 给 unit 添加技能
---@param whichUnit table unit handle
---@param abilityId integer|string 技能 ID
function mock_functions.UnitAddAbility(whichUnit, abilityId)
    if type(whichUnit) == 'table' and whichUnit._mock_type == 'unit' then
        if not whichUnit.abilities then whichUnit.abilities = {} end
        table.insert(whichUnit.abilities, abilityId)
    end
    log_call('UnitAddAbility', { whichUnit, abilityId }, nil)
end

--- UnitRemoveAbility - 从 unit 移除技能
---@param whichUnit table unit handle
---@param abilityId integer|string 技能 ID
function mock_functions.UnitRemoveAbility(whichUnit, abilityId)
    if type(whichUnit) == 'table' and whichUnit._mock_type == 'unit' then
        if whichUnit.abilities then
            for i = #whichUnit.abilities, 1, -1 do
                if whichUnit.abilities[i] == abilityId then
                    table.remove(whichUnit.abilities, i)
                    break
                end
            end
        end
    end
    log_call('UnitRemoveAbility', { whichUnit, abilityId }, nil)
end

--- IssuePointOrder - 发布点到点命令
---@param whichUnit table unit handle
---@param order string 命令字符串
---@param x number X 坐标
---@param y number Y 坐标
function mock_functions.IssuePointOrder(whichUnit, order, x, y)
    log_call('IssuePointOrder', { whichUnit, order, x, y }, nil)
end

--- IssueTargetOrder - 发布目标命令
---@param whichUnit table unit handle
---@param order string 命令字符串
---@param target table 目标 handle
function mock_functions.IssueTargetOrder(whichUnit, order, target)
    log_call('IssueTargetOrder', { whichUnit, order, target }, nil)
end

--- IssueImmediateOrder - 发布立即命令
---@param whichUnit table unit handle
---@param order string 命令字符串
function mock_functions.IssueImmediateOrder(whichUnit, order)
    log_call('IssueImmediateOrder', { whichUnit, order }, nil)
end

--- KillUnit - 杀死 unit
---@param whichUnit table unit handle
function mock_functions.KillUnit(whichUnit)
    if type(whichUnit) == 'table' then
        whichUnit._mock_alive = false
    end
    log_call('KillUnit', { whichUnit }, nil)
end

--- GetOwningPlayer - 返回 unit 的所有者
---@param whichUnit table unit handle
function mock_functions.GetOwningPlayer(whichUnit)
    local owner = nil
    if type(whichUnit) == 'table' and whichUnit._mock_type == 'unit' then
        owner = whichUnit.owner
    end
    log_call('GetOwningPlayer', { whichUnit }, owner)
    return owner
end

--- CreateUnit - 返回假 unit handle
---@param idPlayer table player handle
---@param unitId integer|string 单位类型 ID
---@param x number X 坐标
---@param y number Y 坐标
---@param face number 朝向角度
function mock_functions.CreateUnit(idPlayer, unitId, x, y, face)
    local h = make_handle('unit', {
        unitTypeId = unitId,
        x = x, y = y, face = face,
        owner = idPlayer,
    })
    log_call('CreateUnit', { idPlayer, unitId, x, y, face }, h)
    return h
end

-- --------------------------------------------------------------------------
-- 补充：GetWidgetLife（wzns 用于判断存活，替代 IsUnitAlive/IsUnitDead）
-- --------------------------------------------------------------------------

--- GetWidgetLife - 获取 widget 生命值
---@param whichWidget table widget/unit handle
function mock_functions.GetWidgetLife(whichWidget)
    local life = 0
    if type(whichWidget) == 'table' then
        -- 优先从 states 表取（SetUnitState 设置的）
        if whichWidget.states and whichWidget.states[0] then  -- 0 = UNIT_STATE_LIFE
            life = whichWidget.states[0]
        else
            life = whichWidget.life or 100  -- 默认 100
        end
    end
    log_call('GetWidgetLife', { whichWidget }, life)
    return life
end

-- ============================================================================
-- 安装/卸载/查询 API
-- ============================================================================

--- 安装 mock 到全局环境
--- 将 mock 函数注入 _G，保存原始函数供 uninstall 恢复
function JassMock.install()
    if _installed then
        return  -- 防止重复安装
    end
    for name, fn in pairs(mock_functions) do
        -- 保存原始函数（仅当全局存在时）
        if _G[name] ~= nil then
            _originals[name] = _G[name]
        end
        _G[name] = fn
    end
    _installed = true
    print('[jass_mock] mock 已安装，共 ' .. tostring(JassMock.mock_count()) .. ' 个函数')
end

--- 卸载 mock，恢复原始全局函数
function JassMock.uninstall()
    if not _installed then
        return
    end
    -- 恢复原始函数
    for name, fn in pairs(_originals) do
        _G[name] = fn
    end
    -- 清除 mock 函数（仅清除我们注入的）
    for name, _ in pairs(mock_functions) do
        if not _originals[name] then
            _G[name] = nil
        end
    end
    _originals = {}
    _installed = false
    print('[jass_mock] mock 已卸载')
end

--- 清空调用日志
function JassMock.reset()
    _call_log = {}
    _handle_counter = 0
end

--- 查询某个 mock 函数的调用日志
---@param func_name string mock 函数名（如 'CreateUnit'）
---@return table[] calls 调用记录列表 [{args, ret, time}, ...]
function JassMock.calls(func_name)
    return _call_log[func_name] or {}
end

--- 查询某个 mock 函数的调用次数
---@param func_name string mock 函数名
---@return integer count 调用次数
function JassMock.call_count(func_name)
    local log = _call_log[func_name]
    return log and #log or 0
end

--- 获取所有调用日志
---@return table log func_name -> calls[]
function JassMock.all_calls()
    return _call_log
end

--- 获取已安装的 mock 函数列表
---@return string[] names mock 函数名列表
function JassMock.mocked_names()
    local names = {}
    for name, _ in pairs(mock_functions) do
        table.insert(names, name)
    end
    table.sort(names)
    return names
end

--- 是否已安装
---@return boolean installed
function JassMock.is_installed()
    return _installed
end

--- 获取 mock 函数定义（供测试扩展）
---@return table functions name -> function
function JassMock.get_mock_functions()
    return mock_functions
end

--- 获取 mock 函数数量
---@return integer count
function JassMock.mock_count()
    local n = 0
    for _, _ in pairs(mock_functions) do
        n = n + 1
    end
    return n
end

return JassMock
