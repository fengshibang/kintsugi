Vector3 = class("Vector3")

function Vector3:initialize(x, y, z)
    self.x = x
    self.y = y
    self.z = z
end

--线性插值
function Vector3:lerp(v3, t)
    return self + (v3 - self) * lume.clamp(t, 0, 1)
end


--弧形插值
function Vector3.slerp(lhs, rhs, t)
    local lhsMag = lhs:magnitude()
    local rhsMag = rhs:magnitude()
    if (lhsMag < Vector3.epsilon or rhsMag < Vector3.epsilon) then
        return lhs:lerp(rhs, t)
    end
    local lerpMag = lume.lerp(lhsMag, rhsMag, t)
    local dot = lhs:dot(rhs) / (lhsMag * rhsMag)
    if (dot > 1 - Vector3.epsilon) then
        return lhs:lerp(rhs, t)
    elseif (dot < -1 + Vector3.epsilon) then
        local lhsNor = lhs / lhsMag
        local axis = lhsNor:OrthoNormalVectorFast()

        local m
        m.SetAxisAngle(axis, math.pi * t)
    else
        local axis = lhs:cross(rhs)
        local lhsNor = lhs / lhsMag
        axis = axis:normalize()
        local angle = math.acos(dot) * t

        local m
        m.SetAxisAngle(axis, angle)
    end
end

--axis = Vector3(-1, 0, 0)) 反方向
--axis = Vector3(0, 1, 0)) 绕X旋转
--axis = Vector3(0, 0, 1)) 绕Y旋转
function Vector3:RotateAround(point, axis, angle)
    local q = { x = 0, y = 0, z = 0, w = 0 }
    local mag = axis:magnitude()
    if (mag > Vector3.epsilon) then
        local halfAngle = Deg2Rad(angle) * 0.5
        q.w = math.cos(halfAngle)
        local s = math.sin(halfAngle) / mag
        q.x = s * axis.x
        q.y = s * axis.y
        q.z = s * axis.z
    end

    local dif = self - point

    local x = q.x * 2
    local y = q.y * 2
    local z = q.z * 2
    local xx = q.x * x
    local yy = q.y * y
    local zz = q.z * z
    local xy = q.x * y
    local xz = q.x * z
    local yz = q.y * z
    local wx = q.w * x
    local wy = q.w * y
    local wz = q.w * z

    local res = Vector3(
    (1 - (yy + zz)) * dif.x + (xy - wz) * dif.y + (xz + wy) * dif.z,
    (xy + wz) * dif.x + (1 - (xx + zz)) * dif.y + (yz - wx) * dif.z,
    (xz - wy) * dif.x + (yz + wx) * dif.y + (1 - (xx + yy)) * dif.z)
    return point + res
end

function Vector3.MoveTowards(lhs, rhs, clampedDistance)
    local delta = rhs - lhs
    local sqrDelta = delta:dot(delta)
    if sqrDelta > sqrClampedDistance then
        local deltaMag = math.sqrt(sqrDelta)
        if deltaMag > Vector3.epsilon then
            return lhs + delta / deltaMag * clampedDistance
        else
            return lhs
        end
    else
        return rhs
    end
end

--点积
function Vector3:dot(v3)
    return self.x * v3.x + self.y * v3.y + self.z * v3.z
end

--叉乘
function Vector3:cross(v3)
    return Vector3(
    self.y * v3.z - self.z * v3.y,
    self.z * v3.x - self.x * v3.z,
    self.x * v3.y - self.y * v3.x
    )
end

--沿着法线反射向量。
function Vector3.Reflect(inDirection, inNormal)
    return -2 * Vector3.dot(inNormal, inDirection) * inNormal + inDirection
end

function Vector3:magnitude()
    return math.sqrt(self.x ^ 2 + self.y ^ 2 + self.z ^ 2)
end

--和v3:dot(v3) 效果一样
function Vector3:sqrMagnitude()
    return self.x ^ 2 + self.y ^ 2 + self.z ^ 2
end

function Vector3:normalized()
    local m = self:magnitude()
    if m > 0 then
        return self / m
    else
        return Vector3(0, 0, 0)
    end
