---
name: jira-owner-mention
description: >
  在 Jira daily issue 的有序列表条目中添加或删除 @负责人（mention），或维护 analyzer/owners.py 团队成员映射。
  使用场景：用户说「加人」「删人」「加上 xxx」「去掉 xxx」「@某人」、指定 issue 条目编号与 owner 标识（如 tiancheng、zhiyong）。
  负责人标识与 @mention 文案以 analyzer/owners.py 的 OWNERS 为准；修改 Jira 描述时只增删 mention 节点，不改条目正文与其它附件。
---

# Jira 列表条目加人 / 删人

在指定 Jira issue 的有序列表某一条目中，添加或删除 `@负责人` mention；必要时同步更新 `analyzer/owners.py` 中的团队成员定义。

## 前置依赖

- 项目根目录已配置 `config.json`（或环境变量 `JIRA_BASE_URL` / `JIRA_EMAIL` / `JIRA_API_TOKEN`）
- 负责人映射：**唯一真相来源**为 `analyzer/owners.py` 中的 `OWNERS` 与 `OWNER_DISPLAY_NAMES`
- 列表条目编号与 Jira 界面一致，由 `analyzer.parser.parse_list_items` 计算（`orderedList.attrs.order` + 段内位置）

```python
from analyzer.config import load_config
from analyzer.owners import OWNERS, OWNER_DISPLAY_NAMES
from analyzer.parser import parse_list_items
```

## 铁律（永不违反）

1. **只改 mention**：不修改条目正文文字、不删除 `mediaSingle` / `inlineCard`、不改动 `(Done)` / `(moved …)` 等标记
2. **@mention 文案必须与 OWNERS 一致**（如 `tiancheng` → `@Tiancheng Tang`），不得手写拼写
3. **加人前先查重**：该 listItem 的 paragraph 中已存在同一 `accountId` 或相同 `attrs.text` 的 mention 时，跳过并告知用户
4. **删人只删 mention 节点**：不删相邻的纯空格 `text` 节点以外的正文
5. **PUT 失败不部分提交**：先 `deepcopy` 描述，改完一次 PUT；状态码须为 200 或 204
6. **owners.py 与 Jira 分离**：用户只说「加人/删人」且指向某条 Jira 时，只改 Jira；仅当用户要求「登记新成员」「从团队列表移除」时才改 `owners.py`

## 操作流程

### Step 1：解析用户指令

从用户消息中提取：

| 字段 | 示例 |
|------|------|
| issue key | `KAT-11194` 或 Jira URL |
| 条目编号 | `4`、`第 4 条` |
| 操作 | `加` / `删` / `添加` / `去掉` / `remove` |
| owner 标识 | `tiancheng`、`zhiyong`（对应 `OWNERS` 的 key） |
| 是否改 owners.py | 「把 xxx 加进 owners」「新同事」→ 维护映射表 |

若 owner 标识不在 `OWNERS` 中，先询问用户是要 **登记到 owners.py** 还是提供了错误 key。

### Step 2：获取 issue 描述

```python
GET /rest/api/3/issue/{key}?fields=description
auth = HTTPBasicAuth(config['jira']['email'], config['jira']['api_token'])
```

对返回的 `description` 做 **`copy.deepcopy`** 后再修改。

### Step 3：定位 listItem（按 Jira 编号）

**不要**假设「第 4 条 = `attrs.order == 4` 的 orderedList」。常见结构是一个 `orderedList`（`order=1`）内含多条 `listItem`，编号 1、2、3… 对应 `start_order + position`。

定位算法（与 `parser._parse_ordered_list` 一致）：

```python
def find_list_item_by_index(desc_content, target_index):
    """返回 (listItem dict, paragraph dict) 或 (None, None)"""
    def walk(nodes):
        for node in nodes:
            if not isinstance(node, dict):
                continue
            if node.get('type') == 'orderedList':
                start = node.get('attrs', {}).get('order', 1)
                for pos, child in enumerate(node.get('content', [])):
                    if child.get('type') != 'listItem':
                        continue
                    jira_index = start + pos
                    if jira_index == target_index:
                        para = next(
                            (c for c in child.get('content', [])
                             if c.get('type') == 'paragraph'),
                            None,
                        )
                        return child, para
            if 'content' in node and node.get('type') != 'listItem':
                found = walk(node['content'])
                if found[0]:
                    return found
        return None, None
    return walk(desc_content)
```

