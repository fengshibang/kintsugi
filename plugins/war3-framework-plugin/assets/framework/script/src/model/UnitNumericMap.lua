-- model/UnitNumericMap.lua — 属性集合(管理多个 UnitNumeric)
-- 提炼自 rouge_lua model/UnitNumericMap.lua
-- 设计:每个属性类型对应一个 UnitNumeric,支持装饰器(Decorator)模式

UnitNumericMap = class('UnitNumericMap')

-- 装饰器(用于 Equip/Buff 等临时加成)
UnitNumericDecorator = class('UnitNumericDecorator')

function UnitNumericDecorator:initialize()
    self.attribute = nil
    self.value = nil
end

---@param vm table 绑定的 vm 组件(属性变化时同步到 vm[name][type])
function UnitNumericMap:initialize(vm)
    self.vm = vm
    self.attributes = {}
    self.decorators = {}
end

-- 添加装饰器
function UnitNumericMap:addDecorator(und)
    self.decorators[und] = und.value
    local un = self:get(und.atrribute)
    un.decorator = un.decorator + und.value
end

-- 移除装饰器
function UnitNumericMap:removeDecorator(und)
    self.decorators[und] = nil
    local un = self:get(und.atrribute)
    un.decorator = un.decorator - und.value
end

-- 获取属性(不存在则创建)
---@param t string 属性类型
function UnitNumericMap:get(t)
    local attr = self.attributes[t]
    if not attr then
        attr = UnitNumeric(t, self)
        self.attributes[t] = attr
        attr.onUpdate = function(un)
            self.vm[t] = self.vm[t] or {}
            self.vm[t][un.type] = un.value
        end
    end
    return attr
end

function UnitNumericMap:forEach(callbackfn, thisArg)
    for k, v in pairs(self.attributes) do
        callbackfn(v, k, thisArg)
    end
end

function UnitNumericMap:reset()
    self.decorators = nil
    local cb = function(value, key)
        value = nil
    end
    self:forEach(cb)
end
