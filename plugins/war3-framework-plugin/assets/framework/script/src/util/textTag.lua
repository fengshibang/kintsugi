-- 漂浮文字工具：在单位头顶显示漂浮文字（ac.texttag 统一封装）
-- 替代各 system 中复制的 createTextTag 私有副本（对齐 unitAlive/fourcc 收敛模式）
local function createTextTag(text, unit, life)
    ac.texttag {
        string = text,
        target = unit,
        zoffset = 0,
        size = 20,
        life = life or 2.0,
        show = ac.texttag.SHOW_ALL,
    }
end

return createTextTag
