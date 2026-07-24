HeroComp = Component.create('HeroComp')

function HeroComp:initialize()
    self.equips = {}
    self.bank = {}
end


function HeroComp:__tostring()
    return '英雄组件'
end
