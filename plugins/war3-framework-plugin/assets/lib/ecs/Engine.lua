-- Getting folder that contains our src
local folderOfThisFile = (...):match("(.-)[^%/%.]+$")
local dbg = require 'jass.debug'
local ecs = require(folderOfThisFile .. 'namespace')
local Engine = class("Engine")

-- 性能埋点 profiler (开关 PROFILER_ENABLED, 默认关; os.clock 不可用则降级不计时)
-- 开启: 控制台设 PROFILER_ENABLED = true, 每 250 帧(5秒@50fps) print 每系统耗时
PROFILER_ENABLED = PROFILER_ENABLED or false
local _profilerData = {}      -- {systemName = {time=秒, count=次数}}
local _profilerFrames = 0
local _os_clock = os and os.clock  -- War3 LuaJIT 通常支持, 不可用则 nil

function Engine:initialize(eventManager)
    self.entities = {}
    -- Root Entity of the entity tree
    self.rootEntity = Entity()
    self.singleRequirements = {}
    self.allRequirements = {}
    self.entityLists = {}
    self.eventManager = eventManager

    self.systems = {}
    self.systemRegistry = {}
    self.systems["update"] = {}
    self.systems["draw"] = {}

    self.eventManager:addListener("ComponentRemoved", self, self.componentRemoved)
    self.eventManager:addListener("ComponentAdded", self, self.componentAdded)
end

function Engine:addEntity(entity)
    -- Setting engine eventManager as eventManager for entity
    entity.eventManager = self.eventManager
    -- Getting the next free ID or insert into table
    local newId = #self.entities + 1
    entity.eid = newId
    self.entities[entity.eid] = entity
    if entity.handle then
        self.entityLists[entity.handle] = entity
    end

    -- If a rootEntity entity is defined and the entity doesn't have a parent yet, the rootEntity entity becomes the entity's parent
    if entity.parent == nil then
        entity:setParent(self.rootEntity)
    end
    entity:registerAsChild()

    for _, component in pairs(entity.components) do
        local name = component.class.name
        -- Adding Entity to specific Entitylist
        if not self.entityLists[name] then self.entityLists[name] = {} end
        self.entityLists[name][entity.eid] = entity

        -- Adding Entity to System if all requirements are granted
        if self.singleRequirements[name] then
            for _, system in pairs(self.singleRequirements[name]) do
                self:checkRequirements(entity, system)
            end
        end
    end
end

function Engine:removeEntity(entity, removeChildren, newParent)
    if self.entities[entity.eid] then
        -- Removing the Entity from all Systems and engine
        for _, component in pairs(entity.components) do
            local name = component.class.name
            if self.singleRequirements[name] then
                for _, system in pairs(self.singleRequirements[name]) do
                    system:removeEntity(entity)
                end
            end
        end
        -- Deleting the Entity from the specific entity lists
        for _, component in pairs(entity.components) do
            self.entityLists[component.class.name][entity.eid] = nil
        end

        if entity.handle then
            self.entityLists[entity.handle] = nil
        end

        -- If removeChild is defined, all children become deleted recursively
        if removeChildren then
            for _, child in pairs(entity.children) do
                self:removeEntity(child, true)
            end
        else
            -- If a new Parent is defined, this Entity will be set as the new Parent
            for _, child in pairs(entity.children) do
                if newParent then
                    child:setParent(newParent)
                else
                    child:setParent(self.rootEntity)
                end
                -- Registering as child
                entity:registerAsChild()
            end
        end
        -- Removing Reference to entity from parent
        for _, _ in pairs(entity.parent.children) do
            entity.parent.children[entity.eid] = nil
        end
        -- Setting status of entity to dead. This is for other systems, which still got a hard reference on this
        self.entities[entity.eid].alive = false
        -- Removing entity from engine
        self.entities[entity.eid] = nil
    else
        ecs.debug("Engine: Trying to remove non existent entity from engine.")
        if entity.eid then
            ecs.debug("Engine: Entity id: " .. entity.eid)
        else
            ecs.debug("Engine: Entity has not been added to any engine yet. (No entity.eid)")
        end
        ecs.debug("Engine: Entity's components:")
        for index, component in pairs(entity.components) do
            ecs.debug(index, component)
        end
    end
