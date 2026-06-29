# Rubric — <case-id>

被测会话应……（一句话目标）。

## CHECK skill-invoked
被测会话是否调用了 `Skill` 工具加载目标 skill。
判定依据：评审 prompt 中「被测会话调用的工具」列表里是否出现 `Skill`。
（基线 `--disallowedTools Skill` 应为 fail → 这一项的 baseline delta 就是 skill 触发的增量。）

## CHECK <your-check-id>
<判定依据：明确、二元可判>

## CHECK <your-check-id>
<判定依据>
