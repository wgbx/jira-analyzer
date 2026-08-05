# AI 友好开发体验（Phase 1）设计

日期：2026-08-05  
状态：已批准并实现

## 目标

本仓库由 AI 编写与维护。Phase 1 目标：常见改动（加 Owner、改筛选、调主报告 UI、改 skill）时，新对话几乎不需要人再口头补项目上下文。

成功标准对齐「零口头补课」，不以大重构或完整测试套件为第一阶段交付。

## 方案

采用「说明书优先」：

- 写 `AGENTS.md` + Cursor rules
- 加不连 Jira 的冒烟脚本
- 不拆 `report.py`，不引入测试框架（留给 Phase 2/3）

## 产物

| 文件 | 作用 |
|------|------|
| `AGENTS.md` | 仓库级 Agent 地图 |
| `.cursor/rules/project.mdc` | 每轮自动带上的短总览 |
| `.cursor/rules/add-owner.mdc` | 加成员 |
| `.cursor/rules/report-ui.mdc` | 报告 UI 入口分流 |
| `.cursor/rules/config-filters.mdc` | 配置与筛选口径 |
| `.cursor/rules/skills.mdc` | skills ↔ scripts |
| `scripts/smoke-check.sh` | 无网络冒烟 |
| `package.json` → `npm run smoke` | 冒烟入口 |
| README | 链到 AGENTS；修正过时的加成员说明 |

## 原则

- 规则短、可执行（改哪 / 别改哪 / 怎么验）
- `skills/` 服务操作 Jira；`.cursor/rules/` 服务改本仓库代码
- Owner 唯一真相：`OWNER_REGISTRY`
- 业务操作优先现有 `scripts/jira-*.py`

## 路线图

| 阶段 | 目标 |
|------|------|
| Phase 1（本设计） | 零口头补课 |
| Phase 2 | parser/owners/scheduled 单测 + CI |
| Phase 3 | 拆分 `report.py`，同步更新规则 |

## 验收

- 「加 Owner」只改 `OWNER_REGISTRY`
- 「改口径」改对 `filters`（example + 本地 config）
- 「主报告 UI」落到正确入口，不误改 meeting/daily
- 「改 skill」走 skills + scripts，不写 disposable Python
- `npm run smoke` 通过
