# Jira 列表条目迁移 Skill 配置指南

本文说明如何配置本仓库环境，以便在 Cursor 中正常使用 [`skills/jira-item-migrate.md`](../skills/jira-item-migrate.md) 所描述的 **Jira 列表条目迁移** 工作流。

## 这个 Skill 做什么

将一个 Jira issue 有序列表中的某条（或若干条）迁移到另一个 issue：

- **源 issue**：不删文字、不删附件，只在条目正文前追加 `(moved {目标编号} No.{新序号})`
- **目标 issue**：在 description 末尾新增一条列表项，复制文字、@mention、图片/视频附件，不追加来源标记

执行必须是**原子化**的：附件全部就绪后再 PUT，禁止分步打补丁。

---

## 一、环境要求

| 项目 | 要求 |
|------|------|
| 操作系统 | macOS / Linux / Windows 均可 |
| Python | 3.8+（与项目 `requirements.txt` 一致） |
| 网络 | 能访问你的 Jira Cloud 实例（`*.atlassian.net`）及 `api.media.atlassian.com`（附件媒体服务） |
| Cursor | 支持 Agent 模式，并能读取项目内文件 |

### 安装 Python 依赖

在项目根目录执行：

```bash
npm run setup
```

等价于：

```bash
python3 -m pip install -r requirements.txt
```

当前迁移流程主要依赖 `requests`；Agent 执行时会直接调用 Jira REST API，并复用本仓库的 `analyzer.parser`、`analyzer.jira_http` 等模块。

---

## 二、Jira API 凭据配置（必做）

Skill 需要通过 Jira REST API 读取/写入 issue 描述与附件。凭据与主项目报告生成共用同一套配置。

### 方式 A：本地 `config.json`（推荐）

1. 复制配置模板：

   ```bash
   cp config.example.json config.json
   ```

2. 编辑 `config.json`，填写 `jira` 段：

   ```json
   {
     "jira": {
       "base_url": "https://your-domain.atlassian.net",
       "email": "your-email@example.com",
       "api_token": "YOUR_JIRA_API_TOKEN_HERE"
     }
   }
   ```

   | 字段 | 说明 |
   |------|------|
   | `base_url` | Jira 站点根地址，**不要**带末尾 `/` 或 `/jira` 路径 |
   | `email` | 登录 Jira 的 Atlassian 账号邮箱 |
   | `api_token` | Atlassian API Token |