end

function Engine:addSystem(system, type)
    local name = system.class.name

    -- Check if the specified type is correct
    if type ~= nil and type ~= "draw" and type ~= "update" then
        ecs.debug("Engine: Trying to add System " .. name .. "with invalid type " .. type .. ". Aborting")
        return
    end

    -- Check if a type should be specified
    if system.draw and system.update and not type then
        ecs.debug("Engine: Trying to add System " .. name .. ", which has an update and a draw function, without specifying type. Aborting")
        return
    end

    -- Check if the user is accidentally adding two instances instead of one
    if self.systemRegistry[name] and self.systemRegistry[name] ~= system then
        ecs.debug("Engine: Trying to add two different instances of the same system. Aborting.")
        return
    end

    -- Adding System to engine system reference table
    if not (self.systemRegistry[name]) then
        self:registerSystem(system)
    -- This triggers if the system doesn't have update and draw and it's already existing.
    elseif not (system.update and system.draw) then
        if self.systemRegistry[name] then
            ecs.debug("Engine: System " .. name .. " already exists. Aborting")
            return
        end
    end

    -- Adding System to draw table
    if system.draw and (not type or type == "draw") then
        for _, registeredSystem in pairs(self.systems["draw"]) do
            if registeredSystem.class.name == name then
                ecs.debug("Engine: System " .. name .. " already exists. Aborting")
                return
            end
        end
        table.insert(self.systems["draw"], system)
    -- Adding System to update table
    elseif system.update and (not type or type == "update") then
        for _, registeredSystem in pairs(self.systems["update"]) do
            if registeredSystem.class.name == name then
                ecs.debug("Engine: System " .. name .. " already exists. Aborting")
                return
            end
        end
        table.insert(self.systems["update"], system)
    end

    -- Checks if some of the already existing entities match the required components.
    for _, entity in pairs(self.entities) do
        self:checkRequirements(entity, system)
    end
    return system
end

function Engine:registerSystem(system)
    local name = system.class.name
    self.systemRegistry[name] = system
    -- case: system:requires() returns a table of strings
    if not system.hasGroups then
        for index, req in pairs(system:requires()) do
            -- Registering at singleRequirements
            if index == 1 then
                self.singleRequirements[req] = self.singleRequirements[req] or {}
                table.insert(self.singleRequirements[req], system)
            end
            -- Registering at allRequirements
            self.allRequirements[req] = self.allRequirements[req] or {}
            table.insert(self.allRequirements[req], system)
        end
    end

    -- case: system:requires() returns a table of tables which contain strings
    if system.hasGroups then
        for group, componentList in pairs(system:requires()) do
            -- Registering at singleRequirements
            local component = componentList[1]
            self.singleRequirements[component] = self.singleRequirements[component] or {}
            table.insert(self.singleRequirements[component], system)

            -- Registering at allRequirements
            for _, req in pairs(componentList) do
                self.allRequirements[req] = self.allRequirements[req] or {}
                -- Check if this List already contains the System
                local contained = false
                for _, registeredSystem in pairs(self.allRequirements[req]) do
                    if registeredSystem == system then
                        contained = true
                        break
                    end
                end
                if not contained then
                    table.insert(self.allRequirements[req], system)
                end
            end
        end
    end
end

function Engine:stopSystem(name)
    if self.systemRegistry[name] then
        self.systemRegistry[name].active = false
    else
        ecs.debug("Engine: Trying to stop not existing System: " .. name)
    end
end

function Engine:startSystem(name)
    if self.systemRegistry[name] then
        self.systemRegistry[name].active = true
    else
        ecs.debug("Engine: Trying to start not existing System: " .. name)
    end
end

function Engine:toggleSystem(name)
    if self.systemRegistry[name] then
        self.systemRegistry[name].active = not self.systemRegistry[name].active
    else
        ecs.debug("Engine: Trying to toggle not existing System: " .. name)
    end
end

