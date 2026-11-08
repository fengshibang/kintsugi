-- ============================================================================
-- actions.lua - 语义动作转换为 War3 原生指令执行
-- ============================================================================

local actions = {}
local entity_ref = require 'script.src.auto-test.agent.entity_ref'

--- 获取主英雄对象（兼容哈希表形式的 getEntitiesWithComponent('HeroComp')）
local function get_hero()
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
    return nil
end

--- 选择门派英雄（通过触发双击选人事件或直接调用 HeroSelectionSystem）
local function select_hero_for_player(hero_spec)
    if not (Game and Game.curState and Game.curState().engine) then
        return false, "NO_ENGINE"
    end
    local state = Game.curState()
    local engine = state.engine

    -- 查找玩家1实体
    local player = nil
    if PlayerObj and PlayerObj.getPlayerById then
        player = PlayerObj.getPlayerById(0) or PlayerObj.getPlayerById(1)
    end
    if not player then
        local p_list = engine:getEntitiesWithComponent('PlayerComp')
        if p_list then
            for _, p in pairs(p_list) do
                if p.id == 0 or p.id == 1 then
                    player = p
                    break
                end
                player = player or p
            end
        end
    end
    if not player then return false, "NO_PLAYER" end

    -- 查找目标选人单位
    local target_unit = nil
    if type(hero_spec) == 'string' and hero_spec:match("^u:") then
        target_unit = entity_ref.resolve(hero_spec)
    end
    if not target_unit then
        for _, ent in pairs(engine.entities) do
            if ent.handle and ent.name then
                local uid = (GetUnitTypeId and IdHelp and IdHelp.Id2Str and IdHelp.Id2Str(GetUnitTypeId(ent.handle))) or tostring(ent.id)
                if not hero_spec or hero_spec == "" or uid == hero_spec or tostring(ent.name):find(tostring(hero_spec), 1, true) then
                    if uid == 'Hgbx' or uid == 'Hslz' or uid == 'Hwdd' or uid == 'Hthd' or uid == 'Hqzj' or uid == 'Hbts' then
                        target_unit = ent
                        break
                    end
                end
            end
        end
    end
    if not target_unit then return false, "HERO_UNIT_NOT_FOUND" end

    -- 触发两次 AnyPlayerSelectUnit 完成双击选人
    if state.eventManager and AnyPlayerSelectUnit then
        state.eventManager:fireEvent(AnyPlayerSelectUnit(player, target_unit))
        state.eventManager:fireEvent(AnyPlayerSelectUnit(player, target_unit))
        return true, nil
    end
    return false, "NO_EVENT_MANAGER"
end

--- 查找英雄身上的技能对象
local function find_hero_skill(hero, skill_spec)
    if not hero or not hero.skills then return nil end

    -- 1. 按槽位匹配（Q, W, E, R, 0, 1...）
    local spec_str = tostring(skill_spec):upper()
    for _, skl in pairs(hero.skills) do
        if skl.slot and tostring(skl.slot):upper() == spec_str then
            return skl
        end
    end

    -- 2. 按技能 ID 或名称匹配
    for _, skl in pairs(hero.skills) do
        if skl.id == skill_spec or skl.name == skill_spec then
            return skl
        end
    end

    return nil
end

--- 执行单条动作
---@param hero table 英雄实体
---@param act table 动作定义
---@return table 结果 { op = string, issued = boolean, error = string|nil }
function actions.execute_single(hero, act)
    local op = act.op
    local res = { op = op, issued = false, error = nil }

    if op == "select_hero" then
        local spec = (act.target and act.target.ref) or act.hero_id or act.name or "Hgbx"
        local ok, err = select_hero_for_player(spec)
        res.issued = ok
        res.error = err
        return res
    end

    if not hero or not hero.handle then
        res.error = "NO_HERO"
        return res
    end

    local h = hero.handle

    if op == "move" then
        if not act.x or not act.y then
            res.error = "MISSING_PARAM"
            return res
        end
        res.issued = (IssuePointOrder and IssuePointOrder(h, "move", act.x, act.y)) or false

    elseif op == "attack_move" then
        if not act.x or not act.y then
            res.error = "MISSING_PARAM"
            return res
        end
        res.issued = (IssuePointOrder and IssuePointOrder(h, "attack", act.x, act.y)) or false

    elseif op == "attack" then
        local target_ref = act.target and act.target.ref
        local target_obj, err = entity_ref.resolve(target_ref)
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
        local skill = find_hero_skill(hero, act.skill)
        if not skill then
            res.error = "SKILL_NOT_FOUND"
            return res
        end

        local order_str = skill.getOrder and skill:getOrder()
        if not order_str or order_str == "" then
            order_str = "channel"
        end

        local t_type = skill.targetType or 0
        if t_type == 1 then -- 单位目标
            local target_ref = act.target and act.target.ref
            local target_obj, err = entity_ref.resolve(target_ref)
            if not target_obj then
                res.error = err or "INVALID_TARGET"
                return res
            end
            local th = (type(target_obj) == 'table' and target_obj.handle) or target_obj
            res.issued = (IssueTargetOrder and IssueTargetOrder(h, order_str, th)) or false

        elseif t_type == 2 then -- 点目标
            local x = act.target and act.target.x or act.x
            local y = act.target and act.target.y or act.y
            if not x or not y then
                res.error = "MISSING_PARAM"
                return res
            end
            res.issued = (IssuePointOrder and IssuePointOrder(h, order_str, x, y)) or false

        elseif t_type == 3 then -- 单位或点目标
            if act.target and act.target.ref then
                local target_obj = entity_ref.resolve(act.target.ref)
                if target_obj then
                    local th = (type(target_obj) == 'table' and target_obj.handle) or target_obj
                    res.issued = (IssueTargetOrder and IssueTargetOrder(h, order_str, th)) or false
                    return res
                end
            end
            local x = act.target and act.target.x or act.x or 0
            local y = act.target and act.target.y or act.y or 0
            res.issued = (IssuePointOrder and IssuePointOrder(h, order_str, x, y)) or false

        else -- 0: 无目标瞬发
            res.issued = (IssueImmediateOrder and IssueImmediateOrder(h, order_str)) or false
        end

    elseif op == "use_item" then
        local slot = act.slot or 1
        local item_slot = slot - 1 -- War3 从 0 开始
        if UnitUseItem then
            res.issued = UnitUseItem(h, item_slot)
        end

    elseif op == "pick_up" then
        local target_ref = act.target and act.target.ref
        local item_obj, err = entity_ref.resolve(target_ref)
        if not item_obj then
            res.error = err or "INVALID_TARGET"
            return res
        end
        local ih = (type(item_obj) == 'table' and item_obj.handle) or item_obj
        res.issued = (IssueTargetOrder and IssueTargetOrder(h, "smart", ih)) or false

    elseif op == "chat" then
        local txt = act.text
        if txt and Game and Game.curState and Game.curState().eventManager then
            -- 模拟聊天事件
            res.issued = true
        else
            res.error = "CHAT_FAILED"
        end

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
