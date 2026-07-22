---
name: jira-item-migrate
description: >
  将一个 Jira issue 的有序列表中的某个条目迁移到另一个 Jira issue。
  使用场景：用户说"迁移"、"搬到"、"move"、提供两个 Jira URL 并指定要移动的编号。
  原则：只增不删——源 issue 的文字和附件永远不删除，只在列表项文本前面追加 (moved XXX No.x) 标记；
  目标 issue 只新增一条列表项（含文字、mention、附件图片/视频），不追加来源标记。
  执行必须原子化：附件全部就绪后再 PUT，禁止分步打补丁。
  优先运行 scripts/jira-item-migrate.py，禁止每次临时拼 inline Python。
---

# Jira 列表条目迁移

将源 Jira issue 有序列表中的指定条目迁移到目标 Jira issue。

## 执行方式（优先）

**Agent 必须优先调用仓库内 CLI 脚本** [`scripts/jira-item-migrate.py`](../scripts/jira-item-migrate.py)，不要每次在对话里重新生成一段 inline Python。

脚本已实现本 Skill 的核心流程（`compute_new_number`、trailing media 归属、附件 multipart 上传、批量迁移、替换已有 `(moved …)` 前缀）。凭据复用 `config.json` / `JIRA_*` 环境变量（见 `analyzer.config.load_config`）。

### 命令

```bash
# 完整迁移：复制内容+附件到目标，并更新源 (moved …) 标记
python3 scripts/jira-item-migrate.py migrate --target KAT-11496 \
  KAT-11267:3 KAT-11267:5 KAT-11109:2

# 仅标记：内容已在目标，按指定编号更新源端 (moved …) 标记
python3 scripts/jira-item-migrate.py mark --target KAT-11496 --at 7,8,9 \
  KAT-11349:2 KAT-11349:5 KAT-11349:6

# 移除历史遗留的 (From …) 前缀
python3 scripts/jira-item-migrate.py strip-from KAT-11751:1

# 预览，不写入 Jira（--dry-run 放在子命令前面）
python3 scripts/jira-item-migrate.py --dry-run migrate --target KAT-11496 KAT-11267:3

# 等价 npm 入口
npm run migrate -- migrate --target KAT-11496 KAT-11267:3
```

源条目格式为 `KAT-{编号}:{条目序号}`，可一次传多条。

### 两种子命令怎么选

| 场景 | 子命令 | 说明 |
|------|--------|------|
| 正常迁移 / 目标描述被改需**重迁** | `migrate` | 从源 deep copy 内容，上传附件，在目标末尾追加新条目，更新源 `(moved …)` |
| 内容已在目标、只缺源端标记 | `mark` | 用 `--at` 指定目标条目编号，只改源 `(moved …)` |
| 历史条目带 `(From …)` 需清理 | `strip-from` | 移除目标条目上的 `(From …)` 前缀，不改其他内容 |
| 重迁且源已有旧 `(moved …)` | `migrate` | 脚本会先 strip 旧前缀再写入新编号 |

### Agent 工作流

1. 从用户消息解析 `--target` 与 `KAT-xxxx:N` 列表
2. 判断用 `migrate` 还是 `mark`（用户说「重迁」「11496 被人改了」→ `migrate`；说「标记一下」「确认编号」→ `mark`）
3. **直接运行脚本**；失败时根据 stderr 对照下方「常见故障」排查，**不要**分步 PUT 打补丁
4. 向用户汇报脚本输出中的编号对应与校验结果

### 何时仍读本 Skill 下文

- 脚本报错需理解 ADF / 编号 / trailing media 根因
- 目标 issue 有**空 orderedList 需复用空位**（情况 B）——脚本当前只做末尾追加；此场景按下方 Step 3–8 手工处理或扩展脚本
- 需要修改迁移逻辑时，改 `scripts/jira-item-migrate.py` 而非复制粘贴新脚本

## 标记规范

迁移后**仅在源 issue** 追加英文前缀，issue 编号用**纯数字**（不带 `KAT-` 等项目前缀），与现有 daily 写法一致。

