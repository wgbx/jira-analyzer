# Phase 2–3 Implementation Plan

> **For agentic workers:** Implement task-by-task. Steps use checkbox syntax.

**Goal:** Add offline unit tests (local), then split `analyzer/report.py` so AI can edit report surfaces without loading a 1600-line file.

**Architecture:** stdlib `unittest` under `tests/`; package `analyzer/report/` with thin `__init__.py` re-exports. Verification is local (`npm run smoke` / `npm test`); GitHub Actions only generates/deploys reports.

**Tech Stack:** Python 3.11 / unittest / existing npm scripts.

## Global Constraints

- Public imports stay stable: `from analyzer.report import generate_html_report, ...`
- No Jira network in tests or smoke
- Do not change report HTML behavior in the split (move-only refactor)
- Keep Cursor rules / AGENTS.md in sync after the split
- Do not add a separate Actions CI job for smoke/test (local only)

---

### Task 1: Unit tests

- [x] `tests/test_owners.py` — `detect_owner` / registry shape
- [x] `tests/test_statuses.py` — Done / Backlog / Invalid / Moved
- [x] `tests/test_parser.py` — ADF list parse + strikethrough + mentions
- [x] `tests/test_scheduled.py` — lookup + later release wins
- [x] `package.json` → `"test": "python3 -m unittest discover -s tests -v"`
- [x] `npm test` passes

### Task 2: CI on Actions — cancelled

- [x] ~~`.github/workflows/ci.yml`~~ 已移除；不在 Actions 重复跑 smoke/test
- [x] ~~jira-report 前置检查~~ 已移除

### Task 3: Split report.py

| Module | Responsibility |
|--------|----------------|
| `analyzer/report/common.py` | timestamp, counts, colors, item render helpers |
| `analyzer/report/filters.py` | filter JS + report nav |
| `analyzer/report/html_main.py` | `generate_html_report` |
| `analyzer/report/meeting.py` | meeting block HTML |
| `analyzer/report/daily.py` | `generate_owner_daily_html_report` |
| `analyzer/report/markdown.py` | `generate_markdown_report` |
| `analyzer/report/__init__.py` | public re-exports |

- [x] Delete `analyzer/report.py` after package works
- [x] `npm run smoke` + `npm test` + import check

### Task 4: Docs

- [x] Update `AGENTS.md` / `.cursor/rules/report-ui.mdc` for new paths
- [x] Note Phase 2/3 done in design spec
- [x] Commit
