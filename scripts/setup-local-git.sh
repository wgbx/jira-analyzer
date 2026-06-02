#!/usr/bin/env bash
# 本机一次性配置：忽略自动生成报告的本地改动，全选暂存不会带上该文件。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

REPORT="output/jira-report.html"
if ! git rev-parse --git-dir >/dev/null 2>&1; then
  echo "错误: 不在 git 仓库内" >&2
  exit 1
fi

# 确保报告在版本库中有记录（CI/Pages 用）；本地用 skip-worktree 屏蔽变更
if ! git cat-file -e "HEAD:${REPORT}" 2>/dev/null; then
  if [[ -f "$REPORT" ]]; then
    git add -f "$REPORT"
    echo "已将 ${REPORT} 纳入版本库（仅首次需要提交一次）"
  fi
fi

if [[ -f "$REPORT" ]]; then
  git update-index --skip-worktree "$REPORT"
  echo "✓ 已对本机设置 skip-worktree: ${REPORT}"
  echo "  之后 npm start / dev 更新报告不会出现在「更改」里，全选暂存也不会带上它。"
else
  echo "提示: 尚无 ${REPORT}，请先运行 npm start 后再执行: npm run git:local-ignore"
fi

for extra in output/report-version.json; do
  if [[ -f "$extra" ]]; then
    git update-index --skip-worktree "$extra" 2>/dev/null || true
  fi
done
