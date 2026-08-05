#!/usr/bin/env bash
# 触发 GitHub Actions：工作时段生成 Jira 分析报告（workflow_dispatch）
# 用法：
#   export GITHUB_TOKEN=ghp_xxx   # 需 actions:write（或 classic PAT 勾选 workflow）
#   ./scripts/trigger-github-report.sh
# 可选环境变量：
#   GITHUB_REPO   默认 wgbx/jira-analyzer
#   GITHUB_REF    默认 main

set -euo pipefail

REPO="${GITHUB_REPO:-wgbx/jira-analyzer}"
REF="${GITHUB_REF:-main}"
WORKFLOW="jira-report.yml"

if [[ -z "${GITHUB_TOKEN:-}" ]]; then
  echo "缺少 GITHUB_TOKEN。请先：export GITHUB_TOKEN=你的PAT" >&2
  exit 1
fi

url="https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW}/dispatches"
echo "触发 ${REPO} @ ${REF} → ${WORKFLOW}"

http_code=$(curl -sS -o /tmp/gh-dispatch-body.txt -w "%{http_code}" -X POST \
  -H "Authorization: Bearer ${GITHUB_TOKEN}" \
  -H "Accept: application/vnd.github+json" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  "${url}" \
  -d "{\"ref\":\"${REF}\"}")

if [[ "${http_code}" == "204" ]]; then
  echo "已触发（HTTP 204）。查看：https://github.com/${REPO}/actions/workflows/${WORKFLOW}"
  exit 0
fi

echo "触发失败 HTTP ${http_code}：" >&2
cat /tmp/gh-dispatch-body.txt >&2
exit 1
