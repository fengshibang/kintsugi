-- ============================================================================
-- setup.lua - 游戏场景预置（作弊/调试指令，仅冻结或测试期可用）
-- ============================================================================

local setup = {}
local bridge = require 'script.src.auto-test.agent.bridge'

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

--- 执行场景预置命令
---@param cmd string 命令名称
---@param args table 命令参数
---@return boolean ok, string|nil err
function setup.execute(cmd, args)
    args = args or {}
    local hero = get_hero()
    local p = Player and Player(0)

    -- 记录 setup 事件
    bridge.event('setup', { cmd = cmd, args = args })

    if cmd == "add_gold" then
        local amt = args.amount or 10000
        if SetPlayerState and p and GetPlayerState then
            local cur = GetPlayerState(p, PLAYER_STATE_RESOURCE_GOLD)
            SetPlayerState(p, PLAYER_STATE_RESOURCE_GOLD, cur + amt)
            return true
        end

    elseif cmd == "set_level" then
        local lv = args.level or 1
        if hero and hero.handle and SetHeroLevel then
            SetHeroLevel(hero.handle, lv, true)
            return true
        end

    elseif cmd == "heal_full" then
        if hero and hero.handle and SetUnitState then
            local max_hp = hero.getMaxHp and hero:getMaxHp() or 10000
            local max_mp = hero.getMaxMana and hero:getMaxMana() or 10000
            SetUnitState(hero.handle, UNIT_STATE_LIFE, max_hp)
            SetUnitState(hero.handle, UNIT_STATE_MANA, max_mp)
            return true
        end

    elseif cmd == "reset_cd" then
        if hero and hero.skills then
            for _, skl in pairs(hero.skills) do
                if skl.setCurCool then
                    skl:setCurCool(0)
                end
            end
            return true
        end

    elseif cmd == "teleport" then
        local x = args.x or 0
        local y = args.y or 0
        if hero and hero.handle and SetUnitPosition then
            SetUnitPosition(hero.handle, x, y)
            return true
        end

    elseif cmd == "spawn" then
        local type_id = args.type_id
        local x = args.x or 0
        local y = args.y or 0
        local count = args.count or 1
        local owner_id = args.owner or 12 -- 默认野怪/敌人玩家

        if CreateUnit and type_id then
            local owner_p = Player and Player(owner_id)
            local raw_id = type(type_id) == 'string' and IdHelp and IdHelp.Str2Id and IdHelp.Str2Id(type_id) or type_id
            for _ = 1, count do
                CreateUnit(owner_p, raw_id, x, y, 0)
            end
            return true
        end

    elseif cmd == "add_item" then
        local item_id = args.item_id
        if hero and hero.handle and UnitAddItemById and item_id then
            local raw_id = type(item_id) == 'string' and IdHelp and IdHelp.Str2Id and IdHelp.Str2Id(item_id) or item_id
            UnitAddItemById(hero.handle, raw_id)
            return true
        end

    elseif cmd == "learn_skill" then
        local skill_id = args.skill_id
        local lv = args.level or 1
        if hero and hero.addSkill and skill_id then
            hero:addSkill(skill_id, skill_id)
            return true
        end
    end

    return false, "UNKNOWN_SETUP_CMD"
end

return setup
