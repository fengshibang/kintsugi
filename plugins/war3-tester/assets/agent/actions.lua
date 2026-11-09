-- ============================================================================
-- actions.lua - 语义动作转换为 War3 原生指令执行（Universal Harness Core）
-- 遵循铁律：所有动作必须走 War3 原生 Order (Issue*Order) 或原生 JASS API，
-- 严禁直接调用业务系统的内部回调函数（如 fireEvent、on_cast、on_damage）。
-- ============================================================================

local actions = {}
local entity_ref = nil
pcall(function()
    entity_ref = require 'script.src.auto-test.agent.entity_ref'
end)

--- 通用获取原生玩家句柄（默认 Player 0 / Player 1）
local function get_native_player()
    if GetLocalPlayer then return GetLocalPlayer() end
    if Player then return Player(0) end
    return nil
end

--- 通用获取主英雄对象（支持项目扩展与原生 JASS 优雅降级）
local function get_hero()
    -- 1. 项目特定扩展尝试：PlayerObj / Game.curState
    if PlayerObj and PlayerObj.getPlayerById then
        local p0 = PlayerObj.getPlayerById(0) or PlayerObj.getPlayerById(1)
        if p0 and p0.hero then
            return p0.hero
        end
    end
    if Game and Game.curState and Game.curState().engine then
        local heroes = Game.curState().engine:getEntitiesWithComponent('HeroComp')
        if heroes then
            for _, h in pairs(heroes) do
                return h
            end
        end
    end

    -- 2. 原生 JASS 降级：优先检查当前玩家当前框选/选中的单位
    if GroupEnumUnitsSelected and Player and FirstOfGroup and CreateGroup then
        local p = get_native_player()
        local g = CreateGroup()
        if g then
            GroupEnumUnitsSelected(g, p, nil)
            local selected = FirstOfGroup(g)
            if DestroyGroup then DestroyGroup(g) end
            if selected and selected ~= 0 then
                return { handle = selected, id = selected }
            end
        end
    end

    -- 3. 原生 JASS 降级：遍历当前玩家名下所有单位，寻找 Hero
    if GroupEnumUnitsOfPlayer and Player and FirstOfGroup and CreateGroup then
        local p = get_native_player()
        local g = CreateGroup()
        if g then
            GroupEnumUnitsOfPlayer(g, p, nil)
            local u = FirstOfGroup(g)
            local found = nil
            while u and u ~= 0 do
                if IsUnitType and IsUnitType(u, UNIT_TYPE_HERO) then
                    found = u
                    break
                end
                if GroupRemoveUnit then GroupRemoveUnit(g, u) end
                u = FirstOfGroup(g)
            end
            if DestroyGroup then DestroyGroup(g) end
            if found then
                return { handle = found, id = found }
            end
        end
    end

    return nil
end

--- 通用选择单位（纯原生 JASS 契约，绝不调用 fireEvent 等私有业务回调）
local function select_hero_for_player(hero_spec)
    local target_handle = nil

    -- 1. 解析 entity_ref 引用
    if entity_ref and type(hero_spec) == 'string' and hero_spec:match("^u:?%d+") then
        local ent = entity_ref.resolve(hero_spec)
        target_handle = (type(ent) == 'table' and ent.handle) or ent
    end

    -- 2. 解析数值 handle 或 id
    if not target_handle and tonumber(hero_spec) then
        target_handle = tonumber(hero_spec)
    end

    -- 3. 项目特定 ECS 候选单位解析（若存在）
    if not target_handle and Game and Game.curState and Game.curState().engine then
        local engine = Game.curState().engine
        for _, ent in pairs(engine.entities or {}) do
            if ent.handle and ent.get and ent:get('UnitModelComp') then
                local utype = (GetUnitTypeId and IdHelp and IdHelp.Id2Str and IdHelp.Id2Str(GetUnitTypeId(ent.handle))) or ""
                if not hero_spec or hero_spec == "" or utype == tostring(hero_spec) or tostring(ent.name or ""):find(tostring(hero_spec), 1, true) then
                    target_handle = ent.handle
                    break
                end
            end
        end
    end

    if not target_handle then
        return false, "HERO_UNIT_NOT_FOUND"
    end

    -- 4. 纯原生 JASS 选人契约：驱动 War3 引擎原生的 EVENT_PLAYER_UNIT_SELECTED 事件
    local p = get_native_player()
    if ClearSelectionForPlayer and p then
        ClearSelectionForPlayer(p)
    end
    if SelectUnitForPlayerSingle and p then
        SelectUnitForPlayerSingle(target_handle, p)
        return true, nil
    elseif SelectUnit then
        SelectUnit(target_handle, true)
        return true, nil
    end

    return false, "NO_NATIVE_SELECTION_API"
end

--- 查找英雄身上的技能对象（与 observe.lua 一致）
local function find_hero_skill(hero, skill_spec)
    if not hero or not hero.skills or not skill_spec then return nil end

    local slot_names = {"Q", "W", "E", "R", "D", "F", "B"}
    local spec_str = tostring(skill_spec):upper()

    -- 1. 按槽位匹配
    local idx = 1
    for _, skl in pairs(hero.skills) do
        local slot_str = skl.slot and tostring(skl.slot):upper() or slot_names[idx] or ("S" .. idx)
        if slot_str == spec_str then
            return skl
        end
        idx = idx + 1
    end

    -- 2. 按技能 ID 或名称匹配
    for _, skl in pairs(hero.skills) do
        if tostring(skl.id or ""):upper() == spec_str or skl.name == skill_spec then
            return skl
        end
    end

    return nil
end