| 位置 | 格式 | 示例 |
|------|------|------|
| **源** issue（条目已迁出） | `(moved {target_number} No.{new_number})` | `(moved 11325 No. 7 )` |
| **目标** issue（新迁入条目） | 无额外标记 | 保持源正文原样 |

源端标记用 **strong（加粗）** ADF `text` 节点，插在 paragraph `content` **最前面**，后接空格再跟原有正文。目标端不插入任何迁移前缀。

## 铁律（永不违反）

1. **禁止删除**源 issue 的任何文字、附件、media 节点
2. **禁止修改**源 issue 条目的正文内容——只允许在文本开头追加 `(moved {target_number} No.{new_number})`
3. **禁止删除**源 issue 的 mediaSingle（图片/视频）节点
4. 目标 issue **只做新增**——在 description 末尾追加**一个新的** `orderedList`（`order = new_number`），**禁止**往已有 `orderedList` 里塞 `listItem`、**禁止**对已存在条目做局部 append
5. **原子执行**：附件全部上传成功、ADF 在内存中组装完毕之前，**不得** PUT 目标或源 issue
6. **附件失败即中止**：任一附件上传或 UUID 获取失败时，**不写入**目标、**不标记**源，告知用户手动处理；**禁止**「先写文字、后补图片」或「去掉 media 后重试 PUT」
7. **禁止分步修补**：不得用多次脚本/多次 PUT 叠加修复；一次迁移 = 一次完整流程

## 常见故障（必读）

以下问题均来自「分步 PUT + 附件失败后降级写文字」的真实事故，执行前务必规避。

| 故障现象 | 根因 | 规避方式 |
|----------|------|----------|
| 图片在上、文字在下 | 只 `append(mediaSingle)`，paragraph 内容丢失或为空 | 整段 deep copy listItem，保持子节点顺序 |
| 出现两个相同编号 | 第一次 PUT 留下残缺 `orderedList`，修复时又新增/合并 | 附件就绪前不写目标；只追加一个 `order=new_number` 的 orderedList |
| `(moved … No. 6)` 实际应在 #7 | **off-by-one**：把 `len(items)` 当成新编号，忘了 `+ 1` | 必须用下方 `compute_new_number`；`moved` 与 `order` 同号 |
| 两个 #7（缺 #6） | 目标有条目 **跳号**（如 #1–#5、#7），`len+1` 撞上已有编号 | 用 `max(index)+1`，不能只用 `len(items)+1` |
| 两个 #11 | 目标有**空 orderedList**（paragraph 无文本），`parse_list_items` 未计入 | `compute_new_number` 必须同时扫 `attrs.order`；优先复用空位 |
| 目标多了别人的图 | 把 orderedList 后 trailing media 误归到块内靠前的条目 | 仅最后一条 `listItem` 才合并 trailing media |
| 目标多了录屏/隔开的图 | trailing 扫描未在 `paragraph` 等屏障处停止 | 只吸收**紧挨** orderedList 后连续的 `mediaSingle` |
| bulletList 丢失 | 重试时只保留了 paragraph | copy 源 listItem 的**全部**子节点 |
| Jira 展示错乱 | 复用源 `localId`，ADF 节点冲突 | 迁移副本所有 `localId` 必须重新生成 |

## 操作流程

> **默认路径**：运行 `scripts/jira-item-migrate.py`（见上文「执行方式」）。以下 Step 0–10 为实现参考与排障手册；`migrate` / `mark` 子命令的逻辑与 Step 3–9 一致，源码在 `scripts/jira-item-migrate.py` 的 `JiraMigrator` 类。

### Step 0：执行顺序（原子化）

```
读取源/目标 → 定位源条目 → 内存中 deep copy → 上传全部附件 → 写入新 UUID
    → 组装 new_ordered_list → 校验 ADF
    → PUT 目标（一次）→ 插入 (moved …) 标记 → PUT 源（一次）→ 事后校验
```

**任何一步失败**：停止，不 PUT，向用户报告失败点。优先用 CLI 一次跑完，禁止拆成多轮 inline 脚本。

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

记录该 listItem 内**所有**子节点（`paragraph`、`bulletList`、`mediaSingle` 等）。

