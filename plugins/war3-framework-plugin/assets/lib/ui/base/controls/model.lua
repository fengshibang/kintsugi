local folderOfThisFile = (...):match("(.-)[^%/%.]+$")
require(folderOfThisFile .. "class")
require(folderOfThisFile .. "panel")

ui_class.model = extends(ui_class.panel) {
    --static
    model_map = {}, --存放所有存活的对象

    --public
    model = '', --模型路径

    color = 0xffffffff, --当前模型颜色

    texture_map = nil, -- 存放当前模型 所有已替换的id贴图

    size = 1, --缩放

    animation = 0, -- 全局动画id

    animation_loop = true, --动作循环

    animation_index = 0, --动画索引

    scale_x = 1, --缩放

    scale_y = 1, --缩放

    scale_z = 1, --缩放

    --private
    --模型 类型 和 基类
    _type = 'model', --fdf 中的模板类型

    _base = 'SPRITE', --fdf 中的控件类型

    --构建
    build = function(self)
        local panel
        if self.parent then
            self.parent_id = self.parent._id
        end

        self._id = japi.CreateFrameByTagName(self._base, self._name, self.parent_id, self._type, 0)
        if self._id == nil or self._id == 0 then
            ui_class.ui_base.destroy(self)
            ecs.debugError('创建模型失败')
            return
        end

        self.model_map[self._id] = self
        self.texture_map = {}

        self:init()
        self:set_model(self.model)
        self:set_animation(self.animation, self.animation_loop)
        self:set_progress(1)
        self:set_size(self.size)


        self:set_scale(self.scale_x, self.scale_y, self.scale_z)
        if rawget(self, 'animation_index') then
            self:set_animation_by_index(self.animation_index)
        end
        return self
    end,
    new = function(parent, model_path, x, y, width, height)
        local control = ui_class.model:builder
        {
            parent = parent,
            model = model_path,
            x = x,
            y = y,
            w = width,
            h = height,
        }
        return control
    end,


    destroy = function(self)
        if self._id == nil or self._id == 0 then
            return
        end
        self.model_map[self._id] = nil

        ui_class.ui_base.destroy(self)
    end,

    ---------------------
    --设置动画进度 百分比
    set_progress = function(self, rote)
        self.progress_value = rote
        japi.FrameSetAnimateOffset(self._id, rote)
    end,

    --设置动画
    set_animation = function(self, index, bool)
        japi.FrameSetAnimate(self._id, index, bool == true)
    end,


    --同单位一样的 按照索引播放指定动画  
    set_animation_by_index = function(self, index)
        japi.FrameSetAnimationByIndex(self._id, index)
    end,

    --设置模型路径
    set_model = function(self, path)
        self.model = path
        self.texture_map = {}
        japi.FrameSetModel(self._id, path, 0, 0)
    end,

    set_color = function(self, color)
        self.color = color
        japi.FrameSetModelColor(self._id, color)
    end,

    --设置模型缩放倍率
    set_size = function(self, size)
        local real_size = (self.relative_size or 1) * size
        japi.FrameSetModelSize(self._id, real_size)
    end,

    --获取模型缩放倍率
    get_size = function(self)
        return japi.FrameGetModelSize(self._id)
    end,

    --设置模型按xyz轴缩放
    set_scale = function(self, x, y, z)
        self.scale_x = x
        self.scale_y = y
        self.scale_z = z
        local size = (self.relative_size or 1)
        x = size * x
        y = size * y
        z = size * z
        japi.FrameSetModelScale(self._id, x, y, z)
    end,

    --设置模型旋转x轴
    set_rotate_x = function(self, value)
        japi.FrameSetModelRotateX(self._id, value)
    end,

    --设置模型旋转y轴
    set_rotate_y = function(self, value)
        japi.FrameSetModelRotateY(self._id, value)
    end,

    --设置模型旋转z轴
    set_rotate_z = function(self, value)
        japi.FrameSetModelRotateZ(self._id, value)
    end,

    --获取动画播放倍率
    get_speed = function(self)
        return japi.FrameGetModelSpeed(self._id)
    end,

    --设置动画播放倍率
    set_speed = function(self, value)
        japi.FrameSetModelSpeed(self._id, value)
    end,

    --设置模型与控件的偏移坐标
    set_model_offset = function(self, x, y)
        x = x / 1920 * 0.8
        y = (-y / 1080) * 0.6
        japi.FrameSetModelXY(self._id, x, y)
    end,

    --获取偏移坐标
    get_model_offset = function(self)
        local x = japi.FrameGetModelX(self._id)
        local y = japi.FrameGetModelY(self._id)

        x = x / 0.8 * 1920
        y = y / 0.6 * 1080 * -1
        return x, y
    end,

    replace_id_texture = function(self, image_path, _id)

        if self.texture_map[_id] == image_path then
            return
        end

        self.texture_map[_id] = image_path

        if image_path == '' then
            image_path = 'Transparent.tga'
        end
        japi.FrameSetModelTexture(self._id, image_path, _id)
    end,

    _color_map = {
        ['红'] = 0, ['蓝'] = 1, ['青'] = 2, ['紫'] = 3, ['黄'] = 4, ['橙'] = 5, ['绿'] = 6,
        ['粉'] = 7, ['灰'] = 8, ['淡蓝'] = 9, ['暗绿'] = 10, ['棕'] = 11,
    },

    --设置模型的队伍颜色 0 - 15  0为红色
    set_team_color = function(self, color_id)
        local path1, path2 = '', ''
        if color_id or color_id ~= '' then
            if type(color_id) == 'string' then
                color_id = self._color_map[color_id] or 0
            end
            path1 = string.format('ReplaceableTextures\\TeamColor\\TeamColor%02d.blp', color_id)
            path2 = string.format('ReplaceableTextures\\TeamGlow\\TeamGlow%02d.blp', color_id)
        end
        --队伍颜色
        self:replace_id_texture(path1, 1)
        --光晕贴图
        self:replace_id_texture(path2, 2)

    end,

    __tostring = function(self)
        local str = string.format('模型 %d', self._id or 0)
        return str
    end


}