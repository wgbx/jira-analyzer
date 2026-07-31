---
name: jira-release-summary
description: >
  按负责人汇总当前 / 最近发布周的排期摘要表（含上周遗留、issue、No.、一句话摘要）。
  使用场景：用户说「按人出表」「排期摘要」「这周安排」「看看表格」「发我一份」、
  @skills/jira-release-summary，或只要浏览 data/scheduled.json 本周 items 的可读视图。
  只读展示，不改排期；要改排期用 jira-release-schedule。
---

# Jira 发布周排期摘要（按人）

把 `data/scheduled.json` + 最新报告收成**按人表格**，方便扫一眼本周安排。

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
- **上周遗留**：上一周 items 中，报告里仍 `data-processed=false` 的条目（标「{上周 label 短写}遗留」，如 `7/27遗留`）
- `owner` 以 `scheduled.json` 为准；摘要文本从 `output/index.html` 对应条目的 `item-text` 截取（约 40–70 字）

展示名用 `analyzer/owners.py` 的 `OWNER_DISPLAY_NAMES`（`june`→June 等）。

### 3. 输出格式（必须）

先总览，再按人分节。**按条数降序**排列人员。

```markdown
**{label}**（含上周遗留，共 N 条）

| Owner | 条数 |
|-------|------|
| June | 6 |
| Cici | 5 |

### June（6）
| 来源 | Issue | No. | 摘要 |
|------|-------|-----|------|
| 7/27遗留 | 11584 | 9 | 右上角菜单切页问题 |
| 8/3 | 11816 | 7 | Protect platform（hotfix） |
```

约定：

- **来源**：本周用短日期（`8/3`）；遗留用 `{短日期}遗留`
- **Issue**：纯数字（与 JSON 一致，不加 `KAT-`）
- **摘要**：可读短句即可；可压缩英文长句，保留 High / hotfix 等优先级词
- 开头一句点明是哪一周 + 总条数；不要长篇解释规则

### 4. 可选：只看某人

用户说「只看 cici / June」→ 只输出该人一节 + 其条数。

## 相关

- 编排下一周：`skills/jira-release-schedule.md`
- 数据：`data/scheduled.json`、`output/index.html`
