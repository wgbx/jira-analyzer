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

## 模块地图

| 需求 | 文件 |
|------|------|
| 加/改团队成员 | `analyzer/owners.py` → **只改 `OWNER_REGISTRY`** |
| 列表解析 / Done·Backlog·划线 | `analyzer/parser.py`、`analyzer/statuses.py` |
| Jira API / 活跃状态 | `analyzer/jira_client.py`、`config` 的 `filters` |
| 排期标签 | `data/scheduled.json` + `analyzer/scheduled.py` |
| HTML / 筛选 UI | `analyzer/report.py`（颜色来自 registry） |
| 入口 / 多报告编排 | `jira_analyzer.py` |
| 配置模板（可提交） | `config.example.json` |
| 本地密钥（勿提交） | `config.json` |
| 操作 Jira 的 Agent 流程 | `skills/*.md` + 对应 `scripts/jira-*.py` |

## 铁律

1. 不提交 `config.json`、API Token、真实密钥。
2. 加成员只动 `OWNER_REGISTRY`；勿手改导出的 `OWNERS` / `OWNER_DISPLAY_NAMES`；勿在 `report.py` 再维护第二份调色板。
3. 改 Jira 内容时优先跑现有 `scripts/jira-*.py`，禁止为单次任务临时拼 disposable inline Python。
4. `output/` 是生成物；改报告逻辑后用 `npm start`（有 Token）或 `npm run serve` 验收。
5. 除非用户明确要求，不要顺手大拆 `report.py`（留给 Phase 3）。

## 常见改动菜谱

### 1. 加 Owner

1. 在 `analyzer/owners.py` 的 `OWNER_REGISTRY` 按团队分区插入一条。
2. 必填：`mentions`（与 Jira @ 显示名一致）、`display`；可选 `color`。
3. 书写顺序 = 筛选栏展示顺序。
4. 验证：`npm start` → 筛选栏出现新名字与颜色。

### 2. 改活跃状态 / 排除词

1. 改 `config.example.json` 的 `filters`（提交用模板）。
2. 同步本地 `config.json`（若存在）。
3. 口径：未处理统计只计 Jira 状态在 `active_statuses` 内的子任务；`exclude_keywords` 用于识别已处理前缀。
4. 验证：`npm start` 看汇总卡片数字是否符合预期。

### 3. 改主报告 UI

1. 主报告：`generate_html_report` 及 `_build_filter_*` / 相关 `_build_owner_*`。
2. 会议报告：`_build_meeting_report_html` 一带；Owner Daily：`generate_owner_daily_html_report`；Markdown：`generate_markdown_report`。勿混改。
3. 验证：`npm start` 或 `npm run serve` 打开对应 HTML。

### 4. 改 / 加 Skill

1. 先改 `skills/*.md` 的契约（含 frontmatter `description`，影响何时被选用）。
2. 再改对应 `scripts/jira-*.py`。
3. 保持「优先脚本、禁临时 Python」。
4. 验证：按 skill 文档中的命令跑一遍；`npm run smoke` 确保仓库仍健康。

## 验证清单

- [ ] `npm run smoke` 通过
- [ ] 有 Token：`npm start`，检查 `output/index.html`
- [ ] 仅预览：`npm run serve`

## 后续（勿在日常任务里展开）

- Phase 2：parser / owners / scheduled 单测 + CI  
- Phase 3：拆分 `report.py`，并同步更新本文件与 rules  
