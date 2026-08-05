# Jira 任务分析器

定期分析 Jira 父任务下的子任务（当前默认 Q3：KAT-11542，并保留 Q2：KAT-10938），解析描述中的列表项，统计未处理的项目并生成可视化报告。

> AI / Agent 改代码请先读 [AGENTS.md](./AGENTS.md)。本地健康检查：`npm run smoke && npm test`。

## 功能

- 一次生成多份报告：首页 Q3 + `/2026q2/`（见 `config.example.json` → `reports`）
- 默认拉取各父任务下**全部**子任务并统计列表条目
- 解析 ADF（Atlassian Document Format）描述中的列表项
- 检测条目状态：Done / Backlog（含 Invalid）/ Moved / 删除线
- 自动识别条目的负责人（通过 @mention 和文本匹配）
- 生成带筛选功能的 HTML 报告
- 支持按人员筛选，包括未分配的条目
- 支持「已排期」标记（维护于 `data/scheduled.json`，对应发布周计划）

## 项目结构

```
jira-analyzer/
├── package.json                # npm 脚本入口（推荐本地启动方式）
├── jira_analyzer.py            # Python 入口脚本
├── analyzer/                   # 核心模块
│   ├── config.py              # 配置管理（支持环境变量）
│   ├── owners.py              # 团队成员定义与匹配
│   ├── parser.py              # ADF 解析与状态检测
│   ├── jira_client.py         # Jira API 封装
│   ├── report/                # HTML/Markdown/Daily 报告（分包）
│   │   ├── html_main.py       # 主报告
│   │   ├── daily.py / meeting.py / markdown.py / filters.py / common.py
│   ├── ...
├── tests/                      # 不连 Jira 的 unittest
├── AGENTS.md                   # AI / Agent 改代码地图
├── config.example.json         # 配置模板
├── requirements.txt            # Python 依赖
├── output/                     # 报告与定时任务日志（git 忽略）
└── .github/workflows/          # GitHub Actions 报告部署
```

## 本地运行

需要本机已安装 **Node.js 18+** 与 **Python 3**。

### 1. 安装依赖

```bash
npm run setup
```

`setup` 会自动执行 `git:local-ignore`：在本机忽略自动生成报告的本地改动，**全选暂存**时不会再带上它们。若仍出现在更改列表，可手动再跑一次：`npm run git:local-ignore`。

等价于 `pip install -r requirements.txt`。

### 2. 配置

复制配置模板并填写 Jira API Token：

```bash
cp config.example.json config.json
```

API Token 获取地址：https://id.atlassian.net/manage-profile/security/api-tokens

### 3. 运行

```bash
npm start
```

报告会生成到：
- `output/index.html`（Q3，对应站点 `/`）
- `output/2026q2/index.html`（Q2，对应站点 `/2026q2/`）

并在本地自动用浏览器打开 Q3 报告。

### 常用脚本

| 命令 | 说明 |
|------|------|
| `npm start` | 拉取 Jira 数据并生成报告（默认） |
| `npm run serve` | 仅预览已有报告（静态文件，不拉 Jira） |
| `npm run dev` | **推荐本地使用**：定时拉取 Jira、更新报告，浏览器自动刷新（默认每 120 秒，见 `config.json` → `watch`） |
| `npm run smoke` | 不连 Jira：检查关键文件、配置、import 与语法 |
| `npm test` | 不连 Jira：owners / parser / statuses / scheduled 单测 |

开发时改完 `data/scheduled.json` 或 Jira 后，保持 `npm run dev` 运行即可，无需反复手动 `npm start`。单次生成仍用 `npm start`。

## GitHub 部署

推送到 `main`、手动触发，或由**外部定时器**调用 `workflow_dispatch` 时，GitHub Actions 会运行分析（`npm run setup` → `npm start`）并部署到 GitHub Pages。

> 不使用 GitHub 自带的 `schedule`：免费计划下常延迟数小时甚至漏跑。定时请用下方「外部定时触发」。

### 1. 创建仓库

在 GitHub 上创建一个新仓库（建议设为 Private）。

### 2. 配置 Secrets

在仓库的 **Settings → Secrets and variables → Actions** 中添加：