**顶层 trailing `mediaSingle` 归属（易错）**：紧跟在 `orderedList` 之后的顶层图片，**只属于该 orderedList 里最后一个 `listItem`**，不属于同块里靠前的条目。

```
orderedList order=4
  listItem → #4  ← 迁移这条时，只带走 listItem 内部的 media
  listItem → #5
mediaSingle  xxx.png  ← 这是 #5 的图，不是 #4 的！
orderedList order=6
```

仅当待迁移条目是其所在 `orderedList` 的**最后一个** `listItem` 时，才可合并 trailing media；且**只吸收紧挨 orderedList 之后、连续排列的顶层 `mediaSingle`**，中间一旦夹了 `paragraph` / `bulletList` / 其他节点就**立即停止**，不能扫到更后面的媒体。

```
orderedList order=0
  listItem → #3  media=image.png（在 listItem 内，必带走）
paragraph          ← 屏障：后面的 mov 不归 #3
mediaSingle  x.mov
bulletList
```

真实事故（11152 #3）：listItem 内已有 `image-20260504-184800.png`，后面隔了一个 `paragraph` 才是录屏 mov；旧逻辑一直扫到下一个 `orderedList`，误把 mov 并入 #3。

```python
def get_trailing_media_for_item(top_content, ol_node, list_item):
    items_in_ol = [c for c in ol_node.get('content', []) if c.get('type') == 'listItem']
    if not items_in_ol or items_in_ol[-1] is not list_item:
        return []  # 不是块内最后一条，禁止吸收 trailing media
    ol_idx = next(i for i, n in enumerate(top_content) if n is ol_node)
    trailing = []
    for j in range(ol_idx + 1, len(top_content)):
        n = top_content[j]
        if n.get('type') == 'mediaSingle':
            trailing.append(n)
        else:
            break  # paragraph / bulletList / orderedList 等一律停止，禁止跨过屏障继续扫
    return trailing
```

用 `parse_list_items` **校验**编号与文本摘要，避免改错条。

### Step 4：计算目标 issue 的新编号

编号计算必须同时考虑 `parse_list_items` 可解析的条目 **和** ADF 中 orderedList 的 `attrs.order`（包括空 orderedList），否则空 orderedList 的编号会被遗漏，导致新编号与已有编号冲突。

```python
from analyzer.parser import parse_list_items

def compute_new_number(target_description_content, extra_count=0):
    """
    返回下一条迁移条目在目标 issue 上的编号。
    优先复用空 orderedList 的编号（将内容填入空位），否则追加到末尾。

    extra_count: 同一次 PUT 中要追加多条时，第 2 条在 base+1、第 3 条在 base+2 …
    """
    top = target_description_content if isinstance(target_description_content, list) else target_description_content.get('content', [])

    # 1. 收集所有顶层 orderedList 的 order 值
    used_orders = set()
    empty_slots = {}  # order → orderedList node（可复用的空位）
    for node in top:
        if isinstance(node, dict) and node.get('type') == 'orderedList':
            order = node.get('attrs', {}).get('order', 1)
            used_orders.add(order)
            # 判断是否为空：listItem 内 paragraph 无文本
            items_in = [c for c in node.get('content', []) if c.get('type') == 'listItem']
            if len(items_in) == 1:
                para = next((c for c in items_in[0].get('content', []) if c.get('type') == 'paragraph'), None)
                texts = para.get('content', []) if para else []
                has_text = any(
                    n.get('type') == 'text' and n.get('text', '').strip()
                    for n in texts
                )
                has_mention = any(n.get('type') == 'mention' for n in texts)
                has_media = any(
                    c.get('type') == 'mediaSingle'
                    for c in items_in[0].get('content', [])
                )
                if not has_text and not has_mention and not has_media:
                    empty_slots[order] = node

    # 2. 也从 parse_list_items 获取已占用的 index
    items, _ = parse_list_items(target_description_content)
    parsed_indices = {i['index'] for i in items}

    # 3. 所有已占用编号的并集
    all_used = used_orders | parsed_indices

    # 4. 优先找最小空位复用
    for slot_order in sorted(empty_slots):
        if slot_order not in parsed_indices:
            return slot_order + extra_count  # 复用空位

    # 5. 无空位则在末尾追加
    base = (max(all_used) if all_used else 0) + 1
    return base + extra_count
```

