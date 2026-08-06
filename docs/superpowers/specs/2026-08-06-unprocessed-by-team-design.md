# 未处理按团队（武汉 / 成都 / US）拆分 — 设计

日期：2026-08-06

## 背景

主报告「未处理」卡片目前只显示总数。需要一眼看到武汉、成都、美国三地分别还有多少未处理条目。

## 目标

在主报告「未处理」统计卡片上展示三地未处理条目数，口径与现有「未处理」一致。

## 非目标

- 不改 Markdown / Owner Daily / Meeting 报告
- 不展示「未分配」或其它地区
- 不引入第二份成员调色板或独立团队成员表

## 数据模型

在 `OWNER_REGISTRY` 每条增加必填字段：

```python
'team': 'wuhan' | 'chengdu' | 'us'
```

展示文案：

| `team`   | 文案 |
|----------|------|
| `wuhan`  | 武汉 |
| `chengdu`| 成都 |
| `us`     | US   |

现有成员按 `owners.py` 内注释分区赋值。筛选栏顺序仍为书写顺序。加成员时必须同时填 `team`（更新 `add-owner` 规则与 AGENTS 菜谱）。

## 计数规则

1. 只统计 `_counts_as_unprocessed(item, analysis)` 为真的条目。
2. 每条只计 **1** 次（条目去重）。
3. 取该条目 `owners` 列表中 **第一个** 在 `OWNER_REGISTRY` 内的 owner，按其 `team` 计入。
4. 无 owner、或无一在 registry 内 → 不计入三地（也不单独展示）。
5. 因此：`武汉 + 成都 + US ≤ analysis['unprocessed']`；差额为未分配/未知。跨团队多人同条很少见，按首 owner 团队处理即可。

实现：`analyzer/report/common.py` 新增 `_count_unprocessed_by_team(analysis)`，返回如 `{'wuhan': N, 'chengdu': N, 'us': N}`。

## UI

仅改 `analyzer/report/html_main.py` 的「未处理」卡片：

- 保留现有大数字与「N 个子任务」副标题。
- 其下（或旁）增加一行副文案：`武汉 {n} · 成都 {n} · US {n}`。
- 某地为 0 时仍显示该地（便于确认无遗漏）。
- 其它统计卡片与布局不动。

## 测试

- `tests/test_owners.py`：每条 registry 含合法 `team`。
- 新增计数单测：单团队、跨团队取首 owner、无 owner 不计、与 unprocessed 口径一致。

## 验收

- `npm run smoke && npm test`
- `npm run serve`（或 `npm start`）打开主报告，未处理卡片可见三地数字且合理。

## 改动文件

| 文件 | 改动 |
|------|------|
| `analyzer/owners.py` | 每条加 `team` |
| `analyzer/report/common.py` | `_count_unprocessed_by_team` |
| `analyzer/report/html_main.py` | 未处理卡片副行 |
| `tests/` | registry + 计数单测 |
| `.cursor/rules/add-owner.mdc`、`AGENTS.md` | 加成员必填 `team` |
