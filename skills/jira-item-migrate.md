---
name: jira-item-migrate
description: >
  将一个 Jira issue 的有序列表中的某个条目迁移到另一个 Jira issue。
  使用场景：用户说"迁移"、"搬到"、"move"、提供两个 Jira URL 并指定要移动的编号。
  原则：只增不删——源 issue 的文字和附件永远不删除，只在列表项文本前面追加 (moved XXX No.x) 标记；
  目标 issue 只新增一条列表项（含文字、mention、附件图片/视频），并在文本前追加 (From XXX No.x) 来源标记。
---

# Jira 列表条目迁移

将源 Jira issue 有序列表中的指定条目迁移到目标 Jira issue。

## 标记规范（双向溯源）

迁移后在**两端**各加一条英文前缀，issue 编号均用**纯数字**（不带 `KAT-` 等项目前缀），与现有 daily 写法一致。

| 位置 | 格式 | 示例 |
|------|------|------|
| **源** issue（条目已迁出） | `(moved {target_number} No.{new_number})` | `(moved 11325 No. 7 )` |
| **目标** issue（新迁入条目） | `(From {source_number} No.{source_index})` | `(From 11075 No. 1 )` |

**为何推荐 `(From …)` 而非 `(Migrated from …)` / `(Imported from …)`：**

- 与源端 `(moved …)` **对称、短、好扫**：一眼能拼出完整路径 `11075 #1 → 11325 #7`
- 纯英文、括号包裹，和 `( Done )` / `( Backlog )` 风格一致；`From` 首字母大写
- `(From …)` **不会**命中 `statuses.py` 的 `moved` 检测，目标条目仍按正常未处理项统计
- 不用 `(migrate to …)` 那种非标准写法（历史条目里偶有，但不统一）

两段标记均用 **strong（加粗）** ADF `text` 节点，插在 paragraph `content` **最前面**，后接空格再跟原有正文。

## 铁律（永不违反）

1. **禁止删除**源 issue 的任何文字、附件、media 节点
2. **禁止修改**源 issue 条目的正文内容——只允许在文本开头追加 `(moved {target_number} No.{new_number})`
3. **禁止删除**源 issue 的 mediaSingle（图片/视频）节点
4. 目标 issue **只做新增**——追加新的 orderedList 条目，不改动已有内容；新条目正文前只允许追加 `(From {source_number} No.{source_index})`
5. 如果附件迁移失败（ATTACHMENT_VALIDATION_ERROR），保持源 issue 不变并告知用户手动处理附件

## 操作流程

### Step 1：解析用户指令

从用户消息中提取：
- 源 issue key（如 KAT-11047）
- 要迁移的条目编号（如第 13 点）
- 目标 issue key（如 KAT-10967）

### Step 2：获取两个 issue 的描述

```python
GET /rest/api/3/issue/{key}?fields=description,attachment
```

### Step 3：定位源条目

**不要**假设「第 N 条 = `attrs.order == N` 的 orderedList」。常见结构是一个 `orderedList`（`order=1`）内含多条 `listItem`，编号 = `start_order + position`（与 `parser.parse_list_items` 一致）。

定位算法见 `skills/jira-owner-mention.md` 中的 `find_list_item_by_index`。

记录该 listItem 内所有节点（paragraph、mediaSingle 等），以及紧跟在 orderedList 后面的 **顶层 mediaSingle 节点**（这些是条目附带的图片/视频）。

### Step 4：计算目标 issue 的新编号

统计目标 issue description 中所有 `type=orderedList` 节点的 listItem 数量之和，新编号 = 总数 + 1。

### Step 5：构建迁移内容（deep copy）

对源条目做 **deep copy**，构建新的 orderedList：

```python
new_ordered_list = {
    "type": "orderedList",
    "attrs": {"order": new_number, "localId": "migrated_xxx"},
    "content": [deepcopy(source_listItem)]
}
```

