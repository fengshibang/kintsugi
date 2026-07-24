local storm = require 'jass.storm'
local japi =  require 'jass.japi'

local instance 

local function init()

    local str = [[4d444c585645525304{6}2003{4}4d4f444c7401{4}4a75737420416e6f74686572204d6f64656c{644}4d79643dafdd0bbdc89a2cbd{8}b8c4193dec61023d{8}96{6}5345515384{6}5374616e64{150}4d01{4}3505{36}4d79643dafdd0bbdc89a2cbd{8}b8c4193dec61023d{8}4d544c533{7}3{7}e703{5}1{6}4c41595301{6}1c{14}71{14}ffffffff{12}803f544558530c01{12}54657874757265735c426c61636b33322e626c7{489}47454f533c01{4}3c01{4}5652545804{6}9a9999b1cdccccb{5}fac3aca32a3d{12}fac3ada32a3d6488633d{4}fac310281bb06488633d{4}fac34e524d5304{26}803f{20}803f{20}803f{20}803f5054595001{7}4{6}50434e5401{7}6{6}5056545806{7}3{7}100030001000200474e445804{14}4d54474301{7}1{6}4d41545301{38}76348e3d9a9999b1cdccccb{5}fac3ada32a3d6488633d{4}fac301{6}76348e3d9a9999b1cdccccb{5}fac3ada32a3d6488633d{4}fac35556415301{6}5556425304{18}803f{12}803f{12}803f{12}803f424f4e4568{6}6{7}44656661756c7420426f6e65{144}ffffffff0001{12}ffffffff504956540c{30}]]
    str = str:gsub('%{(%d+)%}', function (len) return string.rep('0', len) end)
    local s = {}
    for i = 1, #str, 2 do 
       local byte = string.format("%d", '0x' .. str:sub(i, i + 1))
       s[#s + 1] = string.char(byte)
    end 
    storm.save("ui\\_model_backdrop.mdx", table.concat(s))

    instance = ui_class.model:builder 
    {
       parent_id = japi.FrameGetParent(japi.FrameGetPortrait()),
       x = 0,
       y = 1050,
       w = 32,
       h = 32,
       model = [[ui\\_model_backdrop.mdx]],
       scale_x = 19,
       scale_y = 10.5,
    }
    instance:set_alpha(0.02)
end 


ui_class.model2 = extends(ui_class.model){

    ignore = true,

    color_id = 0,

     --构建
     build = function (self)
        if instance == nil or instance._id == nil then 
            init()
        end 
        local panel 
        if self.parent then 
            self.parent_id = self.parent._id
        end 
       
        self._id = japi.FrameAddModel(self.parent_id)
        if self._id == nil or self._id == 0 then 
            ui_class.ui_base.destroy(self)
            ecs.debugError('创建模型2失败')
            return 
        end
        
        self.texture_map = {}
        self:reset()
        
        return self
    end,

    reset = function (self)
        self:set_model(self.model, self.color_id)
        self:set_animation(self.animation, self.animation_loop)
        self:set_progress(1)
        self:set_size(self.size)
        self:init()
   
        self:set_scale(self.scale_x, self.scale_y, self.scale_z)

        self:set_rotate_x(self.rotate_x)
        self:set_rotate_y(self.rotate_y)
        self:set_rotate_z(self.rotate_z)
        self:set_model_offset(self.offset_x, self.offset_y)
        if rawget(self, 'animation_index') then 
            self:set_animation_by_index(self.animation_index)
        end 
    end,

    --设置镜头位置  
    set_camera_source = function (self, x, y, z)
        japi.FrameSetModelCameraSource(self._id, x, y, z)
    end,

    --设置镜头目标位置
    set_camera_target = function (self, x, y, z)
        japi.FrameSetModelCameraTarget(self._id, x, y, z)
    end,


    --设置 忽略鼠标点击事件  默认是 true 填 false 可以 屏蔽鼠标点击
    set_ignore_trackevents = function (self, bool)
        self.ignore = bool 
        japi.FrameSetIgnoreTrackEvents(self._id, bool)
    end,

    --设置模型 颜色id 是 0~15 = 玩家颜色
    set_model = function (self, path, color_id)
        japi.FrameSetModel2(self._id, path, color_id or 0)
    end,

    --设置模型在 场景内的坐标  跟镜头位置有关系
    set_model_position = function (self, x, y, z)
        japi.FrameSetModelX(self._id, x)
        japi.FrameSetModelY(self._id, y)
        japi.FrameSetModelZ(self._id, z)
    end,

    --获取模型位置
    get_model_position = function (self)
        return japi.FrameGetModelX(self._id), japi.FrameGetModelY(self._id), japi.FrameGetModelZ(self._id)
    end,
    
}