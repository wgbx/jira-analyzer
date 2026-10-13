---
name: report-quarter-switch
description: >
  Use when 报告要换季度：新季度开始、用户给出新季度父任务号（如「Q4 的 Jira 号是 12205」「切到 Q1」「首页换成新季度」），
  或季度中旬上一季度已处理完、要下掉旧季度入口（「去掉 Q3」「不需要 Q3 入口了」「只保留当前季度」），
  或用户问「之前能看 QX 现在怎么没了」。
---

# 报告季度切换 / 下线上季度

报告列表由 `reports` 驱动：**当前季度在首页 `output/index.html`，上一季度在 `output/<年>q<季>/index.html`**。
季度号散落在配置、模块默认参数、脚本提示和文档里，按下表逐项改，最后用 grep 兜底。

## 当前状态（每次操作后更新本行）

仅保留 Q4=`KAT-12205` 首页（id `q4`）；Q3 已下线，历史快照保留。

## 场景 A：新季度开始（新季度上首页，旧季度挪到子路径）

用户给的数字补成 `KAT-<数字>`。下例以「Q1=`KAT-xxxxx` 上首页，Q4 挪到 `/2026q4/`」为例；跨年时子目录用**旧季度所在年份**。

| 位置 | 改法 |
|---|---|
| `analyzer/config.py` | `DEFAULT_PARENT_ISSUE` → 新号；`DEFAULT_REPORTS` 首项为新季度（`id: q1`、`output/index.html`），第二项为旧季度（**保留原 `id`**，output 改成 `output/2026q4/index.html`）；若还有更早季度则删掉；`get_reports` 回退分支的 `label` → 新季度 |
| 本地 `config.json` → `reports` | 与 `DEFAULT_REPORTS` 同构（勿提交） |
| 模块默认参数 | `analyzer/report/html_main.py`、`daily.py`、`markdown.py`、`analyzer/meeting_report.py`、`analyzer/snapshots.py`（`report_id` 默认值共 6 处 + `build_processed_snapshot`）→ 新季度 label / 父任务 / id |
| `scripts/serve.py` | 预览提示行改成旧季度子路径 |
| `scripts/setup-local-git.sh` | `REPORTS` 里的子目录换成新子路径（`index.html` + `daily-stats.html`） |
| 文档 | `README.md`（简介、功能、配置模板、Actions 说明、运行输出、查看报告）、`jira_analyzer.py` / `analyzer/report/filters.py` docstring、`.cursor/rules/report-ui.mdc` |
| 本地生成物 | 删除不再生成的旧子目录（如 `output/2026q3/`） |

**旧季度必须保留原 `id`**：快照存在 `output/snapshots/<id>/`，改 id 会丢掉发布周净增基线。
新季度第一次运行时没有基线（输出「尚无发布周基线快照」），这是正常的；需要线上基线时，单独提交新季度的快照 `output/snapshots/<新id>/<日期>.json`。

## 场景 B：季度中旬下线上季度入口

上季度条目处理完、不再需要入口时：

| 位置 | 改法 |
|---|---|
| `analyzer/config.py` → `DEFAULT_REPORTS` | 删掉旧季度那项（线上 Actions 只认这里） |
| 本地 `config.json` → `reports` | 同步删掉；只想临时隐藏可改成 `"enabled": false` |
| `scripts/serve.py` | 删掉旧季度预览提示行 |
| `scripts/setup-local-git.sh` | 删掉旧季度两条路径 |
| `README.md` | 删掉「并保留 QX」、功能里的 `+ /<子路径>/`、配置模板第二项、Actions 说明与运行输出 / 查看报告里的旧季度 |
| 本地生成物 | 删除 `output/<旧子路径>/` |

不用改的：季度切换导航只剩一份报告时自动隐藏；模块默认参数已指向当前季度；`output/snapshots/<旧id>/` 保留在 git 作为历史，**不要删**。
线上 `/<旧子路径>/` 会在下一次 Pages 部署后消失（部署产物是整个 `output/`）。

## 验证（两个场景都要做）

```bash
# 兜底：除本 skill 与 output/ 外不应再出现旧值（把占位换成实际旧父任务号 / 子目录 / 季度）
rg -n "KAT-旧号|旧子目录如2026q3|'Q旧'|'q旧'|\"Q旧\"" --glob '!output/**' --glob '!skills/report-quarter-switch.md'
npm run smoke && npm test
CI=1 npm start   # 看每份报告的「找到 N 个子任务」和输出路径是否符合预期
```

场景 B 时，`jira_analyzer.py`、`analyzer/report/filters.py`、`html_main.py` 的 docstring 里「如 Q4 ↔ Q3」这类示例命中可忽略（下次场景 A 再统一更新）。

## 提交

- 只提交代码 + 文档；`config.json` 永不提交；`output/` 下 HTML 由 CI 生成，不提交。
- 提交信息示例：`feat: switch reports to Q1 (KAT-xxxxx) home + Q4 at /2026q4/`、`chore: drop Q3 report entry`。
- 完成后更新本文件「当前状态」一行。

## 常见错误

| 错误 | 后果 |
|---|---|
| 只改本地 `config.json` | 线上 Actions 仍用 `DEFAULT_REPORTS`，站点不变 |
| 旧季度挪子路径时改了 `id` | 历史快照断开，会议块没有基线 |
| 忘了删本地 `output/<旧子路径>/` | `npm run serve` 还能打开过期报告，造成误判 |
