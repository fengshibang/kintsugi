-- types/point.lua — 坐标点
-- 提炼自 rouge_lua types/point.lua,剥 MoeHero 专属地形系统(getZ/add_block/is_block/find_path 等)
-- 设计:3D 坐标(x,y,z),提供距离/角度/极坐标移动/直角坐标移动等运算

local point = Types.point or class('Point')
Types.point = point

point[1] = 0
point[2] = 0
point[3] = 0

function point:__tostring()
    return ('{%.4f, %.4f, %.4f}'):format(self[1], self[2], self[3])
end

function point:initialize(x, y, z)
    self[1] = x
    self[2] = y
    self[3] = z or 0
end

-- 获取坐标
function point:get(getz)
    return self[1], self[2], getz and self[3] or self[3]
end

-- 复制点
function point:copy()
    return point(self[1], self[2], self[3])
end

-- 转换点(兼容 entity:getPoint() 接口)
function point:getPoint()
    return self
end

-- 移动点(覆盖坐标)
function point:move(dest)
    self[1], self[2], self[3] = dest:get()
end

-- 与单位/点的距离(2D)
function point:distance(u)
    local x1, y1 = self:get()
    local x2, y2 = u:getPoint():get()
    local x = x1 - x2
    local y = y1 - y2
    return math.sqrt(x * x + y * y)
end

-- 与单位/点的角度(度)
function point:angle(u)
    local x1, y1 = self:get()
    local x2, y2 = u:getPoint():get()
    return math.deg(math.atan(y2 - y1, x2 - x1))
end

-- 获得一条直线上的一点
-- @param target 目标点
-- @param rng 距离
-- @param flag 是否不超过终点
function point:getLineDest(target, rng, flag)
    if flag and self * target < rng then
        return target
    end
    local angle = self / target
    return self - {angle, rng}
end

-- 直角坐标移动(point + {x, y})
function point:__add(data)
    return point(self[1] + data[1], self[2] + data[2], self[3] + (data[3] or 0))
end

-- 极坐标移动(point - {angle, distance})
function point:__sub(data)
    local x, y = self:get()
    local angle, distance = data[1], data[2]
    return point(x + distance * math.cos(angle / 180 * math.pi), y + distance * math.sin(angle / 180 * math.pi))
end

-- 求两点距离(point * point)
function point:__mul(dest)
    local x1, y1 = self:get()
    local x2, y2 = dest:get()
    local x0, y0 = x1 - x2, y1 - y2
    return math.sqrt(x0 * x0 + y0 * y0)
end

-- 求两点方向(point / point)
function point:__div(dest)
    local x1, y1 = self:get()
    local x2, y2 = dest:get()
    return math.deg(math.atan(y2 - y1, x2 - x1))
end

return point