--- 解析目标引用（兼容通用 handle 与 entity_ref）
local function resolve_target_from_act(act)
    local ref = (act.target and act.target.ref) or act.ref or act.target_ref
    if not ref and act.target_id then
        ref = "u" .. tostring(act.target_id)
    end
    if entity_ref and ref then
        return entity_ref.resolve(ref)
    end
    if act.target and type(act.target) == 'table' and act.target.handle then
        return act.target.handle
    end
    return act.target or act.target_id
end

--- 执行单条动作（纯原生 War3 Order / Native JASS 驱动）
---@param hero table|number 英雄对象或句柄
---@param act table 动作定义
---@return table 结果 { op = string, issued = boolean, error = string|nil }
function actions.execute_single(hero, act)
    local op = act.op
    local res = { op = op, issued = false, error = nil }

    if op == "select_hero" then
        local spec = (act.target and act.target.ref) or act.ref or act.unit_id or act.hero_id or act.id or act.name
        local ok, err = select_hero_for_player(spec)
        res.issued = ok
        res.error = err
        return res
    elseif op == "wait" then
        res.issued = true
        return res
    end

    -- 提取原生句柄
    local h = (type(hero) == 'table' and hero.handle) or hero
    if not h or h == 0 then
        res.error = "NO_HERO"
        return res
    end

    if op == "move" then
        if not act.x or not act.y then
            res.error = "MISSING_PARAM"
            return res
        end
        res.issued = (IssuePointOrder and IssuePointOrder(h, "move", act.x, act.y)) or false
        if res.issued and _G.__agent_record_move_order then
            _G.__agent_record_move_order(act.x, act.y)
        end

    elseif op == "attack_move" then
        if not act.x or not act.y then
            res.error = "MISSING_PARAM"
            return res
        end
        res.issued = (IssuePointOrder and IssuePointOrder(h, "attack", act.x, act.y)) or false

    elseif op == "attack" then
        local target_obj, err = resolve_target_from_act(act)
        if not target_obj then
            res.error = err or "INVALID_TARGET"
            return res
        end
        local th = (type(target_obj) == 'table' and target_obj.handle) or target_obj
        res.issued = (IssueTargetOrder and IssueTargetOrder(h, "attack", th)) or false

    elseif op == "stop" then
        res.issued = (IssueImmediateOrder and IssueImmediateOrder(h, "stop")) or false

    elseif op == "hold" then
        res.issued = (IssueImmediateOrder and IssueImmediateOrder(h, "holdposition")) or false

    elseif op == "cast" then
        -- 优先提取原生 Order 字符串（全通用支持）
        local order_str = act.order or act.order_str
        local t_type = act.target_type or act.targetType

        -- 若未显式指定 order_str，尝试从技能槽位/对象中获取
        if not order_str or order_str == "" then
            local skill_spec = act.skill or act.slot or act.id
            local skill = find_hero_skill(hero, skill_spec)
            if skill then
                order_str = skill.getOrder and skill:getOrder()
                t_type = t_type or skill.targetType
            end
        end

        if not order_str or order_str == "" then
            order_str = "channel"
        end

        t_type = t_type or 0

        if t_type == 1 then -- 单位目标
            local target_obj, err = resolve_target_from_act(act)
            if not target_obj then
                res.error = err or "INVALID_TARGET"
                return res
            end
            local th = (type(target_obj) == 'table' and target_obj.handle) or target_obj
            res.issued = (IssueTargetOrder and IssueTargetOrder(h, order_str, th)) or false

        elseif t_type == 2 then -- 点目标
            local x = (type(act.target) == 'table' and act.target.x) or act.x
            local y = (type(act.target) == 'table' and act.target.y) or act.y
            if not x or not y then
                res.error = "MISSING_PARAM"
                return res
            end
            res.issued = (IssuePointOrder and IssuePointOrder(h, order_str, x, y)) or false

        elseif t_type == 3 then -- 单位或点目标
            local target_obj = resolve_target_from_act(act)
            if target_obj then
                local th = (type(target_obj) == 'table' and target_obj.handle) or target_obj
                res.issued = (IssueTargetOrder and IssueTargetOrder(h, order_str, th)) or false
                return res
            end
            local x = (type(act.target) == 'table' and act.target.x) or act.x or 0
            local y = (type(act.target) == 'table' and act.target.y) or act.y or 0
            res.issued = (IssuePointOrder and IssuePointOrder(h, order_str, x, y)) or false

        else -- 0: 无目标瞬发
            res.issued = (IssueImmediateOrder and IssueImmediateOrder(h, order_str)) or false
        end

    elseif op == "use_item" then
        local slot = act.slot or 1
        local item_slot = slot - 1
        if UnitUseItem then
            res.issued = UnitUseItem(h, item_slot)
        end

    elseif op == "pick_up" then
        local item_obj, err = resolve_target_from_act(act)
        if not item_obj then
            res.error = err or "INVALID_TARGET"
            return res
        end
        local ih = (type(item_obj) == 'table' and item_obj.handle) or item_obj
        res.issued = (IssueTargetOrder and IssueTargetOrder(h, "smart", ih)) or false

    else
        res.error = "UNKNOWN_OP"
    end

    return res
end

--- 批量执行动作列表
---@param actions_list table[]
---@return table[] results
function actions.execute_batch(actions_list)
    local hero = get_hero()
    local results = {}
    if not actions_list or type(actions_list) ~= 'table' then
        return results
    end

    for _, act in ipairs(actions_list) do
        local ok, r = pcall(actions.execute_single, hero, act)
        if ok and r then
            table.insert(results, r)
        else
            table.insert(results, { op = act.op or "unknown", issued = false, error = "EXEC_EXCEPTION" })
        end
    end
    return results
end

return actions
