# JASS → ECS 迁移 PRD

**生成日期**: {{DATE}}
**源文件**: map/war3map.j ({{TOTAL_LINES}} 行)
**生成工具**: jass-to-ecs-migration skill

---

## 1. 总览

| 指标 | 数值 |
|------|------|
| 总触发器函数 | {{TOTAL_TRIGGERS}} |
| 触发器事件类型 | {{EVENT_TYPES}} |
| 涉及库 | {{TOTAL_LIBS}} |
| 已知内存泄漏 | {{LEAK_COUNT}} |
| 已知 null 安全问题 | {{NULL_SAFETY_COUNT}} |
| PolledWait 调用 | {{POLLED_WAIT_COUNT}} |

### 事件分布

{{EVENT_DISTRIBUTION_TABLE}}

---

## 2. 已知问题清单

### 2.1 触发器永久禁用

{{DISABLED_TRIGGERS_LIST}}

### 2.2 Group 内存泄漏

{{GROUP_LEAKS_LIST}}

### 2.3 Hashtable 键冲突

{{HASHTABLE_CONFLICTS_LIST}}

---

## 3. 迁移计划

**迁移策略**: {{MIGRATION_STRATEGY}}

### 批次 1: {{BATCH_1_NAME}}

{{BATCH_1_TRIGGERS}}

### 批次 2: {{BATCH_2_NAME}}

{{BATCH_2_TRIGGERS}}

### 批次 3: {{BATCH_3_NAME}}

{{BATCH_3_TRIGGERS}}

---

## 4. 触发器分析卡片

### {{TRIGGER_NAME}}

**行号**: {{LINE_RANGE}}
**事件类型**: {{EVENT_TYPE}}
**功能描述**: {{DESCRIPTION}}
**复杂度**: {{COMPLEXITY}} (低/中/高)

**依赖 JASS API**:
{{API_LIST}}

**读取/写入变量**:
{{VARIABLE_LIST}}

**读取/写入 Hashtable**:
{{HASHTABLE_LIST}}

**已知问题**:
{{ISSUES}}

**建议 ECS 映射**:
- 事件: {{EVENT_MAPPING}}
- 组件: {{COMPONENT_MAPPING}}
- 系统: {{SYSTEM_MAPPING}}
- 建议文件: {{FILE_HINT}}

**注意事项**:
{{NOTES}}

> 使用 `/war3-dev-guide` 命令，基于以上分析创建对应的 ECS 组件/系统/Lua 文件。

---

*(重复 4.x 卡片，每个触发器一个)*