| 目标已有条目 | `max(index)` | 空位 | 新编号 | 策略 |
|-------------|--------------|------|--------|------|
| #1–#6 连续 | 6 | 无 | **7** | 末尾追加 |
| #1–#5、#7（缺 #6） | 7 | 无 | **8** | 末尾追加 |
| #1–#10、#11 空 | 10 / 11 | **#11** | **11** | **复用 #11 空位**（填入内容） |
| #1–#10、#11 空、#12 空 | 10 | #11 | **11** | 复用最小空位 #11 |

**复用空位时**：不追加新 orderedList，而是将迁移内容填入空 orderedList 的 listItem 中（替换空 paragraph）。

**禁止写法（真实事故）**：

```python
new_number = len(items)              # ❌ 少 +1；且跳号/空条时会撞上已有 index
new_number = len(items) + 1          # ❌ 跳号/空条时仍可能撞上
new_number = max(i['index'] for i in items) + 1  # ❌ 空 orderedList 无 index，max 会漏掉
new_number = ordered_list.attrs['order']          # ❌ 与条目序号无关
```

**推荐**：算出 `new_number` 后，断言 `new_number not in parsed_indices`（可等于空 orderedList 的 order）。

**两条必须同号**（写错任一都会乱）：

1. 目标 `orderedList.attrs.order` = `new_number`（复用空位或新建）
2. 源 `(moved {target} No.{new_number})` 里的数字 = `new_number`（**目标上的新位置**，不是源条目序号）

批量迁移（如 #1 和 #2 同批）：第一条 `compute_new_number(..., 0)`，第二条 `compute_new_number(..., 1)`，依此类推；**每条各追加一个** `orderedList`。

### Step 5：构建迁移内容（deep copy）

对源条目做 **deep copy**，并**重新生成所有 `localId`**（`listItem`、`paragraph`、`bulletList`、`mediaSingle`、`media` 等），避免与源 ADF 冲突导致 Jira 合并/重复展示。

**listItem 子节点顺序必须与源一致**，典型结构：

```
paragraph        ← 正文 + mention（无迁移前缀）
bulletList       ← 若有，必须保留，不可丢
mediaSingle      ← 图片/视频，永远在段落和子弹列表之后
```

将 listItem **外部**、且经 Step 3 判定归属本条的顶层 mediaSingle deep copy 后，追加到 listItem `content` **末尾**（仍在 paragraph / bulletList 之后）。**禁止**把同 `orderedList` 内下一条的 trailing 媒体并入当前条目。

构建新的 orderedList，分两种情况：

**情况 A：末尾追加**（无空位可复用）

```python
import uuid

new_ordered_list = {
    "type": "orderedList",
    "attrs": {"order": new_number, "localId": f"migrated_{uuid.uuid4().hex[:12]}"},
    "content": [migrated_list_item],  # 完整 listItem，非裸 paragraph
}
# 追加到 description content 末尾
```

**情况 B：复用空 orderedList**（`compute_new_number` 返回了已有空 orderedList 的 order）

```python
# 找到目标 issue description 中 order == new_number 的空 orderedList
# 将其 listItem 的 content 替换为 migrated_list_item 的 content
empty_ol = next(n for n in target_desc['content']
                if n.get('type') == 'orderedList'
                and n.get('attrs', {}).get('order') == new_number)
empty_li = next(c for c in empty_ol['content'] if c.get('type') == 'listItem')
empty_li['content'] = migrated_list_item['content']  # 填入迁移内容
# 不追加新 orderedList，原地修改即可
```

**禁止**：
- 只 copy `paragraph` 而丢掉 `bulletList` / `mediaSingle`
- 把迁移条目插入已有**非空** `orderedList` 的 `content` 数组
- 事后单独 `append(mediaSingle)` 到已 PUT 的 listItem

### Step 6：处理附件（图片/视频）——先于一切 PUT

