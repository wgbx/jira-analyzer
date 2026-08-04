---
name: jira-writing-style
description: >
  Use when 需要按团队既有风格撰写 Jira（新建需求、子任务、操作项、可用性改进），
  或用户提到「按我们风格写 Jira」「写个可执行 Jira」「给我一版可直接贴 Jira 的描述」。
  该技能输出固定结构：Owner/POC、Business context、To do、UI 文案、验收点与评论建议。
---

# Jira 写作风格（团队版）

把模糊需求写成可执行 Jira，保持团队当前风格一致，减少来回澄清。

## 何时使用

- 用户说「按我们风格写 Jira」「帮我写一个任务」
- 只有一句背景，需要整理成可落地的 issue
- 需要统一 `Usability:` / `Operation:` 开头与描述结构

## 固定写法（必须遵守）

1. **Summary 前缀**
   - 产品体验类：`Usability: ...`
   - 运营/配置/流程类：`Operation: ...`
   - 句子直接写目标动作，不写空泛标题

2. **描述开头先给执行信息**
   - `Owner: @xxx (due: Mon D, YYYY)`
   - `Design: @xxx / N/A`
   - `FE: @xxx`
   - `BE POC: @xxx`
   - 有 Figma 链接就补：`Figma: ...`

3. **先写 Why，再写 What**
   - `Business context` / `Business use case`：2-4 句说清问题和价值
   - `To do`：按可执行条目列出，不写口号

4. **规则要写成条件流**
   - 多用 `If... then... otherwise...`
   - 明确候选集合、过滤条件、空集行为、兜底逻辑

5. **文案直接给最终文本**
   - `Title: ...`
   - `Tooltip: ...`
   - `Helper text: ...`

6. **评论区只做增量同步**
   - 记录新增约束、范围变化、测试结果（如 `test passed on Prod env`）

## 输出模板（直接填空）

```markdown
Summary
[Usability|Operation]: <一句话目标>

Description
Owner: @<owner> (due: <Mon D, YYYY>)
Design: @<design or N/A>
FE: @<fe>
BE POC: @<be>
Figma: <url or to be provided>

Business context:
<2-4 句：当前问题、影响人群、为什么现在做>

To do:
1) <改动点 1：模块/页面/开关>
2) <改动点 2：交互或业务规则>
3) <改动点 3：兼容与迁移，若有>
4) <改动点 4：埋点/监控/日志，若有>

Rules / Logic:
- Let candidate list be L.
- If <条件 A>, remove <对象> from L.
- If <条件 B>, remove <对象> from L.
- If L is empty, <无动作/降级行为>.
- If L is not empty:
  - If <已有窗口/流程存在>, append L to <existing flow>.
  - Otherwise, show <new flow>.

UI copy (if needed):
- Title: "<...>"
- Text: "<...>"
- Tooltip: "<...>"
- Helper text: "<...>"

Acceptance criteria:
- [ ] <场景 1：正常路径>
- [ ] <场景 2：边界条件>
- [ ] <场景 3：互斥约束/权限>
- [ ] <场景 4：回归影响面>

Out of scope:
- <本期不做项>
```

## 快速规则（写前自检）

- Summary 是否以 `Usability:` 或 `Operation:` 开头
- 是否包含 `Owner + due + FE + BE POC`
- 是否明确写了 `Business context`
- `To do` 是否可被工程直接拆解执行
- 是否给出明确文案而非「待定」
- 是否定义了验收条件而非主观描述

## 参考风格锚点

- `KAT-11847`: 简短背景 + end-to-end 最小改动目标
- `KAT-11701`: 条件流规则清晰、可直接实现
- `KAT-11731`: 文案细节和多层级默认值规则完整

## 常见问题

1. **问题：描述太短，只有一句需求**
   - 做法：先补齐 `Business context` 和 `To do`，至少写出目标、约束、验收

2. **问题：写了需求但不可测试**
   - 做法：把每个预期转成 checkbox 验收标准

3. **问题：实现细节写太死**
   - 做法：限制在业务规则和可见行为；底层实现用「可复用现有逻辑」表述
