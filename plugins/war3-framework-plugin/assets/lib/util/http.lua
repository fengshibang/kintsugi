local jass = require 'jass.common'
local dzapi = require 'jass.dzapi'

local http = {}

local trg = jass.CreateTrigger()

dzapi.DzTriggerRegisterSyncData(trg, "http", false)
jass.TriggerAddAction(trg, function ()
    local handle = dzapi.DzGetTriggerSyncPlayer()
    local data = dzapi.DzGetTriggerSyncData()

    print('玩家', jass.GetPlayerId(handle), '下载了', data)
end)


local url = "43.248.131.180:8003"

--访问服务器下载数据 当下载完成后 会得到一个result 返回值
--5秒后超时 



http.post = function(post,_url)
    post_message(_url or url,  post, function (result)
        --由于数据是异步的 要同步给其他人 
        if result ~= '' then
            dzapi.DzSyncData("http", result) 
        else
            log.debug('请求失败：'..post)
        end
    end)
end

return http