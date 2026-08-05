# AI 友好开发体验设计

日期：2026-08-05  
状态：Phase 1–3 已实现

## 目标

本仓库由 AI 编写与维护。目标：常见改动时几乎不需要口头补上下文；改完可自跑验证；报告逻辑可按表面编辑。

## 阶段

| 阶段 | 状态 | 内容 |
|------|------|------|
| Phase 1 | 完成 | `AGENTS.md` + Cursor rules + `npm run smoke` |
| Phase 2 | 完成 | `tests/` unittest + `npm test` + `.github/workflows/ci.yml` |
| Phase 3 | 完成 | `analyzer/report/` 分包 |

## 原则

- 规则短、可执行（改哪 / 别改哪 / 怎么验）
- `skills/` 服务操作 Jira；`.cursor/rules/` 服务改本仓库代码
- Owner 唯一真相：`OWNER_REGISTRY`
- 业务操作优先现有 `scripts/jira-*.py`
- 报告公开 API 保持：`from analyzer.report import generate_html_report, ...`

## `analyzer/report/` 分包

| 模块 | 职责 |
|------|------|
| `html_main.py` | 主报告 `generate_html_report` |
| `filters.py` | 筛选 JS、报告导航 |
| `daily.py` | Owner Daily 页 |
| `meeting.py` | 发布周会议统计块 |
| `markdown.py` | Markdown 报告 |
| `common.py` | 共享 helpers |
| `__init__.py` | 对外 re-export |

## 验收

- 「加 Owner」只改 `OWNER_REGISTRY`
- 「改口径」改对 `filters`
- 「主报告 UI」落到 `html_main` / `filters`，不误改 daily/meeting
- 「改 skill」走 skills + scripts
- `npm run smoke && npm test` 通过
