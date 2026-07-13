#!/usr/bin/env python3
"""
Jira 任务分析器 - 入口脚本

按 config.reports 拉取多个父任务并生成多份 HTML 报告（如 Q3 首页 + /2026q2）。

使用方式:
    python jira_analyzer.py

定时运行（macOS launchd）:
    详见 com.jira.analyzer.plist

GitHub Actions:
    详见 .github/workflows/jira-report.yml
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from analyzer.config import (
    PROJECT_ROOT,
    load_config,
    ensure_output_dir,
    get_reports,
    OUTPUT_DIR,
)
from analyzer.jira_client import analyze_issues
from analyzer.report import generate_html_report, generate_markdown_report

REPORT_VERSION_FILE = OUTPUT_DIR / 'report-version.json'


def open_file(file_path):
    """
    使用系统默认程序打开文件（仅本地运行时调用）

    支持 macOS、Windows 和 Linux。
    """
    path_str = str(file_path)
    if sys.platform == 'darwin':
        subprocess.run(['open', path_str])
    elif sys.platform == 'win32':
        subprocess.run(['start', path_str], shell=True)
    elif sys.platform.startswith('linux'):
        subprocess.run(['xdg-open', path_str])


def _write_report_version():
    """写入报告版本戳，供开发预览页检测更新并自动刷新。"""
    ensure_output_dir()
    payload = {
        'updated': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
    }
    with open(REPORT_VERSION_FILE, 'w', encoding='utf-8') as f:
        json.dump(payload, f)


def _print_stats(analysis, label=None):
    prefix = f"[{label}] " if label else ""
    print(f"\n{prefix}统计结果:")
    print(f"  总条目数: {analysis['total']}")
    print(f"  已处理: {analysis['processed']}（{analysis.get('processed_jira', 0)} 个子任务）")
    print(f"  未处理: {analysis['unprocessed']}（{analysis.get('unprocessed_jira', 0)} 个子任务）")
    print(f"  已排期: {analysis.get('scheduled_unprocessed', 0)}")
    print(f"  排期已处理: {analysis.get('scheduled_processed', 0)}")


def _nav_href(from_output: str, to_output: str) -> str:
    """计算两份报告之间的相对链接（指向目录，便于 Pages 路径）。"""
    from_dir = Path(from_output).parent
    to_dir = Path(to_output).parent
    rel = os.path.relpath(to_dir, from_dir).replace('\\', '/')
    if rel == '.':
        return './'
    return rel if rel.endswith('/') else f'{rel}/'


def _nav_links_for(reports, current):
    return [
        {
            'label': r.get('label', r.get('id', '')),
            'href': _nav_href(current['output'], r['output']),
        }
        for r in reports
    ]


def _resolve_output_path(relative: str) -> Path:
    path = Path(relative)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def run_analyzer(config=None, *, quiet=False, open_browser=False):
    """
    拉取 Jira、按 reports 配置生成一份或多份报告。

    Returns:
        tuple[dict, Path]: (最后一份 analysis, 首份报告路径)
    """
    if config is None:
        config = load_config()

    if config['jira']['api_token'] == "YOUR_JIRA_API_TOKEN_HERE":
        print("\n⚠️ 请先在 config.json 中填写你的 Jira API Token")
        print("API Token 获取地址: https://id.atlassian.net/manage-profile/security/api-tokens")
        sys.exit(1)

    ensure_output_dir()

    if not quiet:
        print(f"正在刷新报告… ({datetime.now().strftime('%H:%M:%S')})")

    reports = get_reports(config)
    output_format = config.get('output', {}).get('format', 'html')
    base_url = config['jira']['base_url']

    first_path = None
    last_analysis = None

    for report_cfg in reports:
        label = report_cfg.get('label', report_cfg.get('id', ''))
        parent = report_cfg['parent_issue']
        run_config = {**config, 'parent_issue': parent}

        analysis = analyze_issues(run_config)
        last_analysis = analysis
        if not quiet:
            _print_stats(analysis, label)

        output_path = _resolve_output_path(report_cfg['output'])
        if first_path is None:
            first_path = output_path

        if output_format == 'markdown':
            content = generate_markdown_report(
                analysis, parent, label=label,
            )
        else:
            content = generate_html_report(
                analysis,
                base_url,
                parent,
                label=label,
                nav_links=_nav_links_for(reports, report_cfg),
            )

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)

        if not quiet:
            print(f"✅ [{label}] 报告已生成: {output_path}")

    _write_report_version()

    if open_browser and first_path:
        open_file(first_path)

    return last_analysis, first_path


def main():
    """主流程：加载配置 → 分析任务 → 生成报告"""
    print("=" * 50)
    print("Jira 任务分析器")
    print("=" * 50)

    is_ci = os.environ.get('CI') or os.environ.get('GITHUB_ACTIONS')
    run_analyzer(open_browser=not is_ci)


if __name__ == '__main__':
    main()
