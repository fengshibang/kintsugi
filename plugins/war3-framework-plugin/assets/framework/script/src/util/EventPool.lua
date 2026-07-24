-- ============================================================================
-- EventPool.lua - 福利事件抽签引擎(纯逻辑,零 jass 依赖,可桌面单测)
-- ============================================================================
-- 职责:
--   1. 从事件池按【稀有度权重】抽签(档内均分 → 档占比 = 档权重比)
--   2. 近期去重(排除最近 N 次触发过的事件)
--   3. 概率+保底判定(每关概率上货 + 每 guaranteeEvery 关保底 1 次)
--
-- 设计:与 jass/IdHelp/middleclass 完全解耦,事件列表与配置由调用方注入,
--       因此可在桌面 lua5.3 直接 require 单测(auto-test/test_event_pool.lua)。
--       真实事件数据(含物品 ID)由 src/data 层提供,运行时与引擎组合。
--
-- 票01:.scratch/welfare-redesign/issues/01-event-pool-engine.md
-- 配套:docs/福利机制重设计方案.md §3(触发) / §5(加权) / §6(去重)
-- ============================================================================

local EventPool = {}

-- 默认配置(与 spec §5/§3 一致)
local DEFAULT_CONFIG = {
    -- 稀有度/类型权重:抽到某档的概率 = 档权重 / 总权重
    weights = { common = 40, rare = 30, epic = 10, plot = 20 },
    dedupWindow = 4,       -- 去重窗口:排除最近 N 次触发过的事件
    probability = 0.25,    -- 每关上货概率
    guaranteeEvery = 3,    -- 保底:每 N 关至少 1 次(最多连续空 N-1 关)
}

--- 合并配置(深拷贝 weights,避免共享引用)
local function mergeConfig(cfg)
    local out = {}
    for k, v in pairs(DEFAULT_CONFIG) do out[k] = v end
    if cfg then
        for k, v in pairs(cfg) do
            if k == 'weights' and type(v) == 'table' then
                out.weights = {}
                for wk, wv in pairs(DEFAULT_CONFIG.weights) do out.weights[wk] = wv end
                for wk, wv in pairs(v) do out.weights[wk] = wv end
            else
                out[k] = v
            end
        end
    end
    return out
end

--- 创建池实例
--- @param events table 事件定义列表(数组),每项 {key=string, type=string, rarity=string, ...}
--- @param config table|nil 覆盖默认配置
--- @param rng function|nil 随机函数,返回 [0,1);默认 math.random(可注入用于确定性测试)
--- @return table pool
function EventPool.new(events, config, rng)
    local pool = {
        events = events,
        config = mergeConfig(config),
        _rng = rng or math.random,
        _recent = {},     -- 最近抽到的 key(FIFO 环形)
        _sinceLast = 0,   -- 自上次上货以来的空关数
    }
    return setmetatable(pool, { __index = EventPool })
end

--- 取候选事件(排除去重窗口内的 key);候选耗尽则退化为全池(保证不卡)
function EventPool:_candidates()
    local w = self.config.dedupWindow
    if not w or w <= 0 then
        return self.events
    end
    local recentSet = {}
    for i = 1, #self._recent do
        recentSet[self._recent[i]] = true
    end
    local cands = {}
    for _, e in ipairs(self.events) do
        if not recentSet[e.key] then
            cands[#cands + 1] = e
        end
    end
    if #cands == 0 then
        return self.events  -- 去重耗尽:退化全池
    end
    return cands
end

--- 权重抽签:档内均分(每事件权重 = 档权重 / 档内事件数)
--- 使得"抽到某档的概率" = 档权重比(不被档内事件数稀释)
--- @param cands table 候选事件列表
--- @return table 选中的 event
function EventPool:_weightedPick(cands)
    local weights = self.config.weights

    -- 统计候选中各档事件数
    local cnt = {}
    for _, e in ipairs(cands) do
        cnt[e.rarity] = (cnt[e.rarity] or 0) + 1
    end

    -- 每事件有效权重 + 累积总权重
    local entries = {}
    local total = 0
    for _, e in ipairs(cands) do
        local w = (weights[e.rarity] or 0) / cnt[e.rarity]
        entries[#entries + 1] = { e = e, w = w }
        total = total + w
    end

    if total <= 0 then
        -- 无权重(异常配置):均匀退化
        local idx = math.floor(self._rng() * #cands) + 1
        if idx > #cands then idx = #cands end
        return cands[idx]
    end

    local r = self._rng() * total
    local acc = 0
    for _, en in ipairs(entries) do
        acc = acc + en.w
        if r < acc then
            return en.e
        end
    end
    return entries[#entries].e  -- 浮点兜底
end

--- 推入 recent 并维持窗口大小(FIFO)
function EventPool:_pushRecent(key)
    local w = self.config.dedupWindow
    if not w or w <= 0 then return end
    self._recent[#self._recent + 1] = key
    while #self._recent > w do
        table.remove(self._recent, 1)
    end
end

--- 抽签(权重 + 去重),返回选中的 event。不改变 _sinceLast(由 onSettle 管)
--- @return table event
function EventPool:draw()
    local cands = self:_candidates()
    local e = self:_weightedPick(cands)
    self:_pushRecent(e.key)
    return e
end

--- 每关结算主入口:概率+保底判定。
--- 上货则抽签并返回 event、计数器归零;否则计数器+1、返回 nil。
--- @return table|nil event(上货时)或 nil(本关不上货)
function EventPool:onSettle()
    local cfg = self.config
    local stock = false
    -- 保底:已连续空 >= guaranteeEvery-1 关 → 本关必出
    if self._sinceLast >= cfg.guaranteeEvery - 1 then
        stock = true
    elseif self._rng() < cfg.probability then
        stock = true
    end

    if stock then
        self._sinceLast = 0
        return self:draw()
    else
        self._sinceLast = self._sinceLast + 1
        return nil
    end
end

return EventPool
