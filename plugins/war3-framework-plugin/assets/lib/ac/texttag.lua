
local jass = require 'jass.common'
local dbg = require 'jass.debug'

local texttag = {}
setmetatable(texttag, texttag)

--结构
local mt = {}
texttag.__index = mt

--可见性常量
mt.SHOW_NONE = 0
mt.SHOW_ALL = 1
mt.SHOW_SELF = 2
mt.SHOW_ALLY = 4
mt.SHOW_FOG = 8 --是否在迷雾内可见，默认为不可见

--类型
mt.type = 'texttag'

--句柄
mt.handle = 0

--玩家
mt.player = nil

--文本内容
mt.string = '无文本'

--文本大小
mt.size = 10

--初始位置
mt.position = nil

--Z轴偏移（仅在绑定目标时有效）
mt.zoffset = 0

--速度
mt.speed = 0

--角度
mt.angle = 90

--颜色
	mt.red = 100
	mt.green = 100
	mt.blue = 100
	mt.alpha = 100

--生命周期
mt.life = 3

--淡化
mt.fade = 2

--永久性
mt.permanent = false

--可见性
mt.show = texttag.SHOW_ALL

--绑定单位
mt.target = nil

--弹跳
mt.jump_size = 10
mt.jump_speed = 0
mt.jump_a = 0

--设置文本
function mt:setText(string, size)
	if string then
		self.string = string
	end
	jass.SetTextTagText(self.handle, string or self.string, (size or self.size) * 0.0023)
end

--设置位置
function mt:set_position(position)
	-- 如果有 target（绑定单位），使用 SetTextTagPosUnit 跟随单位位置
	if self.target and self.target:has('UnitModelComp') and self.target.handle then
		jass.SetTextTagPosUnit(self.handle, self.target.handle, self.zoffset or 0)
	else
		self.position = position or self.position or Types.point(0,0)
		jass.SetTextTagPos(self.handle, (position or self.position):getPoint():get())
	end
end

--设置颜色
function mt:setColor(red, green, blue, alpha)
	jass.SetTextTagColor(self.handle, (red or self.red) * 2.55, (green or self.green) * 2.55, (blue or self.blue) * 2.55, (alpha or self.alpha) * 2.55)
end

--设置速度
function mt:setSpeed(angle, speed)
	local angle = angle or self.angle
	local speed = speed or self.speed
	jass.SetTextTagVelocity(self.handle, speed * 0.071 * math.cos(math.rad(angle)) / 128, speed * 0.071 * math.sin(math.rad(angle)) / 128)
end

--设置生命周期
function mt:set_life_time(fade, life)
	jass.SetTextTagFadepoint(self.handle, fade or self.fade)
	jass.SetTextTagLifespan(self.handle, life or self.life)
end

--设置永久性
function mt:setPermanent(permanent)
	jass.SetTextTagPermanent(self.handle, permanent or self.permanent)
end

--设置所有者
function mt:setPlayer(player)
	if player then
		self.player = player
	end
end

local function has_flag(flag, bit)
	return flag % (bit * 2) - flag % bit == bit
end

--设置可见性
function mt:setShow(show)
	local show = show or self.show
	local flag = false
	local function is_visible()
		if self.target and self.target:has('UnitModelComp') then 
			return self.target:isVisible(PlayerObj.static.self)
		else 
			return PlayerObj.static.self:isVisible(self.position)
		end
	end
	if has_flag(show, texttag.SHOW_FOG) or is_visible() then
		if has_flag(show, texttag.SHOW_ALL) then
			flag = true
		else
			if has_flag(show, texttag.SHOW_SELF) and PlayerObj.static.self == self.player then
				flag = true
			else
				if has_flag(show, texttag.SHOW_ALLY) and not self.player:isEnemy(PlayerObj.static.self) then
					flag = true
				end
			end
		end
	end
	if(show == texttag.SHOW_NONE)then
		flag = false;
	end

	jass.SetTextTagVisibility(self.handle, flag)

	return flag
end

--创建漂浮文字
local gchash = 0
function texttag:__call(texttag)
	setmetatable(texttag, self)
	texttag.handle = jass.CreateTextTag()

	texttag:setText()
	texttag:set_position()
	texttag:setColor()
	texttag:setSpeed()
	texttag:set_life_time()
	texttag:setPermanent()

	if texttag.target then
		gchash = gchash + 1
		dbg.gchash(texttag, gchash)
		texttag.gchash = gchash
		self.group[texttag] = true
	end
	--show 要在 addTarget 之后
	texttag:setShow()
	
	return texttag
end

--移除漂浮文字
function mt:remove()
	if self.removed then
		return
	end
	self.removed = true
	jass.DestroyTextTag(self.handle)
	self.handle = nil

	texttag.group[self] = nil
end

texttag.group = {}

ac.texttag = texttag

return texttag