用 `parse_list_items` **校验**编号与文本摘要，避免改错条。

### Step 4：解析 accountId（加人时）

```python
GET /rest/api/3/user/search?query={display_name}
# display_name = OWNERS[owner_key][0].lstrip('@')  如 "Tiancheng Tang"
account_id = users[0]['accountId']
```

若无结果，告知用户 Jira 中找不到该用户，**不要**写入假 id。

### Step 5a：添加 mention

在目标 `paragraph['content']` 中插入 ADF mention 节点（建议插在**已有 mention 组之前**，或段落末尾 mention 之前）：

```python
import uuid

mention_text = OWNERS[owner_key][0]   # 如 "@Tiancheng Tang"

new_mention = {
    "type": "mention",
    "attrs": {
        "id": account_id,
        "text": mention_text,
        "accessLevel": "",
        "localId": str(uuid.uuid4()),
    },
}
# 前后各加一个空格 text 节点，与现有条目风格一致
para_content.insert(idx, {"type": "text", "text": " "})
para_content.insert(idx, new_mention)
```

**查重**：遍历 `para_content`，若已有 `type=="mention"` 且 `attrs.id == account_id`（或 `attrs.text` 与 `mention_text` 相同，忽略大小写），则不再插入。

### Step 5b：删除 mention

从 `paragraph['content']` 中移除匹配的 mention 节点：

- `attrs.id` 等于该用户的 `accountId`，或
- `attrs.text` 与 `OWNERS[owner_key]` 中任一关键词相同（忽略大小写）

可选：若删除 mention 后留下连续仅含空格的 `text` 节点，可合并为一个空格，**不要**删非 mention 的正文。

若删除后该条无任何 mention，属正常情况，无需改正文。

### Step 6：写回 Jira

```python
PUT /rest/api/3/issue/{key}
Body: {"fields": {"description": updated_desc}}
```

### Step 7：维护 owners.py（仅当用户要求登记/移除成员）

**新增成员** — 在 `OWNERS` 增加 key 与 @mention 列表，在 `OWNER_DISPLAY_NAMES` 增加展示名：

```python
OWNERS = {
    # ...
    'newperson': ['@Display Name'],  # 与 Jira @mention 完全一致
}
OWNER_DISPLAY_NAMES = {
    # ...
    'newperson': 'Display Name',
}
```

**移除成员** — 删除对应 key（两处都删）。不自动批量清理历史 Jira 里的 @mention，除非用户明确要求。

### Step 8：汇报结果

向用户报告：

- issue key、条目编号、操作（加/删）、owner 标识与 @mention 文案
- 该条摘要（一两句）
- 若改了 `owners.py`，列出变更的 key
- Jira PUT 状态；加人后可用 `detect_owner` / `parse_list_items` 验证 `owners` 字段

## 示例指令

| 用户说法 | 动作 |
|----------|------|
| KAT-11194 第 4 条加上 tiancheng | Step 5a，`owner_key=tiancheng` |
| 把 11194 的 #4 去掉 zhiyong | Step 5b |
| https://…/browse/KAT-11194 条目 2 加 jun | 从 URL 取 key，Step 5a |
| owners 里加 yuxiao，@Yuxiao Zhu | 仅 Step 7 |
| 阅读这个 jira 并把 #4 加上 tiancheng | 先读 issue，再 Step 5a |

## 常见陷阱

1. **单 orderedList 多条目**：编号 4 往往是 `order=1` 的 `content[3]`，不是 `order=4` 的节点
2. **Yuxiao Zhu 等未在 OWNERS 的人**：Jira 里可有 mention，但报告 owner 筛选用不到；需用户确认是否写入 `owners.py`
3. **inlineCard / 截图**：条目内可能有 Slack 链接或 `mediaSingle`，插入 mention 时勿碰这些节点
4. **config 凭据**：勿在 skill 或回复中泄露 `api_token`

## 相关文件

- `analyzer/owners.py` — `OWNERS` / `OWNER_DISPLAY_NAMES` / `detect_owner`
- `analyzer/parser.py` — `parse_list_items`、条目编号规则
- `analyzer/jira_client.py` — `get_issue_description`
- `skills/jira-item-migrate.md` — 列表条目迁移（与本 skill 正交，迁移时不删源 mention）
