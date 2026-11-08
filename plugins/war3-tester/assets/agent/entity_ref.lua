-- ============================================================================
-- entity_ref.lua - 单位引用（ref）映射与有效性校验
-- ============================================================================

local entity_ref = {}

-- 映射表：ref -> { handle = h, obj = obj, type_id = id, name = name }
local ref_cache = {}

local function to_handle(target)
    if type(target) == 'table' and target.handle then
        return target.handle, target
    end
    return target, nil
end

--- 为单位生成或获取稳定 ref
---@param unit_or_handle any 单位对象或底层 handle
---@return string ref
function entity_ref.get_ref(unit_or_handle)
    local h, obj = to_handle(unit_or_handle)
    if not h then return "nil" end

    local handle_id = 0
    if type(h) == 'number' then
        handle_id = h
    elseif GetHandleId then
        handle_id = GetHandleId(h)
    end

    local ref = "u" .. tostring(handle_id)
    local type_id = (GetUnitTypeId and GetUnitTypeId(h)) or (obj and obj.id) or 0
    local name = (GetUnitName and GetUnitName(h)) or (obj and obj.name) or "Unknown"

    ref_cache[ref] = {
        handle = h,
        obj = obj,
        type_id = type_id,
        name = name
    }
    return ref
end

--- 解析并校验 ref 是否有效（兼容 "u12345" 与 "u:12345"）
---@param ref string
---@return any|nil handle_or_obj, string|nil error_code
function entity_ref.resolve(ref)
    if not ref or type(ref) ~= 'string' then
        return nil, "INVALID_TARGET"
    end

    local norm_ref = ref:gsub("^u:", "u")
    local entry = ref_cache[norm_ref]
    if not entry then
        return nil, "STALE_REF"
    end

    local h = entry.handle
    -- 校验单位句柄是否已被 War3 回收或改变类型
    if GetUnitTypeId then
        local cur_type_id = GetUnitTypeId(h)
        if cur_type_id ~= entry.type_id then
            ref_cache[norm_ref] = nil
            return nil, "STALE_REF"
        end
    end

    -- 校验是否已死亡
    if entry.obj and entry.obj.isAlive then
        if not entry.obj:isAlive() then
            return nil, "STALE_REF"
        end
    elseif UnitAlive then
        if not UnitAlive(h) then
            return nil, "STALE_REF"
        end
    elseif IsUnitType and UNIT_TYPE_DEAD then
        if IsUnitType(h, UNIT_TYPE_DEAD) then
            return nil, "STALE_REF"
        end
    end

    -- 尝试返回 ECS 单位对象，没有则返回 handle
    if not entry.obj and Game and Game.curState and Game.curState().engine then
        entry.obj = Game.curState().engine:getEntityWithHandle(h)
    end

    return entry.obj or h, nil
end

--- 清理所有缓存
function entity_ref.clear()
    ref_cache = {}
end

return entity_ref
