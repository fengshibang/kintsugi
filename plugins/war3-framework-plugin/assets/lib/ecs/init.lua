class = require('script.lib.util.middleclass')
local folderOfThisFile = (...)..'.'
require(folderOfThisFile..'engine')

if folderOfThisFile == nil then
    folderOfThisFile = ""
end

ecs = require(folderOfThisFile .. 'namespace')
local jass = require "jass.common"
local japi = require "jass.japi"
local runtime    = require 'jass.runtime'
local g = require 'jass.globals'

runtime.handle_level = 1
runtime.sleep = false
runtime.catch_crash = false

local log = require('script.lib.util.log')


function ecs.debug(message)
    if ecs.config.debug then
        for i = 0, 3 do
            DisplayTextToPlayer(Player(i), 0, 0, "|cffff0000" .. message .. "|r")
        end
        print(tostring(message) .. "\n")
        print(tostring(debug.traceback()) .. "\n")
    end
end

function ecs.debugError(msg)
    print("---------------------------------------")
    print("              LUA ERROR!!              ")
    print("---------------------------------------")
    print(tostring(msg))
    print(debug.traceback())
    print("---------------------------------------")
end

--错误汇报
function runtime.error_handle(msg)
    ecs.debugError(msg)
end

local mt = {}
function mt:__index(i)
    if i < 0 or i > 8191 then
        ecs.debugError("数组索引越界:" .. i)
    end
    return rawget(self, "_default")
end

function mt:__newindex(i, v)
    if i < 0 then
        ecs.debugError("数组索引越界:" .. i)
    elseif i > 8191 then
        ecs.debugError("数组索引越界:" .. i)
    end
    rawset(self, i, v)
end

function _array_(default)
    return setmetatable({ _default = default }, mt)
end

function _loop_()
    local i = 0
    return function()
        if i > 1000000 then
            ecs.debugError("循环次数太多")
        end
        i = i + 1
        return true
    end
end

function _native_(name)
    return _G[name] or japi[name] or jass[name]
end
local function populateNamespace(ns)
    -- require(folderOfThisFile .. "lib.common")
    -- require(folderOfThisFile .. "lib.library")
    -- require(folderOfThisFile .. "lib.japi") 

    --util
    local utilFolder = 'script.lib.util.'
    ns.AttachPoint = require(utilFolder .. "AttachPoint")
    ns.Thread = require(utilFolder .. "thread")
    ns.IdHelp = require(utilFolder .. "IdHelp")
    ns.lume = require(utilFolder .. "lume")
    ns.linklist = require(utilFolder .. "linklist")
    ns.Easing = require(utilFolder .. "Easing")
    ns.Vector3 = require(utilFolder .. 'Vector3')
    ns.BinaryTree = require(utilFolder .. 'BinaryTree')
    -- ns.dzapi = require(utilFolder .. 'dzapi')
    ns.api = require(utilFolder .. 'skyapi')
    -- ns.pcrypt = require(utilFolder .. "pcrypt")
    -- ns.rdata = require(utilFolder .. "remote_data")
    ns.Color = require(utilFolder .. "Color")
    -- ns.util = require(folderOfThisFile .. "src.util")

    -- --lib
    -- local libFolder = folderOfThisFile .. "lib."
    -- ns.class = require(libFolder .. 'middleclass')
    -- ns.Matrix3x3 = require(libFolder .. 'Matrix3x3')
    -- ns.Vector3 = require(libFolder .. 'Vector3')
    -- ns.Quaternion = require(libFolder .. 'Quaternion')
    -- ns.Timer = require(libFolder .. "Timer")
    -- ns.TweenEasing = require(libFolder .. "tweener.TweenEasing")
    -- ns.TweenStyle = require(libFolder .. "tweener.TweenStyle")
    -- ns.Path = require('scripts.Path.Path')
    -- ns.PathNode = require('scripts.Path.PathNode')

    -- Events
    ns.ComponentAdded = require(folderOfThisFile .. "events.ComponentAdded")
    ns.ComponentRemoved = require(folderOfThisFile .. "events.ComponentRemoved")

    -- 底层框架
    ns.Entity = require(folderOfThisFile .. "Entity")
    ns.Engine = require(folderOfThisFile .. "Engine")
    ns.System = require(folderOfThisFile .. "System")
    ns.EventManager = require(folderOfThisFile .. "EventManager")
    ns.Component = require(folderOfThisFile .. "Component")
end

function ecs.initialize(opts)
    ecs.class = class
    if not ecs.initialized then
        ecs.config = {
            japi = true,
            globals = true,
            debug = true,
            version = 2.90,
        }
        local config = ecs.config

        if config.globals then
            populateNamespace(_G)
        end
    else
        print('框架已经初始化.')
    end
end

return ecs