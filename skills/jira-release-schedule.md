---
name: jira-release-schedule
description: >
  为下一发布周编排 data/scheduled.json（Release plan）。
  使用场景：用户说「排下一期」「排下周」「release plan」「维护排期」、提供 Google Sheet 式条目列表、
  要求按人出表、或「Jira 改了 owner 请同步」。
  原则：只排武汉团队（OWNER_REGISTRY team=wuhan）；优先关票；清上周遗留；
  成都 / US 不进 plan；排除名单不排；items 单行 JSON；写完后 npm start 并按人汇总。
---

# Jira 发布周排期

维护 `data/scheduled.json`，为下一发布周选出要做的 daily 列表条目（`issue` + `index` + `owner`）。

## 前置

- `npm start` / `python3 jira_analyzer.py` 可拉取最新报告 → `output/index.html`
- Owner 映射以 `analyzer/owners.py` 为准
- 排期文件格式见 `README.md`「维护已排期列表」；查找逻辑在 `analyzer/scheduled.py`

## 铁律

1. **保留历史 release**，只追加新一周；不要清空旧周
2. **items 单行书写**：`{ "issue": "11776", "index": 7, "owner": "cici" }`，禁止 `json.dumps(indent=2)` 把每个字段拆成多行
3. **不重复排**：`(issue, index)` 已在任意 release 中则跳过
4. **owner 来自 Jira mention**（报告 `data-owners`），不是主观重分配；用户改完 Jira 后要同步时，以最新报告为准覆盖 `owner` 字段
5. **未分配不排**（无 owner 的条目跳过）
6. **只排武汉团队**：`OWNER_REGISTRY[owner].team == 'wuhan'` 才进 plan  
   - **成都**（`tianye` / `lei` / `lory` / `vanppo` 等）**不排**  
   - **US**（`fred` / `jiangtian` / `chenglim` 等）**不排**  
   - 额外排除（即便是武汉）：默认 `dajiang`（用户可改）  
   - 条目任一 owner 落在排除名单 / 非武汉 → 整条不排（多人协作含成都/US 时同样跳过，留给对方计划）

## 排期规则（优先级）

1. **清上周遗留**：上一 release 中仍 `data-processed=false` 的条目，本周优先做完（已在旧 release 里即可，不必复制到新周；汇报时标「上周遗留」）
2. **优先关票**：按 ticket 剩余**未处理**条目数升序；优先排「把剩余全排进本周 → 可关 ticket」的票（★）
3. **量级**：过少则继续补（参考上周约 20–28 条我方条目）；用户说「再多排」再扩；排除名单成员的剩余不算「我方可关」
4. **日期**：上一 release 的 `date` + 7 天；`label` 为 `M/D/YYYY Release`（如 `8/3/2026 Release`）

## 工作流

### Step 1：刷新数据

```bash
npm start
```

读 `data/scheduled.json` 与 `output/index.html`（或直接走 analyzer），得到：

- 各 ticket 未处理条目、`data-owners`、是否已排期
- 上周遗留未完成列表

### Step 2：选出本周候选

对每个活跃 ticket：

| 条件 | 处理 |
|------|------|
| 未处理 + 未排期 + **武汉** owner + 不在排除名单 | 可排 |
| 剩余少（1–5）且剩余均可排（仅计武汉侧） | ★ 优先整票排入 |
| 仅差成都 / US / 排除名单才能关票 | 仍可排武汉条目，但不声称「可关票」 |
| 全未分配 / 仅成都或 US | 跳过 |

多 owner 时 `scheduled.json` 的 `owner` 取**第一个武汉且非排除**的 key。

### Step 3：写入 `data/scheduled.json`

追加新 release，例如：

```json
{
  "date": "2026-08-03",
  "label": "8/3/2026 Release",
  "items": [
    { "issue": "11424", "index": 1, "owner": "cici" },
    { "issue": "11675", "index": 6, "owner": "jun" }
  ]
}
```

### Step 4：再跑报告 + 按人出表

```bash
npm start
```

向用户展示：

1. 上周遗留（issue / No. / owner / 摘要）
2. 本周新增条数与可关票列表
3. **按人列表**（含上周遗留），格式见 `skills/jira-release-summary.md`：

```text
**8/3/2026 Release**（含上周遗留，共 N 条）

### June（6）
11584 No.2 @June Teng — …
11776 No.7 @cici Huang ← 7/27遗留 — …
```

### Step 5：用户反馈后的常见调整

| 用户说 | 动作 |
|--------|------|
| 排除某人 / 某人不要排 | 加入排除名单，从本周 items 删除其条目，可补其他 ★ |
| 再多排一点 | 按关票优先继续补到约定量级 |
| 更新 owner / 我改了 Jira | `npm start` 后按报告同步 `owner`；**保持单行格式**重写文件 |
| 粘贴 Sheet 列表维护进去 | 解析 `11776 No.7 … cici Huang` → 写入对应 release（可新建周） |

## Owner 同步（改完 Jira 后）

对 `scheduled.json` 里每条 `(issue, index)`：

1. 从最新报告读 `data-owners`
2. 若当前 `owner` 仍在列表且不在排除名单 → 不动
3. 否则改为第一个非排除 owner；无人可写则标出给用户
4. 重写文件时**整文件保持 items 单行**（不要 `indent=2` 展开对象）

## 用户粘贴 Sheet 时的解析

```
8/3/2026	Release in this week
	11724 No.9	P1		Jiaqi Yu
	11584 No.6		Launched	zhiyong song
```

- `issue` = 数字；`index` = `No.` 后序号
- owner：显示名 / `@mention` → `owners.py` 的 key（`Jiaqi Yu`→`jiaqi`，`cici Huang`→`cici`）
- `P1` / `Launched` / `Backlog` 等是状态备注，**不写入** JSON

## 相关文件

- `data/scheduled.json` — 排期真相来源
- `analyzer/scheduled.py` — `(task_key, index) → release label`
- `analyzer/owners.py` — owner key / mention / 展示名
- `output/index.html` — 排期与处理状态（`npm start` 生成）
- `skills/jira-release-summary.md` — **只读**按人摘要表（确认 / 转发用）
- `skills/jira-owner-mention.md` — 改 Jira @mention（与本 skill 互补）
