-- ============================================================================
-- observe.lua - 生成游戏状态与周围环境的观测快照
-- ============================================================================

local observe = {}
local entity_ref = require 'script.src.auto-test.agent.entity_ref'

local HERO_CANDIDATE_TYPES = {
    Hgbx = true, Hslz = true, Hwdd = true,
    Hthd = true, Hqzj = true, Hbts = true
}

--- 安全格式化数值：支持 NaN / inf 异常暴露，普通数值保留 1 位小数
local function safe_num(val)
    if val == nil then return 0 end
    if type(val) ~= 'number' then return tostring(val) end
    if val ~= val then return "NaN" end
    if val == math.huge then return "inf" end
    if val == -math.huge then return "-inf" end
    return tonumber(string.format('%.1f', val))
end

--- 计算两点距离
local function get_distance(x1, y1, x2, y2)
    local dx = x1 - x2
    local dy = y1 - y2
    return math.sqrt(dx * dx + dy * dy)
end

--- 获取单位四字物编 ID
local function get_unit_type_str(ent)
    if ent and ent.handle and GetUnitTypeId and IdHelp and IdHelp.Id2Str then
        local ok, s = pcall(function() return IdHelp.Id2Str(GetUnitTypeId(ent.handle)) end)
        if ok and s then return s end
    end
    return tostring(ent and ent.id or "Unit")
end

--- 获取玩家主英雄（支持项目扩展与原生 JASS 优雅降级）
local function get_player_hero()
    if PlayerObj and PlayerObj.getPlayerById then
        local p0 = PlayerObj.getPlayerById(0) or PlayerObj.getPlayerById(1)
        if p0 and p0.hero then
            return p0.hero
        end
    end
    if Game and Game.curState and Game.curState().engine then
        local engine = Game.curState().engine
        local hero_entities = engine:getEntitiesWithComponent('HeroComp')
        if hero_entities then
            local fallback = nil
            for _, h in pairs(hero_entities) do
                fallback = fallback or h
                if h.isAlive and h:isAlive() then
                    return h
                end
            end
            return fallback
        end
    end

    -- 原生 JASS 降级：优先检查当前玩家当前选中的单位
    if GroupEnumUnitsSelected and Player and FirstOfGroup and CreateGroup then
        local p = (GetLocalPlayer and GetLocalPlayer()) or (Player and Player(0))
        local g = CreateGroup()
        if g then
            GroupEnumUnitsSelected(g, p, nil)
            local selected = FirstOfGroup(g)
            if DestroyGroup then DestroyGroup(g) end
            if selected and selected ~= 0 then
                return { handle = selected, id = selected, name = (GetUnitName and GetUnitName(selected)) or "Hero" }
            end
        end
    end

    -- 原生 JASS 降级：遍历当前玩家所有单位，寻找英雄单位
    if GroupEnumUnitsOfPlayer and Player and FirstOfGroup and CreateGroup then
        local p = (GetLocalPlayer and GetLocalPlayer()) or (Player and Player(0))
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
                return { handle = found, id = found, name = (GetUnitName and GetUnitName(found)) or "Hero" }
            end
        end
    end

    return nil
end

--- 提取英雄属性快照
local function extract_hero_attrs(hero)
    local attrs = {}
    local umc = hero:get('UnitModelComp')
    if umc and umc.attributeMap then
        local map = umc.attributeMap
        local core_keys = {
            '攻击', '防御', '力道', '身法', '根骨', '悟性', '移速', 
            '气血上限', '真气上限', '暴击率', '暴击伤害', '伤害加成', '减伤'
        }
        for _, k in ipairs(core_keys) do
            local num_obj = map:get(k)
            if num_obj and num_obj.get then
                attrs[k] = safe_num(num_obj:get())
            end
        end
    end
    return attrs
end

--- 提取 Buff 列表
local function extract_buffs(hero)
    local list = {}
    if hero.buffs then
        for _, buff in ipairs(hero.buffs) do
            local comp = buff:get('BuffComp')
            local remain = 0
            if comp then
                if comp.duration == 0 then
                    remain = -1 -- 永久
                else
                    remain = math.max(0, (comp.duration - comp.frameCount) * 0.02)
                end
            end
            table.insert(list, {
                id = buff.id or buff.name,
                name = buff.name or "Buff",
                stacks = buff.stack or 1,
                remain = safe_num(remain)
            })
        end
    end
    return list
