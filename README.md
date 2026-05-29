# Jira 任务分析器

定期分析 Jira 父任务（KAT-10938）下的子任务，解析描述中的列表项，统计未处理的项目并生成可视化报告。

## 功能

- 自动获取分配给当前用户的子任务
- 解析 ADF（Atlassian Document Format）描述中的列表项
- 检测条目状态：Done / Backlog / Moved / 删除线
- 自动识别条目的负责人（通过 @mention 和文本匹配）
- 生成带筛选功能的 HTML 报告
- 支持按人员筛选，包括未分配的条目

## 项目结构

```
jira-analyzer/
├── jira_analyzer.py           # 入口脚本
├── analyzer/                   # 核心模块
│   ├── config.py              # 配置管理（支持环境变量）
│   ├── owners.py              # 团队成员定义与匹配
│   ├── parser.py              # ADF 解析与状态检测
│   ├── jira_client.py         # Jira API 封装
│   └── report.py              # HTML/Markdown 报告生成
├── config.example.json         # 配置模板
├── requirements.txt            # Python 依赖
└── .github/workflows/          # GitHub Actions 工作流
```

## 本地运行

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置

复制配置模板并填写 Jira API Token：

```bash
cp config.example.json config.json
```

API Token 获取地址：https://id.atlassian.net/manage-profile/security/api-tokens

### 3. 运行

```bash
python jira_analyzer.py
```

报告会自动生成到 `output/jira-report.html` 并在浏览器中打开。

## GitHub 部署

项目使用 GitHub Actions 每小时自动运行，并将报告部署到 GitHub Pages。

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

## 添加团队成员

编辑 `analyzer/owners.py`，在 `OWNERS` 字典中添加新成员：

```python
'username': ['Name', 'name', '@Name', '@Full Name'],
```

同时在 `OWNER_DISPLAY_NAMES` 中设置展示名称，在 `analyzer/report.py` 的 `OWNER_COLORS` 中设置颜色。
