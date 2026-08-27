---
name: create-jira
description: >
  Use when 需要按团队风格撰写并创建/改写 Jira（新建需求、子任务、操作项、可用性改进），
  或用户提到「创建 Jira」「建个票」「按我们风格写 Jira」「写个可执行 Jira」、
  「给我一版可直接贴 / 发到 Jira 的描述」，或要把调查结论从需求里拿掉、按问题+待办重写，
  或创建时需要决定是否做成子任务、挂在谁下面、是否 Relates，
  或对已有票做文案小改（禁止整段覆盖）。
  覆盖：写作风格 + 实际建票（POST）+ 安全改票。
---

# 创建 Jira（写作风格 + 建票）

把模糊需求写成可执行 Jira，并按确认结果创建 issue。

**正文只暴露具体问题 + 可执行产品待办；不写调查结论、不写官话、不写「云里雾里」的背景。**

## 何时使用

- 「创建 Jira」「建个票」「按我们风格写」「帮我写一个任务」
- 只有一句背景，需要整理成可落地的 issue
- 需要统一 `Usability:` / `Operation:` / `Scalability:` 前缀与描述结构
- 已有票要改一两句文案（**只改目标句，见下方「改已有票」**）

## 流程概览（必须）

1. **先对齐文案**：输出可贴草稿，等用户审查；未说「可以建 / 创建」→ 不 POST
2. **确认层级**：要建 Subtask 先问父项 key；未确认 → 独立「任务」
3. **创建**：用户明确同意后再 POST
4. **迭代改文案**：用户改意见时，先给修订稿再写回；写回时遵守「改已有票」铁律

## 固定写法（必须遵守）

1. **Summary 前缀**
   - 产品体验：`Usability: ...`
   - 运营/配置/流程：`Operation: ...`
   - 平台效率 / 资产治理：`Scalability: ...`（标题前缀 ≠ 必须挂某父项）
   - 写问题或目标，不写已定方案  
     ❌ `Build an extensible social solution`  
     ✅ `Social links lack a reusable extension model`

2. **描述开头：执行信息（缺的写 TBD，不要编）**
   - `Owner: @xxx (due: Mon D, YYYY)`
   - `Design: @xxx / TBD`
   - `FE: @xxx`
   - `BE POC: @xxx`
   - 有 Figma 再补：`Figma: ...`

3. **问题段：写具体问题，不写空泛背景**
   - 推荐标题：`Usability problems to solve:`（可用性类）；其它类型可用等价短标题
   - 结构：一句总问题 + 3～5 条 bullet，每条一个可核对的痛点
   - ✅ 说清楚：谁痛、在哪、发生什么、后果是什么  
     例：校验分散在 Social / Collabs / Forms；过严导致站点改前缀后用户无法保存；要等 BD 催才改
   - ❌ 禁止：`the gap vs X is obvious`、`feels modern`、大段价值叙事却不点问题
   - 对竞品/对标：写**具体差异**（步骤多、难理解、慢上线），不要只说「有差距」
   - 不用「从未 / never」；用「经常 / 容易 / 往往」

4. **待办段：产品 To do，不要官话**
   - 推荐标题（二选一，按范围选）：
     - 在现有能力上改：`Improvements on the current flow (... keep the existing foundation ...)`
     - 确有条件分支再写 `Rules / Logic`（见下）
   - ❌ 禁止默认用 `redesign` / `re-design` / 「推倒重来」——除非用户明确要求重做
   - ✅ 用 `improve` / `consolidate` / `loosen` / 「在现有基础上提升」
   - 每条 To do 要能直接指导产品/工程动作，不要「对齐范围 / 定义模型 / hand off」这类空待办
   - 不写已跑出的数字、脚本名、分批 PR；调查结论放评论

5. **章节按需，禁止套满模板**
   - **默认必有**：执行信息行、问题段、待办段
   - **默认不要**：`Acceptance criteria`、`Out of scope`（用户要再加）
   - `Rules / Logic`：仅当有真实 If/then 产品分支时才写
   - `UI copy`：仅当本票改可见文案时才写

6. **密度**
   - 太少（几句口号）→ 补具体问题点与可执行 To do
   - 太多（云里雾里长文）→ 砍到「总问题 + bullet 问题 + 编号 To do」
   - 锚点密度见 `KAT-11517`、`KAT-11975`

7. **文案直接给最终文本**（若改 UI）
   - `Title:` / `Tooltip:` / `Helper text:`

