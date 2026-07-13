#!/usr/bin/env bash
# 本机一次性配置：忽略自动生成报告的本地改动，全选暂存不会带上该文件。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

REPORTS=(
  "output/index.html"
  "output/2026q2/index.html"
  "output/jira-report.html"
)

if ! git rev-parse --git-dir >/dev/null 2>&1; then
  echo "错误: 不在 git 仓库内" >&2
  exit 1
fi

skip_one() {
  local report="$1"
  if [[ ! -f "$report" ]]; then
    return 0
  fi
  # 若已在版本库中，本机 skip-worktree；否则不强制 add（报告由 CI 生成）
  if git cat-file -e "HEAD:${report}" 2>/dev/null; then
    git update-index --skip-worktree "$report"
    echo "✓ 已对本机设置 skip-worktree: ${report}"
  else
    git update-index --skip-worktree "$report" 2>/dev/null || true
    echo "✓ 已对本机设置 skip-worktree: ${report}"
  fi
}

any=0
for report in "${REPORTS[@]}"; do
  if [[ -f "$report" ]]; then
    skip_one "$report"
    any=1
  fi
done

if [[ "$any" -eq 0 ]]; then
  echo "提示: 尚无报告文件，请先运行 npm start 后再执行: npm run git:local-ignore"
fi

for extra in output/report-version.json; do
  if [[ -f "$extra" ]]; then
    git update-index --skip-worktree "$extra" 2>/dev/null || true
  fi
done
