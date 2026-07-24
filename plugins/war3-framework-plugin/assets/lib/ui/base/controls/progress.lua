
ui_class.progress = extends(ui_class.panel)
{
     --构造方法 派生进度条实例化对象所用
     new = function (parent, path, x, y, width, height,background)
          --底图是一张黑色的图片 这个可以写死
          local panel = ui_class.panel.new(parent,background, x, y, width, height) 
          panel.__index = ui_class.progress 
          
          --创建传进来路径的一张图片，用来显示进度条
          panel.texture = panel:add_texture(path, 0, 0, width, height)

          --创建一个文本控件 用来显示具体数值
          panel.text = panel:add_text('', 0, 0, width, height,8,4)

          return panel
     end,

     --设置进度条方法
     --@ self 对象自己
     --@ value: number 当前进度
     --@ max_value: number 最大进度
     set_value = function (self, value, max_value)
          local rate = 0
          if max_value > 0 then 
               rate = value / max_value
          end 

          rate = math.max(0,rate)

          --改变图层尺寸 为进度值百分比
          self.texture:set_control_size(self.w * rate, self.h)
          
          --local str = string.format(' %.0f / %.0f (%.2f)',value, max_value, rate)
          local str = string.format(' %.0f / %.0f',value, max_value)
          --设置文本内容
          self.text:set_text(str)
     end,
     destroy = function (self)
        if self._id == nil or self._id == 0 then 
            return 
        end

        self.texture:destroy()
        self.text:destroy()
        ui_class.panel.destroy(self)
    end,
    
    clear = function (self)
        self.text:set_text('')
        self.texture:set_position(self.offset_x,self.offset_y)
		self.texture:set_control_size(self.w,self.h)
    end,

    __tostring = function (self)
        local str = string.format('进度条 %d',self._id or 0)
        return str
    end
}

