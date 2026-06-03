# Jira 任务分析器

定期分析 Jira 父任务（KAT-10938）下的子任务，解析描述中的列表项，统计未处理的项目并生成可视化报告。

## 功能

- 默认拉取父任务（KAT-10938）下**全部**子任务并统计列表条目
- 解析 ADF（Atlassian Document Format）描述中的列表项
- 检测条目状态：Done / Backlog / Moved / 删除线
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
│   └── report.py              # HTML/Markdown 报告生成
├── config.example.json         # 配置模板
├── requirements.txt            # Python 依赖
├── output/                     # 报告与定时任务日志（git 忽略）
└── .github/workflows/          # GitHub Actions 工作流
```

## 本地运行

需要本机已安装 **Node.js 18+** 与 **Python 3**。

### 1. 安装依赖

```bash
npm run setup
```

`setup` 会自动执行 `git:local-ignore`：在本机忽略 `output/jira-report.html` 的本地改动，**全选暂存**时不会再带上自动生成的报告。若仍出现在更改列表，可手动再跑一次：`npm run git:local-ignore`。

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

报告会生成到 `output/jira-report.html`，并在本地自动用浏览器打开。

### 常用脚本

| 命令 | 说明 |
|------|------|
| `npm start` | 拉取 Jira 数据并生成报告（默认） |
| `npm run analyze` | 同 `npm start` |
| `npm run serve` | 仅预览已有报告（静态文件，不拉 Jira） |
| `npm run dev` | **推荐本地使用**：定时拉取 Jira、更新报告，浏览器自动刷新（默认每 120 秒，见 `config.json` → `watch`） |

开发时改完 `data/scheduled.json` 或 Jira 后，保持 `npm run dev` 运行即可，无需反复手动 `npm start`。单次生成仍用 `npm start`。

## GitHub 部署

项目使用 GitHub Actions 每 4 小时自动运行（与本地相同：`npm run setup` → `npm start`），并将报告部署到 GitHub Pages。

### 1. 创建仓库

在 GitHub 上创建一个新仓库（建议设为 Private）。

### 2. 配置 Secrets

在仓库的 **Settings → Secrets and variables → Actions** 中添加：

| Secret 名称 | 说明 |
|---|---|
| `JIRA_BASE_URL` | Jira 实例地址，如 `https://your-domain.atlassian.net` |
| `JIRA_EMAIL` | Jira 账号邮箱 |
| `JIRA_API_TOKEN` | Jira API Token |
| `JIRA_PARENT_ISSUE` | 父任务编号，如 `KAT-10938` |

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

### 5. 查看报告

部署完成后，访问：`https://your-username.github.io/jira-analyzer/jira-report.html`

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

报告会对命中排期表的条目显示发布周标签；**排期状态** 支持：全部、已排期、排期已处理（Done/Backlog/Moved）、未排期。

### 统计口径

**总条目数 / 已处理 / 排期已处理**：父任务下**全部**子任务 Description 列表行的合计。**未处理 / 已排期**：仅 Jira 状态为 **待办**、**正在进行** 的子任务（API 的 `status.name`；界面上的「未处理」「进行中」与此对应，不是字面字符串 `未处理`/`进行中`）。`To Verify` 等 QA 后状态不计入。可在 `filters.active_statuses` 配置，也支持别名 `未处理`→`待办`、`进行中`→`正在进行`。

## 添加团队成员

编辑 `analyzer/owners.py`，在 `OWNERS` 字典中添加新成员：

```python
'username': ['Name', 'name', '@Name', '@Full Name'],
```

同时在 `OWNER_DISPLAY_NAMES` 中设置展示名称，在 `analyzer/report.py` 的 `OWNER_COLORS` 中设置颜色。
