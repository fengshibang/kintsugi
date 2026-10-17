# 触发器分析: {{TRIGGER_NAME}}

**源**: war3map.j 行 {{START_LINE}}-{{END_LINE}}
**事件**: {{EVENT_TYPE}}

---

## 功能描述

{{DESCRIPTION}}

## 原始代码

```jass
{{FULL_CODE}}
```

## JASS API 依赖

| API | 行偏移 | 用途 | Lua 替代 |
|-----|--------|------|----------|
{{API_TABLE}}

## 变量依赖

### 读取的全局变量

| 变量 | 行偏移 | 类型 |
|------|--------|------|
{{READ_VARS}}

### 写入的全局变量

| 变量 | 行偏移 | 类型 |
|------|--------|------|
{{WRITE_VARS}}

### Hashtable 操作

| Hashtable | Key | SubKey | 操作 | 行偏移 |
|-----------|-----|--------|------|--------|
{{HASHTABLE_OPS}}

## ECS 映射建议

- **事件**: {{EVENT}}
- **建议组件**: {{COMPONENTS}}
- **建议系统**: {{SYSTEMS}}
- **建议文件**: `{{FILE_HINT}}`

## 已知问题

{{ISSUES}}

## 迁移步骤建议

1. {{STEP_1}}
2. {{STEP_2}}
3. {{STEP_3}}

---

> 将以上分析粘贴给 `/war3-dev-guide`，用于创建对应的 ECS Lua 实现。
