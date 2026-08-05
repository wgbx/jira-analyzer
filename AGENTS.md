# AGENTS.md — 给写代码的 AI

本仓库由 AI 维护。改代码前先读本节；细节规则见 `.cursor/rules/`。设计说明：`docs/superpowers/specs/2026-08-05-ai-devex-design.md`。

## 一句话

定期拉取 Jira 父任务下子任务的描述列表 → 解析状态/负责人 → 生成可筛选 HTML 报告（多报告由 `config.reports` 驱动）。

## 命令

| 场景 | 命令 |
|------|------|
| 装依赖 | `npm run setup` |
| 拉 Jira 并生成报告 | `npm start`（需要本地 `config.json`） |
| 只预览已有报告 | `npm run serve` |
| 本地定时刷新 | `npm run dev` |
| 不连 Jira 冒烟 | `npm run smoke` |
| 单测 | `npm test` |

## 模块地图

| 需求 | 文件 |
|------|------|
| 加/改团队成员 | `analyzer/owners.py` → **只改 `OWNER_REGISTRY`** |
| 列表解析 / Done·Backlog·划线 | `analyzer/parser.py`、`analyzer/statuses.py` |
| Jira API / 活跃状态 | `analyzer/jira_client.py`、`config` 的 `filters` |
| 排期标签 | `data/scheduled.json` + `analyzer/scheduled.py` |
| HTML / 筛选 UI | `analyzer/report/`（`html_main.py` 主报告；`daily.py` / `meeting.py` / `markdown.py`；颜色来自 registry） |
| 入口 / 多报告编排 | `jira_analyzer.py` |
| 配置模板（勿提交） | 本地 `config.json`（模板在 README）；Actions 用 Secrets + `DEFAULT_REPORTS` |
| 本地密钥（勿提交） | `config.json` 的 `jira` 段 |
| 操作 Jira 的 Agent 流程 | `skills/*.md` + 对应 `scripts/jira-*.py` |

## 铁律

1. 不提交 `config.json`、API Token、真实密钥。
2. 加成员只动 `OWNER_REGISTRY`；勿手改导出的 `OWNERS` / `OWNER_DISPLAY_NAMES`；勿在 `analyzer/report/` 再维护第二份调色板。
3. 改 Jira 内容时优先跑现有 `scripts/jira-*.py`，禁止为单次任务临时拼 disposable inline Python。
4. `output/` 是生成物；改报告逻辑后用 `npm start`（有 Token）或 `npm run serve` 验收。
5. 除非用户明确要求，不要把 `analyzer/report/` 各模块重新合并成单文件。

## 常见改动菜谱

### 1. 加 Owner

1. 在 `analyzer/owners.py` 的 `OWNER_REGISTRY` 按团队分区插入一条。
2. 必填：`mentions`（与 Jira @ 显示名一致）、`display`；可选 `color`。
3. 书写顺序 = 筛选栏展示顺序。
4. 验证：`npm start` → 筛选栏出现新名字与颜色。

### 2. 改活跃状态 / 排除词 / 父任务

1. **本地**：改 `config.json` 的 `filters` / `reports`（模板见 README）。
2. **Actions 默认父任务**：改 `analyzer/config.py` 的 `DEFAULT_REPORTS`。
3. 口径：未处理统计只计 Jira 状态在 `active_statuses` 内的子任务（未配则用代码默认）。
4. 验证：`npm start` 看汇总卡片数字是否符合预期。

### 3. 改主报告 UI

1. 主报告：`analyzer/report/html_main.py` → `generate_html_report`；筛选 JS：`filters.py`；共享 helpers：`common.py`。
2. 会议块：`meeting.py`；Owner Daily：`daily.py`；Markdown：`markdown.py`。勿混改。
3. 验证：`npm start` 或 `npm run serve` 打开对应 HTML。

### 4. 改 / 加 Skill

1. 先改 `skills/*.md` 的契约（含 frontmatter `description`，影响何时被选用）。
2. 再改对应 `scripts/jira-*.py`。
3. 保持「优先脚本、禁临时 Python」。
4. 验证：按 skill 文档中的命令跑一遍；`npm run smoke && npm test` 确保仓库仍健康。

## 验证清单

- [ ] `npm run smoke` 通过
- [ ] `npm test` 通过
- [ ] 有 Token：`npm start`，检查 `output/index.html`
- [ ] 仅预览：`npm run serve`

## 已完成 / 后续

- Phase 1：AGENTS + Cursor rules + smoke  
- Phase 2：unittest（owners/parser/statuses/scheduled），本地 `npm test`  
- Phase 3：`analyzer/report/` 分包  

新功能优先落在对应子模块；勿再造巨型单文件。
