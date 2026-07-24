local node = {}
local list = {}


function node.new(val)
    return {
        data = val,
        next = nil
    } -- data表示数据域 next表示指针域
end

-- insert:在某个节点后插入新节点
function node.insert(n, val)

    n.next = node.new(val)
end

function list.new()
    return {
        head = nil
    } -- head为头节点
end

function list.push_back(l, val) -- 传入链表和值

    -- 判断头结点是否为空
    -- 为空，新节点为头节点
    -- 如果不为空，找到最后一个节点，在最后一个节点插入新元素

    if l.head then

        local n = l.head
        while n.next do
            n = n.next -- 往后指
        end
        node.insert(n, val)

    else -- 为空

        l.head = node.new(val)
    end

end
function list.print(l)
    local n = l.head
    while n do
        print(n.data)
        n = n.next
    end
end

function list.count(l)
    local n = l.head
    local i = 0
    while n do
        i = i + 1
        n = n.next
    end
    return i
end


function list.pop_front(l)

    if l.head then
        local t = l.head
        l.head = l.head.next
        return t
    else
        return nil
    end

end
function list.remove(l, value)
    local next = l.head
    local front = l.head
    local temp = {}
    while front do
        if front.data == value then
            temp = front
            next.next = front.next
            return temp
        end
        next = front
        front = front.next
    end

end
function list.sort1(l)
    local temp = l.head
    while temp.next do
        local front = temp

        while front do
            if front.data > temp.data then
                front.data, temp.data = temp.data, front.data
            end
            front = front.next
        end
        temp = temp.next
    end
end

function list.insert(l, i, val)

    local temp = l.head
    local front = l.head

    -- 插入头节点
    if i == 1 then
        local t = l.head.next
        local new = node.new(val)
        l.head = new
        new.next = t
    end

    -- 身体
    for i = 1, i - 1 do
        front = temp
        temp = temp.next
    end
    local new = node.new(val)
    front.next = new
    new.next = temp

end

return  list