**处理 mediaSingle**：
- listItem **内部**的 mediaSingle → 保留在 copy 中
- listItem **外部**（紧跟 orderedList 后的顶层 mediaSingle）→ 也追加到新 orderedList 的 listItem content 末尾

### Step 6：处理附件（图片/视频）

media 节点中的 `id` 是 Atlassian 媒体服务的 UUID，非附件数字 ID。同一文件在不同 issue 上 UUID 不同。

**ADF 结构**（勿读错层级）：

```
mediaSingle
  └── media          ← attrs.id / attrs.alt 在此节点
```

**迁移附件的步骤**：

1. 从 `mediaSingle.content[0]`（`type=media`）读取 `attrs.alt` 文件名
2. 从源 issue 的 attachment 列表中找到匹配的附件 → 获取数字 ID
3. 下载附件二进制数据：`GET /rest/api/3/attachment/content/{id}`
4. 上传到目标 issue：`POST /rest/api/3/issue/{target_key}/attachments`（header: `X-Atlassian-Token: no-check`）
5. 获取新附件的 media UUID：
   ```python
   resp = requests.get(
       f"{base_url}/rest/api/3/attachment/content/{new_attachment_id}",
       auth=auth, allow_redirects=False, timeout=30
   )
   location = resp.headers.get('Location', '')
   # Location 格式: https://api.media.atlassian.com/file/{UUID}/binary?...
   # 用正则提取 UUID
   uuid = re.search(r'/file/([a-f0-9-]+)/binary', location).group(1)
   ```
6. 将新 UUID 写入 `mediaSingle.content[0].attrs.id`

**如果上传或 UUID 获取失败**：跳过 media 节点，只迁移文字内容，告知用户需手动处理附件。

### Step 7：标记目标 issue 新条目并追加

在 deep copy 后的 listItem 的 paragraph `content` **最前面**插入来源标记：

```json
[
  {"type": "text", "text": "(From {source_number} No.", "marks": [{"type": "strong"}]},
  {"type": "text", "text": "{source_index}", "marks": [{"type": "strong"}]},
  {"type": "text", "text": ") ", "marks": [{"type": "strong"}]}
]
```

`{source_number}` 为源 issue key 的纯数字部分（如 `11075`），`{source_index}` 为源条目编号。

将新的 orderedList 追加到目标 issue description 的 `content` 数组末尾。

```python
PUT /rest/api/3/issue/{target_key}
Body: {"fields": {"description": updated_desc}}
```

**验证**：返回状态码 204 或 200 表示成功。如果是 400（ATTACHMENT_VALIDATION_ERROR），说明 media UUID 有问题，移除 media 节点后重试。

### Step 8：标记源 issue 条目

**只修改文字，不删除任何东西**：

在源 issue 的 listItem 的 paragraph content **最前面**插入：

```json
[
  {"type": "text", "text": "(moved {target_number} No.", "marks": [{"type": "strong"}]},
  {"type": "text", "text": "{new_number}", "marks": [{"type": "strong"}]},
  {"type": "text", "text": ") ", "marks": [{"type": "strong"}]}
]
```

**注意**：`{target_number}` 是目标 issue key 中的纯数字部分（如 `11325`），**不带项目前缀**（即不带 `KAT-`）。

然后保留原有文字节点（保持原样）。

**重要**：源 issue 的 mediaSingle 节点**全部保留不动**。

```python
PUT /rest/api/3/issue/{source_key}
Body: {"fields": {"description": updated_source_desc}}
```

### Step 9：汇报结果

向用户报告：
- 迁移了什么内容（文字概要）
- 源 issue 标记为 `(moved {target_number} No.{new_number})`
- 目标 issue 新增为第 {new_number} 条，标记为 `(From {source_number} No.{source_index})`
- 附件迁移是否成功，如失败说明哪些附件需手动处理

## 示例

11075 #1 → 11325 #7 完成后：

- **KAT-11075 #1**：`(moved 11325 No. 7 ) Add a copy icon…`
- **KAT-11325 #7**：`(From 11075 No. 1 ) Add a copy icon…`