media 节点中的 `id` 是 Atlassian 媒体服务的 UUID，非附件数字 ID。同一文件在不同 issue 上 UUID 不同。

**ADF 结构**（勿读错层级）：

```
mediaSingle
  └── media          ← attrs.id / attrs.alt 在此节点
```

收集 listItem 内 + 外部顶层的全部 `mediaSingle`，**在内存中的 copy 上**逐个处理：

1. 从 `mediaSingle.content[0]`（`type=media`）读取 `attrs.alt` 文件名
2. 从源 issue 的 attachment 列表中找到匹配的附件 → 获取数字 ID
3. 下载附件二进制数据：`GET /rest/api/3/attachment/content/{id}`
4. 上传到目标 issue（见下方 **multipart 注意**）
5. 获取新附件的 media UUID：
   ```python
   resp = requests.get(
       f"{base_url}/rest/api/3/attachment/content/{new_attachment_id}",
       auth=auth, allow_redirects=False, timeout=30
   )
   location = resp.headers.get('Location', '')
   # Location 格式: https://api.media.atlassian.com/file/{UUID}/binary?...
   uuid = re.search(r'/file/([a-f0-9-]+)/binary', location).group(1)
   ```
6. 将新 UUID 写入 copy 中 `mediaSingle.content[0].attrs.id`

#### multipart 上传注意（否则 415）

`build_jira_session` 默认设置 `Content-Type: application/json`，**不能**用于附件上传。

```python
# 上传时必须去掉 application/json，只保留 X-Atlassian-Token
headers = {'X-Atlassian-Token': 'no-check'}
upload_headers = {k: v for k, v in session.headers.items() if k.lower() != 'content-type'}
upload_headers.update(headers)

requests.post(
    f"{base_url}/rest/api/3/issue/{target_key}/attachments",
    auth=session.auth,
    headers=upload_headers,
    files={'file': (filename, data, mime_type)},
    timeout=120,
)
```

**如果任一附件上传或 UUID 获取失败**：停止整个迁移，不 PUT 目标、不标记源，列出失败文件名，请用户手动处理或重试。

### Step 7：写入目标 issue 新条目

将 `new_ordered_list` **追加**到目标 issue description 的 `content` 数组**末尾**（不修改已有节点）。目标条目**不插入** `(From …)` 或任何迁移前缀。

#### PUT 前自检（内存中）

- [ ] `new_number == max(index) + 1` 且不在已有 `index` 集合中（批量时按 `extra_count` 递增）
- [ ] listItem 第一个子节点是含内容的 `paragraph`（非空 `content`）
- [ ] `bulletList`（若源有）仍在 paragraph 与 mediaSingle 之间
- [ ] 所有 `mediaSingle` 在 listItem `content` 末尾，且 `attrs.id` 均为目标 issue 的新 UUID
- [ ] 仅新增一个 `orderedList`，`attrs.order == new_number`（**不等于** `len(items)`）
- [ ] 源 `(moved … No.{new_number})` 与目标 `order` 数字一致
- [ ] 所有 `localId` 均为新生成的值

```python
PUT /rest/api/3/issue/{target_key}
Body: {"fields": {"description": updated_desc}}
```

**验证**：返回 204 或 200。若 400（`ATTACHMENT_VALIDATION_ERROR`）：**不要**去掉 media 重试——说明 Step 6 的 UUID 有问题，**中止**并排查，避免留下残缺条目。

### Step 8：标记源 issue 条目

**目标 PUT 成功后再改源**（避免目标失败却源已标记）。

在源 issue 的 listItem 的 paragraph `content` **最前面**插入：

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

### Step 9：事后校验

PUT 完成后重新 GET 两个 issue，用 `parse_list_items` 确认：

- 目标 issue 条目总数 = 迁移前 + 迁移条数，**无重复编号**（`len(indices) == len(set(indices))`）
- 目标新条目 `index == new_number`，文本**不含** `(From …)` 前缀
- 源条目 `(moved {target} No.{new_number})` 中 **No. 后面的数字 == 目标新条目的 index**（不是源条目序号）
- 源条目 `is_moved == True`
- 目标新条目的 listItem 子节点顺序：`paragraph` →（`bulletList`?）→ `mediaSingle`…