function Engine:update(...)
    if not PROFILER_ENABLED then
        -- 默认关闭: 零开销原逻辑
        for _, system in ipairs(self.systems["update"]) do
            if system.active then
                system:update(...)
            end
        end
        return
    end
    -- profiler 模式
    local clock = _os_clock
    for _, system in ipairs(self.systems["update"]) do
        if system.active then
            if clock then
                local name = system.class.name
                local t0 = clock()
                system:update(...)
                local dt = clock() - t0
                local d = _profilerData[name] or {time = 0, count = 0}
                d.time = d.time + dt
                d.count = d.count + 1
                _profilerData[name] = d
            else
                system:update(...)
            end
        end
    end
    if clock then
        _profilerFrames = _profilerFrames + 1
        if _profilerFrames >= 250 then  -- 5秒@50fps
            self:profilerReport()
            _profilerData = {}
            _profilerFrames = 0
        end
    end
end

-- 打印 profiler 报告 (按耗时降序), 仅 PROFILER_ENABLED 时有意义
function Engine:profilerReport()
    if not PROFILER_ENABLED then return end
    if not _os_clock then
        print("[Profiler] os.clock 不可用, 无法计时")
        return
    end
    print(string.format("[Profiler] 系统耗时(近%d帧/%.1fs):", _profilerFrames, _profilerFrames * 0.02))
    local total = 0
    local entries = {}
    for name, d in pairs(_profilerData) do
        table.insert(entries, {name = name, time = d.time, count = d.count})
        total = total + d.time
    end
    table.sort(entries, function(a, b) return a.time > b.time end)
    for _, e in ipairs(entries) do
        print(string.format("  %-30s %.4fs / %d次 (均%.3fms)", e.name, e.time, e.count, e.time / e.count * 1000))
    end
    print(string.format("  总计: %.4fs (update耗时占比%.1f%%)", total, total / (_profilerFrames * 0.02) * 100))
end

function Engine:draw()
    for _, system in ipairs(self.systems["draw"]) do
        if system.active then
            system:draw()
        end
    end
end

function Engine:componentRemoved(event)
    -- In case a single component gets removed from an entity, we inform
    -- all systems that this entity lost this specific component.
    local entity = event.entity
    local component = event.component

    -- Removing Entity from Entity lists
    self.entityLists[component][entity.eid] = nil

    -- Removing Entity from systems
    if self.allRequirements[component] then
        for _, system in pairs(self.allRequirements[component]) do
            system:componentRemoved(entity, component)
        end
    end
end

function Engine:componentAdded(event)
    local entity = event.entity
    local component = event.component

    -- Adding the Entity to Entitylist
    if not self.entityLists[component] then self.entityLists[component] = {} end
    self.entityLists[component][entity.eid] = entity
    -- Adding the Entity to the requiring systems
    if self.allRequirements[component] then
        for _, system in pairs(self.allRequirements[component]) do
            self:checkRequirements(entity, system)
        end
    end
end

function Engine:getRootEntity()
    if self.rootEntity ~= nil then
        return self.rootEntity
    end
end

-- Returns an Entitylist for a specific component. If the Entitylist doesn't exist yet it'll be created and returned.
function Engine:getEntitiesWithComponent(component)
    if not self.entityLists[component] then self.entityLists[component] = {} end
    return self.entityLists[component]
end

function Engine:getEntityWithHandle(handle)
    return self.entityLists[handle]
end

-- Returns a count of existing Entities with a given component
function Engine:getEntityCount(component)
    local count = 0
    if self.entityLists[component] then
        for _, system in pairs(self.entityLists[component]) do
            count = count + 1
        end
    end
    return count
end

function Engine:checkRequirements(entity, system) -- luacheck: ignore self
    local meetsRequirements = true
    local foundGroup = nil
    for group, req in pairs(system:requires()) do
        if not system.hasGroups then
            if not entity.components[req] then
                meetsRequirements = false
                break
            end
        else
            meetsRequirements = true
            for _, req2 in pairs(req) do
                if not entity.components[req2] then
                    meetsRequirements = false
                    break
                end
            end
            if meetsRequirements == true then
                foundGroup = true
                system:addEntity(entity, group)
            end
        end
    end
    if meetsRequirements == true and foundGroup == nil then
        system:addEntity(entity)
    end
end

return Engine