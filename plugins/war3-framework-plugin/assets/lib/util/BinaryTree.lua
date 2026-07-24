-- 节点定义
local function TreeNode(value)
    return {
        value = value,
        left = nil,
        right = nil
    }
end

-- 二叉树定义
local BinaryTree = {}
BinaryTree.__index = BinaryTree

-- 创建二叉树
function BinaryTree.new()
    return setmetatable({ root = nil }, BinaryTree)
end

-- 添加节点到二叉树，可选指定父节点
function BinaryTree:add(value, parentValue)
    local newNode = TreeNode(value)

    -- 如果没有根节点，则新节点成为根节点
    if not self.root then
        if parentValue then
            error("Cannot specify parent for the root node.")
        else
            self.root = newNode
            return
        end
    end

    local function insertNode(currentNode)
        if currentNode.value == parentValue then
            -- 如果左子节点不存在，就添加到左边，否则添加到右边
            if not currentNode.left then
                currentNode.left = newNode
            elseif not currentNode.right then
                currentNode.right = newNode
            else
                error("Both child nodes of " .. parentValue .. " are occupied.")
            end
            return true
        elseif currentNode.left and insertNode(currentNode.left) then
            return true
        elseif currentNode.right and insertNode(currentNode.right) then
            return true
        end
        return false
    end

    if parentValue and not insertNode(self.root) then
        error("Parent value " .. parentValue .. " not found.")
    end
end

-- 遍历打印
function BinaryTree:traverse(node, level)
    node = node or self.root
    level = level or 0
    if node then
        self:traverse(node.right, level + 1)
        print(string.rep("  ", level) .. node.value)
        self:traverse(node.left, level + 1)
    end
end


return BinaryTree