end

function Vector3:normalize()
    local m = self:magnitude()
    if m then
        self = self / m
    end
    return self
end
--[[计算3d角度
function Vector3.angle(from, to)
    --dot(点积)计算夹角，然后使用acos(反余弦函数)弧度，弧度再deg(弧度转角度)成角度。
    return math.deg(math.acos(lume.clamp(Vector3.dot(to:normalized(), from:normalized()), -1, 1)))
end]]

-- 计算2d角度,没有计算Z轴
-- 取值范围-180 180
function Vector3.angleBetween(from, to)
    return math.deg(math.atan(to.y - from.y, to.x - from.x))
end

function Vector3.distance(a, b)
    return (a - b):magnitude()
end

function Vector3:OrthoNormalVectorFast()
    if (math.abs(self.z) > Vector3.k1OverSqrt2) then
        local a = self.y * self.y + self.z * self.z
        local k = 1 / math.sqrt(a)
        return Vector3(0, -self.z * k, self.y * k)
    else
        local a = self.x * self.x + self.y * self.y
        local k = 1 / math.sqrt(a)
        return Vector3(-self.y * k, self.x * k, 0)
    end
end

function Vector3.__add(a, b)
    if (type(a) ~= 'table' or type(b) ~= 'table') then
        print(tostring(debug.traceback()) .. "\n")
        error("bad argument")
        return
    end
    return Vector3(a.x + b.x, a.y + b.y, a.z + b.z)
end

function Vector3.__sub(a, b)
    if (type(a) ~= 'table' or type(b) ~= 'table') then
        print(tostring(debug.traceback()) .. "\n")
        error("bad argument")
        return
    end
    return Vector3(a.x - b.x, a.y - b.y, a.z - b.z)
end

function Vector3.__mul(a, b)
    if (type(a) == 'table' and type(b) == "number") then
        return Vector3(a.x * b, a.y * b, a.z * b)
    elseif (type(b) == 'table' and type(a) == "number") then
        return Vector3(a * b.x, a * b.y, a * b.z)
    elseif (a.class.name == 'Vector3' and b.class.name == 'Quaternion') then
        local x = b.x * 2
        local y = b.y * 2
        local z = b.z * 2
        local xx = b.x * x
        local yy = b.y * y
        local zz = b.z * z
        local xy = b.x * y
        local xz = b.x * z
        local yz = b.y * z
        local wx = b.w * x
        local wy = b.w * y
        local wz = b.w * z
        return Vector3((1 - (yy + zz)) * a.x + (xy - wz)        * a.y + (xz + wy)        * a.z
        , (xy + wz)        * a.x + (1 - (xx + zz)) * a.y + (yz - wx)        * a.z
        , (xz - wy)        * a.x + (yz + wx)        * a.y + (1 - (xx + yy)) * a .z
        )
    else
        print(tostring(debug.traceback()) .. "\n")
        error("bad argument")
    end
end

function Vector3.__div(a, b)
    if (type(a) == 'table' and type(b) == "number") then
        return Vector3(a.x / b, a.y / b, a.z / b)
    else
        print(tostring(debug.traceback()) .. "\n")
        error("bad argument")
    end
end

function Vector3.__tostring(v)
    return v.x .. ", " .. v.y .. ", " .. v.z
end

function Vector3.__eq(a, b)
    return (a.x == b.x and a.y == b.y and a.z == b.z)
end

function Vector3.__le(a, b)
    return a:magnitude() <= b:magnitude()
end

function Vector3.__lt(a, b)
    return a:magnitude() < b:magnitude()
end

Vector3.down = Vector3(0, 0, -1)
Vector3.up = Vector3(0, 0, 1)
Vector3.left = Vector3(-1, 0, 0)
Vector3.right = Vector3(1, 0, 0)
Vector3.forward = Vector3(0, 1, 0)
Vector3.back = Vector3(0, -1, 0)
Vector3.one = Vector3(1, 1, 1)
Vector3.zero = Vector3(0, 0, 0)
Vector3.epsilon = 0.00001
Vector3.k1OverSqrt2 = math.sqrt(0.5)

return Vector3