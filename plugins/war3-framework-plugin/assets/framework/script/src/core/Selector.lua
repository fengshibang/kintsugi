-- core/Selector.lua — 范围/直线选择器
-- 提炼自 rouge_lua core/Selector.lua,剥 MoeHero 专属 removeGod(RestrictionInvulnerableComp)
-- 设计:对象池复用临时 entitys 表,标量化距离计算避免 Vector3 分配

Selector = class("Selector")

-- 对象池:复用 inRange/inLine 内的临时 entitys 表
-- 栈式 pop/push, 栈纪律天然支持重入嵌套
local entitysPool = {}

local function acquireEntitys()
    local t = table.remove(entitysPool)
    if t then
        for k in pairs(t) do t[k] = nil end
        return t
    end
    return {}
end

local function releaseEntitys(t)
    for k in pairs(t) do t[k] = nil end
    table.insert(entitysPool, t)
end

function Selector:initialize(data)
    self.selected = {}
    if data then
        self.isEnemy = data.isEnemy
    end
end

-- 圆形范围选择
-- @param center 中心点(entity 或 point)
-- @param radius 半径
-- @param comps 组件列表(第一个组件用于 getEntitiesWithComponent,后续组件过滤)
-- @param call 回调函数(可选,返回 true 中断)
function Selector:inRange(center, radius, comps, call)
    local _entitys = Game.curState().engine:getEntitiesWithComponent(comps[1])
    local entitys = acquireEntitys()
    for i, v in pairs(_entitys) do
        local flag = true
        for i = 2, #comps, 1 do
            if not v:has(comps[i]) then
                flag = false
                break
            end
        end
        if self.isEnemy and v:getTeam() == 1 then
            flag = false
        end
        if flag then
            entitys[#entitys + 1] = v
        end
    end
    -- 中心坐标提到循环外
    local cx, cy, cz = center:getPoint():get()
    for i = #entitys, 1, -1 do
        if entitys[i] then
            -- 标量距离计算
            local ex, ey, ez = entitys[i]:getPoint():get()
            local dx, dy, dz = ex - cx, ey - cy, ez - cz
            if (dx * dx + dy * dy + dz * dz) < radius * radius then
                if call then
                    if call(entitys[i]) then
                        break
                    end
                else
                    self.selected[#self.selected + 1] = entitys[i]
                end
            end
        end
    end
    releaseEntitys(entitys)
    return self
end

-- 直线范围选择
-- @param origin 起点(entity 或 point)
-- @param direction 方向向量(Vector3,会归一化)
-- @param maxDist 最大距离
-- @param width 宽度
-- @param call 回调函数(可选)
-- @param comps 组件列表
function Selector:inLine(origin, direction, maxDist, width, call, comps)
    local ox, oy, oz = origin:getPoint():get()
    local _entitys = Game.curState().engine:getEntitiesWithComponent(comps[1])
    local entitys = acquireEntitys()
    for i, v in pairs(_entitys) do
        local flag = true
        for i = 2, #comps, 1 do
            if not v:has(comps[i]) then
                flag = false
                break
            end
        end
        if flag then
            entitys[#entitys + 1] = v
        end
    end
    direction = direction:normalize()
    local dir_x, dir_y, dir_z = direction.x, direction.y, direction.z
    local widthSq = (width + 150) * (width + 150)
    for i = #entitys, 1, -1 do
        local entity = entitys[i]
        if entity then
            local ex, ey, ez = entity:getPoint():get()
            local dx, dy, dz = ex - ox, ey - oy, ez - oz
            -- dist 必须开方(原代码语义:用模长投影非 dot 投影)
            local dist = math.sqrt(dx * dx + dy * dy + dz * dz)
            if dist < maxDist then
                local px, py, pz = ox + dir_x * dist, oy + dir_y * dist, oz + dir_z * dist
                local pdx, pdy, pdz = ex - px, ey - py, ez - pz
                if (pdx * pdx + pdy * pdy + pdz * pdz) < widthSq then
                    if call then
                        if call(entity) then
                            break
                        end
                    else
                        self.selected[#self.selected + 1] = entity
                    end
                end
            end
        end
    end
    releaseEntitys(entitys)
    return self
end

-- 移除死亡单位
function Selector:removeDead()
    for i = #self.selected, 1, -1 do
        if self.selected[i]:isDead() then
            table.remove(self.selected, i)
        end
    end
end

function Selector:clear()
    for k in pairs(self.selected) do self.selected[k] = nil end
end

function Selector:get()
    return self.selected
end

return Selector