| Secret 名称 | 说明 |
|---|---|
| `JIRA_BASE_URL` | Jira 实例地址，如 `https://your-domain.atlassian.net` |
| `JIRA_EMAIL` | Jira 账号邮箱 |
| `JIRA_API_TOKEN` | Jira API Token |

父任务编号写在仓库内的 `config.example.json` → `reports`（当前 Q3=`KAT-11542`，Q2=`KAT-10938`），CI 会直接读取，无需 Secret。

### 3. 启用 GitHub Pages

在仓库的 **Settings → Pages** 中：
- Source 选择 **GitHub Actions**

### 4. 推送代码

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/your-username/jira-analyzer.git
git push -u origin main
```

推送后 Actions 会自动运行。也可以在 Actions 页面手动触发。

### 5. 外部定时触发（推荐）

用免费 cron 服务准点调用 GitHub API，Actions 仍走免费额度。

**A. 创建 PAT**

1. GitHub → **Settings → Developer settings → Personal access tokens**
2. 推荐 **Fine-grained token**：只选本仓库，Permissions → **Actions: Read and write**
3. 复制 token（只显示一次）

**B. 配置 [cron-job.org](https://cron-job.org)（免费）**

1. 注册并创建 Cronjob
2. URL：

```text
https://api.github.com/repos/wgbx/jira-analyzer/actions/workflows/jira-report.yml/dispatches
```

3. Method：`POST`
4. Headers：

| Header | Value |
|---|---|
| `Authorization` | `Bearer <你的PAT>` |
| `Accept` | `application/vnd.github+json` |
| `Content-Type` | `application/json` |

5. Body：`{"ref":"main"}`
6. Schedule（北京时间 9:00–20:00 每小时）：`0 9-20 * * *`（若界面用 UTC，改为 `0 1-12 * * *`）

成功时 API 返回 **204**。也可本地试跑：

```bash
export GITHUB_TOKEN=你的PAT
./scripts/trigger-github-report.sh
```

### 6. 查看报告

部署完成后，访问：
- Q3：`https://your-username.github.io/jira-analyzer/`
- Q2：`https://your-username.github.io/jira-analyzer/2026q2/`

## 本地定时运行（macOS launchd）

编辑 `com.jira.analyzer.plist` 中的路径，然后：

```bash
cp com.jira.analyzer.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.jira.analyzer.plist
```

卸载：

```bash
launchctl unload ~/Library/LaunchAgents/com.jira.analyzer.plist
```

## 维护已排期列表

编辑 `data/scheduled.json`，按发布周录入子任务编号与列表序号（与 Google Sheet 中 `11047 No.15` 格式一致：`issue` 为数字部分，`index` 为 No. 后的序号）：

```json
{
  "project_key": "KAT",
  "releases": [
    {
      "date": "2026-06-01",
      "label": "6/1/2026 Release",
      "items": [{"issue": "11047", "index": 15}]
    }
  ]
}
```

报告会对命中排期表的条目显示发布周标签；**排期状态** 支持：全部、已排期、排期已处理（Done/Backlog/Invalid/Moved）、未排期。

### 统计口径

**总条目数 / 已处理 / 排期已处理**：父任务下**全部**子任务 Description 列表行的合计。**未处理 / 已排期**：仅 Jira 状态为 **待办**、**正在进行** 的子任务（API 的 `status.name`；界面上的「未处理」「进行中」与此对应，不是字面字符串 `未处理`/`进行中`）。`To Verify` 等 QA 后状态不计入。可在 `filters.active_statuses` 配置，也支持别名 `未处理`→`待办`、`进行中`→`正在进行`。

**已处理 / 未处理** 卡片下方另显示子任务数：含已处理条目的子任务数；含未处理条目且 Jira 状态活跃的子任务数。

## 添加团队成员

编辑 `analyzer/owners.py`，**只在 `OWNER_REGISTRY` 增加一条**（展示名、颜色、@mention 都在这里；筛选栏顺序 = 书写顺序）：

```python
'username': {
    'mentions': ['@Jira 显示名'],
    'display': '筛选栏名',
    'color': ('#背景色', '#文字色'),  # 可选
},
```

勿手改导出的 `OWNERS` / `OWNER_DISPLAY_NAMES`，也不要在 `report.py` 另维护调色板。