8. **评论区只做增量同步**（约束变化、测试结果、调查数字）

## 创建（层级与 POST）

1. **先确认再创建 Subtask。** 问清父项 key 后再 POST；不要猜 `11539` / Relates 对象的父项
2. 没确认 → 独立「任务」，无 parent
3. 用户说关联某条 → 只 Relates，**不要**顺便挂它的父项
4. 挂错无法改类型/父项 → 只能新建 + 删旧；故父项只能问
5. 用户只要文案 → 不 POST

## 改已有票（铁律 — 来自 KAT-11975 事故）

用户或他人可能已在 Jira 里加过链接、附件、录屏、Owner 等。**禁止**为改一两句而整段 `PUT` 覆盖 description。

1. **先 GET** 当前 `description`（ADF）与 `attachment`
2. **只改用户点名的句子/小节**；保留其余节点（mention、inlineCard、media、用户手写段落）
3. 改前在对话里贴出「将改哪几句」；用户同意后再写回
4. 若必须重构结构：先列出会动到的块，并确认附件/链接是否保留；**媒体节点丢失等于删附件展示**
5. 找不到稳妥的局部补丁时：输出修订文案让用户自己贴，或只改用户明确授权覆盖的段落

## 输出模板（按需删节）

```markdown
Summary
[Usability|Operation|Scalability]: <问题或目标，不是已定方案>

Description
Owner: @<owner or TBD> (due: <Mon D, YYYY or TBD>)
Design: @<design or TBD>
FE: @<fe or TBD>
BE POC: @<be or TBD>

Usability problems to solve: <一句总问题：谁痛、什么坏了、后果>
- <具体痛点 1：场景 + 现象>
- <具体痛点 2：含对标时写清差异，禁止 “gap is obvious”>
- <具体痛点 3：…>

Improvements on the current flow (keep the existing foundation; focus on fixing the usability problems without introducing new ones):
1) <在现有流程上提升的具体动作>
2) <统一 / 放宽 / 收敛等可执行项>
3) <…>

Rules / Logic:   ← 仅当有真实分支；否则整节删掉
- If <条件>, <行为>.

UI copy (if needed):
- Title: "..."
```

## 快速规则（写前 / 建前 / 改前自检）

- Summary 有正确前缀，且不是方案口号
- 问题段是否**条条具体**？有没有空话（obvious / modern / gap）？
- To do 是否产品动作？有没有 `redesign`？有没有「对齐/定义/hand off」官话？
- 是否误加了默认的 AC / Out of scope？
- 有真实分支才写 Rules / Logic
- Subtask 父项是否已口头确认？
- 改已有票：是否 GET 过现稿？是否只动目标句？附件/链接还在吗？
- 用户是否已说可以建 / 可以改？

## 参考风格锚点

- `KAT-11517`：问题总述 + bullet 痛点 + 改造要点（密度基准）
- `KAT-11975`：可用性 + 现有基础上提升；对标写具体差异；含用户补充的链接/录屏时勿覆盖
- `KAT-11847`：短背景 + end-to-end 最小改动
- `KAT-11701`：有真实条件流才上 `Rules / Logic`
- `KAT-11909`：问题 + To do；独立任务，只 Relates，不挂错父项

## 常见问题

1. **只有一句需求** → 补「总问题 + 3～5 条具体痛点 + 可执行 To do」，不要灌空背景  
2. **写得太长、读不动** → 删价值散文，只留问题 bullet 与 To do  
3. **写得太少、像口号** → 每条痛点补场景/后果；对标补具体差异  
4. **To do 全是官话** → 改成「改哪条流程 / 统一哪几处校验 / 放宽什么规则」  
5. **出现 redesign** → 改成 improve / 在现有基础上；除非用户明确要重做  
6. **调查当需求** → 数字、脚本、Slack 证据可放正文链接或评论，不写成长篇结论  
7. **没问就挂父项** → 停；先问。先例：`KAT-11879`、`KAT-11909`  
8. **改一句却整页覆盖** → 停；按「改已有票」做局部更新

## 红旗

- `the gap vs … is obvious` / `feels modern` / 无事实的「体验不好」
- To do 含 `redesign` 而用户要的是提升
- 套满 AC / Out of scope / Rules 只为「完整」
- 标题或 To do 已是结案方案
- 未问用户就 parent / Subtask
- 改票时整段 PUT，丢掉用户加的链接、录屏、mention
- 用户只要文案却已 POST