end

--- 提取技能状态
local function extract_skills(hero)
    local list = {}
    if hero.skills then
        local slot_names = {"Q", "W", "E", "R", "D", "F", "B"}
        local idx = 1
        for _, skill in pairs(hero.skills) do
            local cd = 0
            if skill.getCurCool then
                cd = skill:getCurCool()
            end

            local mana_cost = skill.cost or 0
            local cur_mana = hero.getMana and hero:getMana() or 0

            local castable = true
            local reason = nil

            if cd and cd > 0.05 then
                castable = false
                reason = "cooldown"
            elseif cur_mana < mana_cost then
                castable = false
                reason = "no_mana"
            end

            local target_type = "none"
            if skill.targetType == 1 then
                target_type = "unit"
            elseif skill.targetType == 2 then
                target_type = "point"
            elseif skill.targetType == 3 then
                target_type = "unit_or_point"
            end

            local slot_str = skill.slot and tostring(skill.slot) or slot_names[idx] or ("S" .. idx)
            table.insert(list, {
                slot = slot_str,
                id = skill.id or skill.name,
                name = skill.name or "Skill",
                level = skill.level or 1,
                cd_remain = safe_num(cd),
                mana_cost = safe_num(mana_cost),
                target = target_type,
                range = safe_num(skill.range or 600),
                castable = castable,
                reason = reason
            })
            idx = idx + 1
        end
    end
    return list
end

--- 提取物品状态
local function extract_items(hero)
    local list = {}
    local items = hero.bag or hero.items
    if items then
        for slot, item in ipairs(items) do
            table.insert(list, {
                slot = slot,
                id = item.id or item.name,
                name = item.name or "Item",
                charges = item.charges or 1,
                usable = item.usable ~= false
            })
        end
    end

    -- 原生 JASS 背包物品兜底提取
    if #list == 0 and hero and hero.handle and UnitItemInSlot then
        for i = 0, 5 do
            local item_h = UnitItemInSlot(hero.handle, i)
            if item_h and item_h ~= 0 then
                table.insert(list, {
                    slot = i + 1,
                    id = (GetItemTypeId and GetItemTypeId(item_h)) or i,
                    name = (GetItemName and GetItemName(item_h)) or "Item",
                    charges = (GetItemCharges and GetItemCharges(item_h)) or 1,
                    usable = true
                })
            end
        end
    end
    return list
end

