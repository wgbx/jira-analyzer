---
name: jira-release-summary
description: >
  按负责人汇总当前 / 最近发布周的排期摘要（含上周遗留）。
  条目行格式固定为：11584 No.7 @cici Huang（issue + No. + @mention）。
  使用场景：用户说「按人出表」「排期摘要」「这周安排」「看看表格」「发我一份」、
  @skills/jira-release-summary，或只要浏览 data/scheduled.json 本周 items 的可读视图。
  只读展示，不改排期；要改排期用 jira-release-schedule。
---

# Jira 发布周排期摘要（按人）

把 `data/scheduled.json` + 最新报告收成**按人列表**，方便扫一眼本周安排。

## 何时用

- 「按刚才的表格再发我一份」「这周安排按人看看」
- 拉本 skill 直接看摘要
- 排完期后的确认视图（`jira-release-schedule` Step 4 同款输出）

**不做**：增删排期、改 owner（那些走 `skills/jira-release-schedule.md` / `jira-owner-mention.md`）。

## 步骤

### 1. 数据要新就先刷新

用户未说明可跳过；说「最新」「刚改了 Jira」则：

```bash
npm start
```

### 2. 取范围

- **本周**：`releases` 里 `date` 最新的一周（如 `8/3/2026 Release`）
- **上周遗留**：上一周 items 中，报告里仍 `data-processed=false` 的条目（标在行尾或分组小标题，如 `← 7/27遗留`）
- `owner` 以 `scheduled.json` 为准；`@mention` 用 `analyzer/owners.py` 的 `OWNERS[key][0]`（如 `cici` → `@cici Huang`）
- 可选：同一行后追加短摘要（从 `output/index.html` 的 `item-text` 压缩，约 40 字）

### 3. 输出格式（必须）

**每条一行**，格式：

```text
{issue} No.{index} @{mention}
```

示例：

```text
11584 No.7 @cici Huang
11584 No.9 @Jayce
```

整体结构：先总览条数，再按人分节（**条数降序**）。遗留条目可在行尾标 `← 7/27遗留`。

```markdown
**8/3/2026 Release**（含上周遗留，共 30 条）

June 6 · Cici 5 · Tiancheng 5 · …

### June（6）
11584 No.2 @June Teng — Stripe connected account（High）
11691 No.11 @June Teng — Komi import 缺第一 section
11816 No.7 @June Teng — Protect platform（hotfix）

### Cici（5）
11776 No.7 @cici Huang ← 7/27遗留 — Intro text 字号过大
11424 No.1 @cici Huang — 查看 filled info 需显示 field title
```

约定：

- **Issue**：纯数字，不加 `KAT-`
- **@mention**：必须与 `OWNERS` 一致，不要自造 `@Jayce.Chen` 这类非登记写法（除非用户显式要求某种 ping 格式）
- **摘要**：可选；有则用 ` — ` 接在 mention 后；保留 High / hotfix 等词
- 开头点明哪一周 + 总条数；不要长篇解释规则

### 4. 可选：只看某人

用户说「只看 cici / June」→ 只输出该人一节。

## 相关

- 编排下一周：`skills/jira-release-schedule.md`
- 数据：`data/scheduled.json`、`output/index.html`
