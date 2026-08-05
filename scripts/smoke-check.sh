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
  analyzer/report.py
  analyzer/config.py
  analyzer/jira_client.py
  config.example.json
  package.json
  skills
)

for p in "${REQUIRED_PATHS[@]}"; do
  [[ -e "$p" ]] || fail "missing path: $p"
done
ok "required paths exist"

python3 - <<'PY' || fail "config.example.json invalid"
import json
from pathlib import Path
cfg = json.loads(Path("config.example.json").read_text(encoding="utf-8"))
assert "reports" in cfg and isinstance(cfg["reports"], list) and cfg["reports"], "reports missing/empty"
assert "filters" in cfg and "active_statuses" in cfg["filters"], "filters.active_statuses missing"
print("config.example.json ok")
PY
ok "config.example.json"

python3 - <<'PY' || fail "import or OWNER_REGISTRY check failed"
from analyzer.owners import OWNER_REGISTRY, OWNERS, OWNER_DISPLAY_NAMES
from analyzer.parser import parse_list_items, extract_text_from_adf
from analyzer import report, config, jira_client  # noqa: F401

assert OWNER_REGISTRY, "OWNER_REGISTRY empty"
assert set(OWNERS) == set(OWNER_REGISTRY), "OWNERS keys mismatch registry"
assert set(OWNER_DISPLAY_NAMES) == set(OWNER_REGISTRY), "DISPLAY keys mismatch registry"
for key, entry in OWNER_REGISTRY.items():
    assert entry.get("mentions"), f"{key}: mentions required"
    assert entry.get("display"), f"{key}: display required"
print(f"registry ok ({len(OWNER_REGISTRY)} owners); parser exports ok")
PY
ok "imports + OWNER_REGISTRY"

PY_FILES=()
while IFS= read -r f; do
  PY_FILES+=("$f")
done < <(find analyzer -name '*.py' -print; printf '%s\n' jira_analyzer.py; find scripts -name '*.py' -print)
python3 -m py_compile "${PY_FILES[@]}" || fail "py_compile"
ok "py_compile"

echo "smoke: all checks passed"