--- 生成快照
---@param options table|nil { detail = "brief"|"full", radius = 1200, mode = "step"|"free" }
---@return table
function observe.snapshot(options)
    options = options or {}
    local detail = options.detail or "full"
    local radius = options.radius or 1200
    local mode = options.mode or "step"

    local gold = 0
    local lumber = 0
    if Player and GetPlayerState and PLAYER_STATE_RESOURCE_GOLD then
        pcall(function()
            local p0 = Player(0)
            gold = GetPlayerState(p0, PLAYER_STATE_RESOURCE_GOLD) or 0
            if PLAYER_STATE_RESOURCE_LUMBER then
                lumber = GetPlayerState(p0, PLAYER_STATE_RESOURCE_LUMBER) or 0
            end
        end)
    end

    local cur_clock = ac and ac.clock and ac.clock() or 0
    local snap = {
        frame = cur_clock,
        game_time = safe_num(cur_clock / 1000.0),
        mode = mode,
        hero = nil,
        player = {
            gold = gold,
            lumber = lumber,
            realm = "初入江湖",
            wave = 1
        },
        nearby = {},
        ground_items = {},
        quest = { current = "探索游戏", progress = "进行中" },
        alerts = { since_last = 0 }
    }

    local hero = get_player_hero()
    local h_x, h_y = 0, 0
    if hero then
        if hero.getPoint then
            local pt = hero:getPoint()
            if pt then h_x, h_y = pt[1] or pt.x or 0, pt[2] or pt.y or 0 end
        elseif GetUnitX and hero.handle then
            h_x, h_y = GetUnitX(hero.handle), GetUnitY(hero.handle)
        end

        local hp = hero.getHp and hero:getHp() or (GetUnitState and GetUnitState(hero.handle, UNIT_STATE_LIFE)) or 0
        local hp_max = hero.getMaxHp and hero:getMaxHp() or (GetUnitState and GetUnitState(hero.handle, UNIT_STATE_MAX_LIFE)) or 1
        local mp = hero.getMana and hero:getMana() or (GetUnitState and GetUnitState(hero.handle, UNIT_STATE_MANA)) or 0
        local mp_max = hero.getMaxMana and hero:getMaxMana() or (GetUnitState and GetUnitState(hero.handle, UNIT_STATE_MAX_MANA)) or 1
        local facing = hero.getFacing and hero:getFacing() or (GetUnitFacing and GetUnitFacing(hero.handle)) or 0

        snap.hero = {
            ref = entity_ref.get_ref(hero),
            unit_id = hero.id,
            type_id = get_unit_type_str(hero),
            name = hero.name or "Hero",
            level = hero.getLevel and hero:getLevel() or 1,
            x = safe_num(h_x),
            y = safe_num(h_y),
            facing = safe_num(facing),
            hp = safe_num(hp),
            hp_max = safe_num(hp_max),
            mp = safe_num(mp),
            mp_max = safe_num(mp_max),
            attrs = (detail == "full") and extract_hero_attrs(hero) or {},
            buffs = extract_buffs(hero),
            skills = extract_skills(hero),
            items = extract_items(hero)
        }
    else
        snap.quest = { current = "选择门派英雄", progress = "待选人" }
    end

    -- 获取附近单位（若尚未选英雄，则返回地图上的候选英雄/单位供 Agent 选人）
    local all_nearby = {}
    if Game and Game.curState and Game.curState().engine then
        local entities = Game.curState().engine.entities
        if entities then
            for _, ent in pairs(entities) do
                if ent ~= hero and ent.handle and ent.get and ent:get('UnitModelComp') and (not ent.isAlive or ent:isAlive()) then
                    local ux, uy = 0, 0
                    if ent.getPoint then
                        local pt = ent:getPoint()
                        if pt then ux, uy = pt[1] or pt.x or 0, pt[2] or pt.y or 0 end
                    elseif GetUnitX then
                        ux, uy = GetUnitX(ent.handle), GetUnitY(ent.handle)
                    end
                    local d = hero and get_distance(h_x, h_y, ux, uy) or 0
                    if (not hero) or (d <= radius) then
                        local rel = "neutral"
                        if hero then
                            local ok_e, is_e = pcall(function() return hero.isEnemy and hero:isEnemy(ent) end)
                            local ok_a, is_a = pcall(function() return hero.isAlly and hero:isAlly(ent) end)
                            if ok_e and is_e then
                                rel = "enemy"
                            elseif ok_a and is_a then
                                rel = "ally"
                            end
                        end

                        local uhp = ent.getHp and ent:getHp() or 0
                        local umax = ent.getMaxHp and ent:getMaxHp() or 1
                        local hp_pct = safe_num(uhp / math.max(1, umax))
                        local utype = get_unit_type_str(ent)

                        local item = {
                            ref = entity_ref.get_ref(ent),
                            unit_id = ent.id,
                            type_id = utype,
                            name = ent.name or "Unit",
                            rel = rel,
                            x = safe_num(ux),
                            y = safe_num(uy),
                            dist = safe_num(d),
                            hp_pct = hp_pct,
                            is_boss = ent.isBossUnit and ent:isBossUnit(ent) or false
                        }
                        if not hero and HERO_CANDIDATE_TYPES[utype] then
                            item.selectable_hero = true
                        end
                        table.insert(all_nearby, item)
                    end
                end
            end
        end
    end

    -- 按照距离排序（选人阶段优先将 selectable_hero 排在前面）
    table.sort(all_nearby, function(a, b)
        if a.selectable_hero ~= b.selectable_hero then
            return a.selectable_hero == true
        end
        return a.dist < b.dist
    end)

    local max_count = (detail == "brief") and 8 or 20
    if #all_nearby > max_count then
        snap.nearby_truncated = #all_nearby - max_count
        for i = 1, max_count do
            table.insert(snap.nearby, all_nearby[i])
        end
    else
        snap.nearby = all_nearby
    end

    return snap
end

return observe
