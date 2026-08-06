# Unprocessed-by-Team Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show Wuhan / Chengdu / US unprocessed item counts on the main report「未处理」card.

**Architecture:** Add `team` on each `OWNER_REGISTRY` entry; count unprocessed items once via first known owner's team in `common.py`; render a sub-line on the unprocessed stat card in `html_main.py`.

**Tech Stack:** Python 3, unittest, existing HTML report modules.

## Global Constraints

- Count only `_counts_as_unprocessed` items; one count per item; first registry owner wins.
- No unassigned row; 0 still shown for each team.
- Do not change Markdown / Daily / Meeting reports.
- Owner single source: `OWNER_REGISTRY` only; no second palette/map.
- Verify: `npm run smoke && npm test`.

---

### Task 1: Registry `team` field

**Files:**
- Modify: `analyzer/owners.py`
- Modify: `tests/test_owners.py`
- Modify: `.cursor/rules/add-owner.mdc`, `AGENTS.md` (docs folded into this task)

**Interfaces:**
- Produces: every `OWNER_REGISTRY[key]['team']` ∈ `{'wuhan','chengdu','us'}`

- [ ] **Step 1: Write failing test** — assert each entry has valid `team`

```python
_VALID_TEAMS = {'wuhan', 'chengdu', 'us'}

def test_entries_have_valid_team(self):
    for key, entry in OWNER_REGISTRY.items():
        self.assertIn(entry.get('team'), _VALID_TEAMS, msg=key)
```

- [ ] **Step 2: Run test — expect FAIL** (`team` missing)

Run: `python3 -m unittest tests.test_owners.OwnerRegistryTests.test_entries_have_valid_team -v`

- [ ] **Step 3: Add `team` to every registry entry** (wuhan / chengdu / us by comment sections)

- [ ] **Step 4: Update add-owner docs** — require `team` in add-owner.mdc + AGENTS.md recipe

- [ ] **Step 5: Run tests — PASS**; commit

---

### Task 2: `_count_unprocessed_by_team`

**Files:**
- Create: `tests/test_report_common.py`
- Modify: `analyzer/report/common.py`

**Interfaces:**
- Consumes: `_counts_as_unprocessed`, `OWNER_REGISTRY`
- Produces: `_count_unprocessed_by_team(analysis) -> dict[str,int]` with keys `wuhan`,`chengdu`,`us`

- [ ] **Step 1: Write failing tests** for single team, cross-team first-owner, unassigned skipped

- [ ] **Step 2: Run — expect FAIL** (function missing)

- [ ] **Step 3: Implement `_count_unprocessed_by_team`**

- [ ] **Step 4: Run tests — PASS**; commit

---

### Task 3: HTML card sub-line

**Files:**
- Modify: `analyzer/report/html_main.py` (未处理 card ~389–391)

**Interfaces:**
- Consumes: `_count_unprocessed_by_team(analysis)`
- Produces: sub-line `武汉 N · 成都 N · US N` (0 still shown)

- [ ] **Step 1: Wire count into generate_html_report**; render under unprocessed card

- [ ] **Step 2: `npm run smoke && npm test`**

- [ ] **Step 3: Commit**
