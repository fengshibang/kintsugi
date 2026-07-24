local code = require 'jass.code'
local hook = require 'jass.hook'
local jass = require 'jass.common'
local japi = require 'jass.japi'
local g = require 'jass.globals'
local dbg = require 'jass.debug'
local slk = require 'jass.slk'

function code.AnyUnitDamage(source, target, damage)
    Game.curState().eventManager:fireEvent(AnyUnitDamaged(source, target, damage))
end

-- function hook.RemoveUnit(unit, realfunc)
--     local targetUnit = Game.curState().engine:getEntityWithHandle(unit)
--     if targetUnit then
--         targetUnit:destroy()
--     end
--     realfunc(unit)
-- end

-- local wzList = {"偏将军", "中领军", "安东将军", "征东将军", "前将军", "卫将军", "车骑将军",
--                 "骠骑将军", "大将军"}

-- local zgRequire = {200, 500, 1200, 2400, 4800, 7200, 9600, 12000, 15000}
-- -- local zgRequire ={
-- --     2,
-- --     5,
-- --     12,
-- --     24,
-- --     48,
-- --     72,
-- --     96,
-- --     120,
-- --     150,
-- -- }

-- local wzSkill = {{"算无遗策", "A0AW"}, {"勇战", "A0AX"}, {"振奋", "A0AY"}, {"陷阵之志", "A0AZ"},
--                  {"领袖", "A0B1"}}

-- function code.OnZhanGongChange(playerHandle)
--     local player = Game.curState().engine:getEntityWithHandle(playerHandle)
--     xpcall(function()
--         if player then
--             local zg = player:getRes('战功')
--             for i = #zgRequire, 1, -1 do
--                 local hero = player.hero
--                 if hero and (zg >= zgRequire[i]) and
--                     ((not player:getData('武职等级')) or (player:getData('武职等级') < i)) then
--                     player:setData('武职等级', i)
--                     if i >= 5 then
--                         if not player:getData('武职技能') then
--                             local r = math.random(#wzSkill)
--                             hero:addSkill(wzSkill[r][1], wzSkill[r][2])
--                             player:setData('武职技能', wzSkill[r][1])
--                         else
--                             local r = player:getData('武职技能')
--                             local skl = hero:findSkill(r)
--                             skl:setLevel(i - 4, true)
--                         end
--                     end
--                     for j = 1, #wzList, 1 do
--                         if hero:findBuff(wzList[j]) then
--                             hero:removeBuff(wzList[j])
--                         end
--                     end
--                     hero:addBuff({
--                         from = hero,
--                         name = wzList[i]
--                     })
--                     break
--                 end
--             end
--         end
--     end, ecs.debugError)
-- end

-- function code.CaculateScore()
--     if is_player(GetEnumPlayer()) then
        
--         code.YDWERPGAddKey(GetEnumPlayer(), "tong" .. g.Qnandu, 1)
--         if g.Qnandu >= 0 then
--             code.YDWERPGAddKey(GetEnumPlayer(), "S1XSND", 2)
--         elseif g.Qnandu == 4 then
--             code.YDWERPGAddKey(GetEnumPlayer(), "S1GSJM", 2)
--         end
--     end
-- end

-- ac.loop(1000,function()
--     ForForce(GetPlayersAll,function()
--         if is_player(GetEnumPlayer()) then
--             code.YDWERPGAddKey(GetEnumPlayer(), "S1JRJJ", 1)
--         end
--     end)
-- end)


-- function hook.CreateItem(itemId,x,y,realfunc)
--     local handle = realfunc(itemId,x,y)
--     dbg.handle_ref(handle)
--     AssetsManager.singleton:createItem(handle)
--     return handle
-- end

-- function CreateItem(itemId,x,y)
--     return hook.CreateItem(itemId,x,y,jass.CreateItem)
-- end

-- function hook.RemoveItem(handle,realfunc)
--     local it = Game.curState().engine:getEntityWithHandle(handle)
--     if it then
--         Game.curState().engine:removeEntity(it)
--     end
--     realfunc(handle)
-- end


-- function RemoveItem(handle)
--     return hook.RemoveItem(handle,jass.RemoveItem)
-- end



