local fs = require 'bee.filesystem'
local root = fs.absolute(fs.path '..')

fs.create_directories(root / 'log' / 'info')
local logfile = root / 'log' / 'info' / (os.date('%Y-%m-%d %H-%M-%S') .. '.log')
return {
    info = function (msg)
        local f = io.open(logfile:string(), 'a+')
        if f then
            f:write(string.format("%s %s\n", os.date('Date: %Y-%m-%d %H:%M:%S'),msg))
            f:close()
        end
    end
}