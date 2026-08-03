---
name: jira-item-status
description: >
  在 Jira daily issue 的有序列表条目前方添加或替换状态标记（Done / Backlog / Invalid 等）。
  使用场景：用户说「标成 backlog」「标记 Done」「标成 invalid」「11816 5 backlog」「给第 5 条加 Done」、
  或只给 issue+条目编号且要搁置时（默认 Backlog）。
  写入规范：单个加粗 text 节点，文案形如 (Done)、(Backlog)；只改段首状态前缀，不改正文、mention、附件。
  优先运行 scripts/jira-item-status.py，禁止每次临时拼 inline Python。
---

# Jira 列表条目状态标记

在指定 Jira issue 有序列表某一条目的**最前面**写入（或替换）状态前缀，例如 `(Done)`、`(Backlog)`。

## 标记规范（铁律）

标准写法与现有 Done 条目一致：

| 规则 | 说明 |
|------|------|
| 文案 | 英文括号 + 规范标签，如 `(Done)`、`(Backlog)` |
| ADF | **一个** `text` 节点，整段含括号，带 `strong`（加粗） |
| 位置 | 插入目标 `paragraph.content` **最前面** |
| 默认 | 用户未说状态时 → **`Backlog`** |
| 范围 | 只改段首状态前缀；不改正文、mention、`mediaSingle`、`inlineCard`、`(moved …)`、优先级等其它括号 |

ADF 示例（正确）：

```json
{
  "type": "text",
  "text": "(Done)",
  "marks": [{ "type": "strong" }]
}
```

错误示例（不要写）：

- 拆成 `"("` + `"backlog"(strong)` + `")"` 三段
- 不加粗
- 写成中文括号 `（Done）` 或小写 `(done)`（写入用规范大小写；解析端大小写不敏感）

### 规范标签

与 `analyzer/statuses.py` 对齐（写入用右侧文案）：

| 用户说法 | 写入 |
|----------|------|
| （默认）/ backlog | `(Backlog)` |
| done / Done | `(Done)` |
| invalid | `(Invalid)` |
| cannot reproduce | `(Cannot reproduce)` |

其它用户明确给出的状态（如 `Won't fix`）可原样写入 `(Won't fix)` 并加粗；但 analyzer 统计只认上表已知前缀。

## 执行方式（优先）

**Agent 必须优先调用** [`scripts/jira-item-status.py`](../scripts/jira-item-status.py)，不要每次在对话里拼 inline Python。

```bash
# 默认 Backlog
python3 scripts/jira-item-status.py KAT-11816:5
python3 scripts/jira-item-status.py 11816:5

# 指定状态
python3 scripts/jira-item-status.py --status Done KAT-11816:1
python3 scripts/jira-item-status.py done 11816:1 11816:3
python3 scripts/jira-item-status.py --status "Cannot reproduce" KAT-11675:2

# 预览
python3 scripts/jira-item-status.py --dry-run KAT-11816:5
```

凭据复用 `config.json` / `JIRA_*`（`analyzer.config.load_config`）。

## 操作流程

### Step 1：解析指令

| 字段 | 示例 | 默认 |
|------|------|------|
| issue | `11816`、`KAT-11816`、URL | 无，必须能解析 |
| 条目编号 | `5`、`第 5 条` | 无 |
| 状态 | `done` / `backlog` / `invalid`… | **`Backlog`** |

可将多条一次标记：`11816:1 11816:3`。

### Step 2：运行脚本

按上表拼命令并执行。同一 issue 多条目会合并为一次 GET/PUT。

### Step 3：汇报

向用户报告：issue key、条目编号、写入的 `(Label)`、条目摘要一两句、PUT 状态（或 dry-run）。

## 脚本行为摘要

1. `GET` description → `deepcopy`
2. 按 Jira 界面编号定位 listItem（`orderedList.attrs.order` + 段内位置）
3. **先剥掉**段首已有已知状态前缀（含历史拆分写法 `(``backlog``)`），再插入规范加粗节点
4. 若下一段落文本不以空白/`(` 开头，在状态后插一个普通空格节点，避免 `(Backlog)正文` 粘连
5. 一次 `PUT`；仅接受 200/204
6. 已是目标状态时仍会规范化写法（例如把拆分的 backlog 收成单个 `(Backlog)` strong 节点）

## 示例指令

| 用户说法 | 命令 |
|----------|------|
| 11816 5 标成 backlog | `python3 scripts/jira-item-status.py KAT-11816:5` |
| 11816 5 | 同上（默认 Backlog） |
| 11816 1 标记 Done | `python3 scripts/jira-item-status.py --status Done KAT-11816:1` |
| 把 11675 的 #2 标成 invalid | `python3 scripts/jira-item-status.py --status Invalid KAT-11675:2` |

## 常见陷阱

1. **不要**用手改 mention / 迁移流程来「顺便」改状态
2. **单 orderedList 多条目**：编号 5 往往是 `order=1` 的 `content[4]`，不是 `order=5` 的节点
3. **`(Done)(High priority…)`**：剥前缀时只去掉已知状态段，保留后面的优先级等括号
4. **凭据**：勿在回复中泄露 `api_token`
