#!/usr/bin/env bash
# 不连 Jira 的仓库冒烟检查。失败退出非零。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

fail() { echo "smoke FAIL: $*" >&2; exit 1; }
ok() { echo "smoke OK: $*"; }

REQUIRED_PATHS=(
  AGENTS.md
  analyzer/owners.py
  analyzer/parser.py
  analyzer/report/__init__.py
  analyzer/report/html_main.py
  analyzer/config.py
  analyzer/jira_client.py
  package.json
  skills
)

for p in "${REQUIRED_PATHS[@]}"; do
  [[ -e "$p" ]] || fail "missing path: $p"
done
ok "required paths exist"

python3 - <<'PY' || fail "DEFAULT_REPORTS invalid"
from analyzer.config import DEFAULT_REPORTS, DEFAULT_OUTPUT, CONFIG_PATH
assert DEFAULT_REPORTS and isinstance(DEFAULT_REPORTS, list)
assert all(r.get("parent_issue") and r.get("output") for r in DEFAULT_REPORTS)
assert DEFAULT_OUTPUT.get("format")
assert CONFIG_PATH.name == "config.json"
print(f"DEFAULT_REPORTS ok ({len(DEFAULT_REPORTS)} reports)")
PY
ok "config defaults"

python3 - <<'PY' || fail "import or OWNER_REGISTRY check failed"
from analyzer.owners import OWNER_REGISTRY, OWNERS, OWNER_DISPLAY_NAMES
from analyzer.parser import parse_list_items, extract_text_from_adf
from analyzer.report import (
    generate_html_report,
    generate_markdown_report,
    generate_owner_daily_html_report,
)
from analyzer import config, jira_client  # noqa: F401

assert OWNER_REGISTRY, "OWNER_REGISTRY empty"
assert set(OWNERS) == set(OWNER_REGISTRY), "OWNERS keys mismatch registry"
assert set(OWNER_DISPLAY_NAMES) == set(OWNER_REGISTRY), "DISPLAY keys mismatch registry"
for key, entry in OWNER_REGISTRY.items():
    assert entry.get("mentions"), f"{key}: mentions required"
    assert entry.get("display"), f"{key}: display required"
assert callable(generate_html_report)
assert callable(generate_markdown_report)
assert callable(generate_owner_daily_html_report)
print(f"registry ok ({len(OWNER_REGISTRY)} owners); report package ok")
PY
ok "imports + OWNER_REGISTRY"

PY_FILES=()
while IFS= read -r f; do
  PY_FILES+=("$f")
done < <(find analyzer -name '*.py' -print; printf '%s\n' jira_analyzer.py; find scripts -name '*.py' -print)
python3 -m py_compile "${PY_FILES[@]}" || fail "py_compile"
ok "py_compile"

echo "smoke: all checks passed"
