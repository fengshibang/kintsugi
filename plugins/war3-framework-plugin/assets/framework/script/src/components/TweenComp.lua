TweenComp = Component.create('TweenComp',{'from','to','duration','style','easing','onUpdate','onFinished'})

function TweenComp:__tostring()
    return "缓动组件"
end

function TweenComp:initialize(from, to, duration,style, easing, onUpdate, onFinished)
    self.from = from
    self.to = to
    self.easing = easing
    self.style = style 
    self.duration = duration
    self.onUpdate = onUpdate
    self.onFinished = onFinished

    self.tweens = {}
    self.currentIndex = 1
    self.elapsed = 0
end