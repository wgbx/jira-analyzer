---
name: jira-writing-style
description: >
  Use when 需要按团队既有风格撰写或改写 Jira（新建需求、子任务、操作项、可用性/平台化改进），
  或用户提到「按我们风格写 Jira」「写个可执行 Jira」「给我一版可直接贴 Jira 的描述」，
  或要把调查结论/方案从需求里拿掉、按问题+待办重写，
  或创建 Jira 时需要决定是否做成子任务、挂在谁下面。
---

# Jira 写作风格（团队版）

把模糊需求写成可执行 Jira，保持团队当前风格一致，减少来回澄清。

**需求暴露问题和待办，不携带已查到的结论和做事方式。**

## 何时使用

- 用户说「按我们风格写 Jira」「帮我写一个任务」
- 只有一句背景，需要整理成可落地的 issue
- 需要统一 `Usability:` / `Operation:` / `Scalability:` 开头与描述结构
- 已有调查/脚本/数字，但用户要的是需求，不是结论文档

## 固定写法（必须遵守）

1. **Summary 前缀**
   - 产品体验类：`Usability: ...`
   - 运营/配置/流程类：`Operation: ...`
   - 平台效率 / 资产治理：`Scalability: ...`（这是标题前缀，不是「必须建成 11539 的子任务」）
   - 写问题或目标，不写已定方案（❌ `retire unused keys and keep audit`；✅ `i18n catalog has no retire lifecycle`）

2. **描述开头先给执行信息**
   - `Owner: @xxx (due: Mon D, YYYY)`
   - `Design: @xxx / N/A`
   - `FE: @xxx`
   - `BE POC: @xxx`
   - 有 Figma 链接就补：`Figma: ...`

3. **先写 Why，再写 What**
   - `Business context`：先价值（平台化 / 性能 / 共享资产为什么不能无限膨胀），再问题
   - 问题用「经常忘记 / 没移除」，不用「从未 / never」
   - `To do`：审计、确认、下线、验收这类待办；不写已跑出的数字、脚本名、分批 PR 计划
   - 已查结论放到评论或 PR，不写进需求正文

4. **章节按需，不要套满模板**
   - 必有：Owner 行、`Business context`、`To do`、`Acceptance criteria`
   - `Rules / Logic`：仅当产品/交互有真实分支（If…then…、候选集过滤、空集行为）时才写。清理 / 审计 / 治理类线性待办不要套 If/then
   - `UI copy`：仅当本票要改可见文案时才写
   - `Out of scope`：有明确不做项时才写

5. **文案直接给最终文本**（若本票改 UI 文案）
   - `Title: ...`
   - `Tooltip: ...`
   - `Helper text: ...`

6. **评论区只做增量同步**
   - 记录新增约束、范围变化、测试结果（如 `test passed on Prod env`）
   - 扫描基线、脚本、分批删除计划也放这里，不回写需求

7. **层级：创建子任务前必须先问父项**
   - **先确认再创建。** 要建成 Subtask 时，必须先问用户挂在哪条下面，得到明确 issue key 后再 POST。不要猜 `11539` / 当前 Q3 故事 / Relates 对象的父项
   - 没确认 → 默认建成独立「任务」，无 parent
   - 用户说关联到某条（如 `11874`）→ 只 Relates，**不要**顺便挂它的父项
   - 双挂会乱：同一条既是 11539 的子任务又 Relates 到 11539 的另一条子任务
   - Jira **调不了**：Subtask 不能改成任务、也不能换父项类型。挂错只能新建 + 删旧（换 key）。所以父项只能问，不能先挂再改

## 输出模板（按需删节）

```markdown
Summary
[Usability|Operation|Scalability]: <问题或目标，不是已定方案>

Description
Owner: @<owner> (due: <Mon D, YYYY>)
Design: @<design or N/A>
FE: @<fe>
BE POC: @<be>
Figma: <url or to be provided>

Business context:
<先价值：平台化 / 性能 / 为什么现在做>
<再问题：经常发生什么、影响谁；不用「从未」>

To do:
1) <待办 1：审计 / 确认 / 改什么面>
2) <待办 2>
3) <待办 3：验收相关，若有>

Rules / Logic:   ← 仅当有真实分支时保留；否则整节删掉
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
- [ ] <场景 3：回归影响面>

Out of scope:
- <本期不做项>
```

## 快速规则（写前自检）

- Summary 是否以 `Usability:` / `Operation:` / `Scalability:` 开头，且没有把方案写进标题
- 是否包含 `Owner + due + FE + BE POC`
- `Business context` 是否先价值再问题，且没有「从未 / never」
- 需求里是否出现了已查数字、脚本名、PR 切分——有则挪到评论
- `To do` 是否可被工程拆解，但仍是待办不是结案
- 有真实分支才写 `Rules / Logic`；没有就不要
- 改 UI 时才给最终文案；有验收，不写主观「更好」
- 要建 Subtask？父项 key 是否已经用户口头确认？没有 → 先问，或建成独立任务

## 参考风格锚点

- `KAT-11847`: 简短背景 + end-to-end 最小改动目标
- `KAT-11701`: 条件流规则清晰、可直接实现（这种票才需要 `Rules / Logic`）
- `KAT-11731`: 文案细节和多层级默认值规则完整
- `KAT-11909`: 平台化价值在前 + 问题 + To do + 验收；无 Rules/Logic；独立任务，只 Relates `11874`，不挂 `11539`

## 常见问题

1. **问题：描述太短，只有一句需求**
   - 做法：先补齐 `Business context` 和 `To do`，至少写出目标、约束、验收

2. **问题：写了需求但不可测试**
   - 做法：把每个预期转成 checkbox 验收标准

3. **问题：实现细节写太死 / 把调查当需求**
   - 做法：正文只留问题和待办。扫描结果、脚本、分批计划、gzip 数字放评论或 PR

4. **问题：没有分支却写了 Rules / Logic**
   - 做法：整节删掉。If/then 只服务真实产品规则，不服务「显得完整」

5. **问题：用「从未被移除」这类绝对表述**
   - 做法：改成「经常忘记移除 / 没移除」。需求描述现状习惯，不断言从未发生

6. **问题：关联了 11874 却又建成 11539 的子任务 / 没问就挂了父项**
   - 做法：停。先问「挂在哪条下面？」。没答就建成独立任务。先例：`KAT-11879`、`KAT-11909`

## 红旗（写完再看一眼）

- 标题或 To do 已经是「删 unused + 留审计脚本」这类结案
- `Business context` 里出现具体条数、百分比、命令名
- 线性清理票仍有 `Let candidate list be L`
- 出现 never / 从未 / always / 从不
- 价值（平台化、载荷、生命周期）埋在问题后面或干脆没有
- 未问用户就设了 parent / 建成 Subtask
- 新票 parent=`11539` 且同时又 Relates 到 11539 的另一条子任务
