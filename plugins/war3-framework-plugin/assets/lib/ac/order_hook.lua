
local message = require 'jass.message'
local japi = require 'jass.japi'
local jass= require'jass.common'



local event_map = {

    --本地发布无目标命令
    ['order_immediate'] = function (unit_handle, info)
        --当框选一群单位发布命令时 flag 会变化
        local name, order_id, unknow, flag = table.unpack(info)
        if IdHelp.id2Order[order_id] == 'stop' then
            return true
        end
        local hero = Game.curState().engine:getEntityWithHandle(unit_handle)
        if hero then
            local skills = hero.skills
            for i, skl in ipairs(skills) do
                if skl:castingHard() and skl:isCasting() then
                    return false
                end                
            end
        end    
        return true
    end,

    --本地发布点命令
    ['order_point'] = function (unit_handle, info)
        --当框选一群单位发布命令时 flag 会变化
        local name, order_id, unknow, x, y, flag = table.unpack(info)    
        local hero = Game.curState().engine:getEntityWithHandle(unit_handle)
        if hero then
            local skills = hero.skills
            for i, skl in ipairs(skills) do
                if skl:castingHard() and skl:isCasting() then
                    return false
                end                
            end
        end         
        return true
    end,

    --本地发布目标命令
    ['order_target'] = function (unit_handle, info)
        --当框选一群单位发布命令时 flag 会变化
        --当对地面发布命令时 handle 为0
        local name, order_id, unknow, x, y, handle, flag = table.unpack(info)  
        local hero = Game.curState().engine:getEntityWithHandle(unit_handle)
        if hero then
            local skills = hero.skills
            for i, skl in ipairs(skills) do
                if skl:castingHard() and skl:isCasting() then
                    return false
                end                
            end
        end      
        return true
    end,

    --本地右键单位发布命令
    ['order_smart'] = function (unit_handle, info)
        --当框选一群单位发布命令时 flag 会变化
        local name, order_id, unknow, handle, flag = table.unpack(info)
        return true
    end,

    --本地物品丢弃事件
    ['order_discard'] = function (unit_handle, info)
        local name, order_id, unknow, x, y, unit, handle, flag = table.unpack(info) 
        return true
    end,

}

function message.order_hook(info)
    local unit_handle = japi.GetRealSelectUnit() 
    local event = event_map[info[1]]
    if event then 
        return event(unit_handle, info)
    end 
    return true 
end