BulletComp = Component.create('BulletComp',{'filter','radius','objs','onHit'},{
filter = {"UnitModelComp"},
radius = 50,
objs = {}})

function BulletComp:__tostring()
    return '子弹组件'
end
