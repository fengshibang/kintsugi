-- FourCC 工具：将 4 字符字符串转换为整数 ID（War3 物编 ID 约定）
-- 统一替代各 system 中复制的 FourCC 私有副本（对齐 unitAlive 收敛模式）
local function FourCC(s)
    return string.byte(s, 1) * 0x1000000 + string.byte(s, 2) * 0x10000 + string.byte(s, 3) * 0x100 + string.byte(s, 4)
end

return FourCC