3. 获取 API Token：打开 [Atlassian 账户安全设置](https://id.atlassian.net/manage-profile/security/api-tokens)，创建 Token 后粘贴到 `api_token`。

> `config.json` 已在 `.gitignore` 中，**不要**提交到 Git。

### 方式 B：环境变量

若不想落盘 `config.json`，可设置：

```bash
export JIRA_BASE_URL="https://your-domain.atlassian.net"
export JIRA_EMAIL="your-email@example.com"
export JIRA_API_TOKEN="your-api-token"
```

`analyzer.config.load_config()` 会优先读取这三个环境变量。

### 验证凭据是否可用

在项目根目录运行：

```bash
python3 -c "
from analyzer.config import load_config
from analyzer.jira_http import build_jira_session, jira_request

cfg = load_config()
session = build_jira_session(cfg)
url = f\"{cfg['jira']['base_url']}/rest/api/3/myself\"
r = jira_request(session, 'GET', url, timeout=30)
print('OK' if r.status_code == 200 else f'FAIL {r.status_code}: {r.text[:200]}')
"
```

输出 `OK` 表示凭据与网络正常。

---

## 三、Jira 账号权限要求

执行迁移的账号需要对**源 issue** 和**目标 issue** 具备：

| 能力 | 用途 |
|------|------|
| **浏览项目** | `GET /rest/api/3/issue/{key}` 读取 description、attachment |
| **编辑 Issue** | `PUT /rest/api/3/issue/{key}` 更新 description（ADF） |
| **创建附件** | `POST /rest/api/3/issue/{key}/attachments` 上传图片/视频到目标 issue |

典型角色：项目 **Developer** 或 **Administrator**。若只能看不能改，PUT 会返回 403。

迁移涉及的 issue 需使用 **Atlassian Document Format（ADF）** 描述（Jira Cloud 默认），且列表为 `orderedList` 结构——与本仓库 `analyzer/parser.py` 的解析逻辑一致。

---

## 四、在 Cursor 中启用 Skill

本仓库的 Skill 文件位于项目根目录 `skills/jira-item-migrate.md`（带 YAML frontmatter）。在 Cursor 中有以下几种用法。

### 方式 1：对话中 @ 引用（最简单）

在 Agent 对话里直接附加 Skill 文件，例如：

```text
@skills/jira-item-migrate.md 把 KAT-11075 的第 1 条迁移到 KAT-11325
```

或先 @ Skill，再描述具体操作。Agent 会读取该文件并按其中流程执行。

### 方式 2：安装为 Cursor 项目 Skill（可选，便于团队共享）

若希望 Cursor 按标准 Skill 目录自动发现，可将内容链接或复制到：

```text
.cursor/skills/jira-item-migrate/SKILL.md
```

示例（符号链接，便于与 `skills/` 保持同步）：

```bash
mkdir -p .cursor/skills/jira-item-migrate
ln -sf ../../skills/jira-item-migrate.md .cursor/skills/jira-item-migrate/SKILL.md
```

之后可在 Skill 列表中看到 `jira-item-migrate`，或在对话里 @ `jira-item-migrate`。

### 方式 3：Cursor Rule 自动关联（可选）

在 `.cursor/rules/` 下新增规则，说明当用户提到「迁移」「搬到」「move」等关键词时，应读取 `skills/jira-item-migrate.md`。适合团队统一话术，避免每次手动 @。

---

## 五、相关 Skill 与代码依赖

迁移流程会间接依赖以下内容，**无需单独配置**，但 Agent 需要能读取这些文件：

| 资源 | 作用 |
|------|------|
| [`skills/jira-owner-mention.md`](../skills/jira-owner-mention.md) | `find_list_item_by_index`：按 Jira 界面编号定位 listItem |
| [`analyzer/parser.py`](../analyzer/parser.py) | `parse_list_items`：编号校验、事后验证 |
| [`analyzer/jira_http.py`](../analyzer/jira_http.py) | `build_jira_session`：认证与重试；附件上传须去掉默认 `Content-Type: application/json` |
| [`analyzer/config.py`](../analyzer/config.py) | `load_config`：加载 Jira 凭据 |

若条目含 @负责人，mention 文案以 `analyzer/owners.py` 为准；迁移时**复制** mention 节点，一般不修改 `owners.py`。

---

## 六、如何使用（对话示例）

配置完成后，在 Cursor Agent 中可用自然语言发起迁移。建议一次说清 **源 issue、条目编号、目标 issue**：

```text
@skills/jira-item-migrate.md
把 KAT-11075 的第 1 条迁移到 KAT-11325
```

```text
@skills/jira-item-migrate.md
迁移 KAT-11206 #4 → KAT-11325
```

```text
@skills/jira-item-migrate.md
把 https://xxx.atlassian.net/browse/KAT-11111 的第 7 条搬到 KAT-11386
```

也可直接提供两个 Jira URL + 条目编号。Agent 应遵循 Skill 中的原子化流程：先上传全部附件，再 PUT 目标，最后 PUT 源。

---

## 七、配置检查清单

使用前请确认：

- [ ] 已执行 `npm run setup` 或 `pip install -r requirements.txt`
- [ ] `config.json` 或环境变量 `JIRA_*` 三项均已填写且有效
- [ ] `python3 -c "from analyzer.config import load_config; ..."` 自检返回 `OK`
- [ ] 当前 Jira 账号对源、目标 issue 有编辑与附件权限
- [ ] Cursor 对话中已 @ `skills/jira-item-migrate.md`（或已安装为 `.cursor/skills`）
- [ ] 明确要迁移的**条目编号**（与 Jira 界面 `No.1`、`No.2` 一致，不是 ADF 内部数组下标）

---

## 八、常见问题

### 1. 提示「配置文件不存在」

复制 `config.example.json` 为 `config.json`，或设置 `JIRA_BASE_URL`、`JIRA_EMAIL`、`JIRA_API_TOKEN` 环境变量。

### 2. PUT 返回 403 Forbidden

检查账号是否对该项目有 **Edit Issues** 权限，或 issue 是否被工作流/字段权限锁住。

### 3. 附件上传返回 415

Skill 要求上传时**不能**带 `Content-Type: application/json`。应使用 `build_jira_session` 创建 session 后，上传请求头只保留 `X-Atlassian-Token: no-check`（详见 Skill Step 6）。若 Agent 未按此处理，可提醒其参考 `analyzer/jira_http.py` 与 Skill 中的 multipart 示例。

### 4. 迁移后编号重复或跳号

属逻辑错误，应使用 Skill 中的 `compute_new_number`，不要用 `len(items)` 或 `len(items)+1` 估算。详见 Skill「常见故障」表。

### 5. 源条目图片被误删或目标多了别人的图

多为 trailing `mediaSingle` 归属判断错误。提醒 Agent 严格按 Skill Step 3 的 `get_trailing_media_for_item` 规则执行。

### 6. 附件失败后的状态

按 Skill 铁律：**任一附件失败则整单中止**，不写入目标、不标记源。需修复网络/权限后重新发起完整迁移。

---

## 九、与报告生成配置的关系

`config.json` 中的 `parent_issue`、`filters`、`scheduled` 等字段用于 **HTML 报告统计**，与条目迁移**无直接依赖**。迁移只需 `jira` 段（或等价环境变量）即可。

若你仅为迁移配置本仓库，最小 `config.json` 示例：

```json
{
  "jira": {
    "base_url": "https://your-domain.atlassian.net",
    "email": "your-email@example.com",
    "api_token": "YOUR_JIRA_API_TOKEN_HERE"
  }
}
```

---

## 十、进一步阅读

- Skill 完整操作流程与铁律：[`skills/jira-item-migrate.md`](../skills/jira-item-migrate.md)
- 列表条目加人/删人（正交能力）：[`skills/jira-owner-mention.md`](../skills/jira-owner-mention.md)
- 项目总体说明：[`README.md`](../README.md)