**编号纠错示例**（曾发生）：目标已有 6 条，新条应在 #7，却写成 `(moved 11386 No. 6 )` → 将目标末尾 `orderedList.attrs.order` 改为 `7`，并修正源 paragraph 中加粗数字节点为 `"7"`。

若校验失败，**不要**再分步 PATCH——向用户说明偏差，必要时回滚（删除目标末尾多余的 `orderedList`、去掉源 `(moved …)` 前缀）后整单重跑。

### Step 10：汇报结果

向用户报告：
- 迁移了什么内容（文字概要）
- 源 issue 标记为 `(moved {target_number} No.{new_number})`
- 目标 issue 新增为第 {new_number} 条（无来源前缀）
- 附件迁移数量与文件名
- 若曾中止：说明失败点，确认两端均未写入

## 示例

### CLI：批量重迁到 11496（目标描述曾被改动）

源端已有旧 `(moved 11496 No. 7–12)`，但 11496 内容对不上，需重迁并更新编号：

```bash
python3 scripts/jira-item-migrate.py migrate --target KAT-11496 \
  KAT-11267:3 KAT-11267:5 KAT-11109:2 KAT-10839:5 KAT-10951:10 KAT-10928:10
```

脚本会追加到目标末尾（如 #32–#37），并把源端 `(moved …)` 改为新编号。

### CLI：仅补源端 moved 标记

内容已在目标 issue 中，源端尚未标记，需指定目标条目编号：

```bash
python3 scripts/jira-item-migrate.py mark --target KAT-11496 --at 7,8,9 \
  KAT-11349:2 KAT-11349:5 KAT-11349:6
```

### 单条：11075 #1 → 11325（目标已有 6 条）

```python
items, _ = parse_list_items(target_desc['content'])
new_number = max(i['index'] for i in items) + 1   # max=6 → 7
```

完成后：

- **KAT-11075 #1**：`(moved 11325 No. 7 ) Add a copy icon…` ← `No. 7` 是目标新位置
- **KAT-11325 #7**：`Add a copy icon…`（正文原样，无来源前缀）

### 单条：11244 #7 → 11386（目标已有 6 条）

- **KAT-11244 #7**：`(moved 11386 No. 7 ) (Lury)The shared amount…`
- **KAT-11386 #7**：`(Lury)The shared amount…`

### 单条：11206 #4 → 11325（目标有 #1–#5、#7，缺 #6）

```python
items, _ = parse_list_items(target_desc['content'])  # indices: [1,2,3,4,5,7]
new_number = max(i['index'] for i in items) + 1      # 7 + 1 = 8，不是 len+1=7
```

- **KAT-11206 #4**：`(moved 11325 No. 8 ) (Lury)Only show one tab "Sold by co-sellers"…`
- **KAT-11325 #8**：`(Lury)Only show one tab "Sold by co-sellers"…`

### 单条：11111 #7 → 11386（目标有 #1–#10、#11 空）

```python
# parse_list_items 返回 [1,2,3,...,10]，max=10
# 但 ADF 中有 order=11 的空 orderedList
compute_new_number(target_desc['content'])  # → 11（复用空位）
```

- **KAT-11111 #7**：`(moved 11386 No. 11 )`
- **KAT-11386 #11**：填入原有空 orderedList，正文原样

含子弹列表与图片时，目标 #7 的 ADF 顺序：

```
listItem
  [0] paragraph   please make sure… @Tiancheng Tang
  [1] bulletList  If the post media is different…
  [2] mediaSingle Frame 2147238569.png
```

## 相关文件

- **`scripts/jira-item-migrate.py`** — **首选执行入口**（`migrate` / `mark` / `strip-from` 子命令）
- `docs/jira-item-migrate-setup.md` — 环境配置与凭据自检
- `skills/jira-owner-mention.md` — `find_list_item_by_index`（脚本内同名实现）
- `analyzer/jira_http.py` — `build_jira_session`（附件上传须绕过默认 JSON Content-Type）
- `analyzer/parser.py` — `parse_list_items`（编号校验与事后验证）
