#!/usr/bin/env python3
"""
Jira 任务分析器 - 入口脚本

定期分析 KAT-10938 子任务，统计未处理的项目并生成可视化报告。

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

from analyzer.config import load_config, ensure_output_dir, OUTPUT_DIR
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


def _print_stats(analysis):
    print(f"\n统计结果:")
    print(f"  总条目数: {analysis['total']}")
    print(f"  已处理: {analysis['processed']}")
    print(f"  未处理: {analysis['unprocessed']}")
    print(f"  已排期: {analysis.get('scheduled_unprocessed', 0)}")
    print(f"  排期已处理: {analysis.get('scheduled_processed', 0)}")


def run_analyzer(config=None, *, quiet=False, open_browser=False):
    """
    拉取 Jira、生成报告。

    Returns:
        tuple[dict, Path]: (analysis, output_path)
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

    analysis = analyze_issues(config)
    _print_stats(analysis) if not quiet else None

    output_format = config.get('output', {}).get('format', 'html')
    base_url = config['jira']['base_url']

    if output_format == 'markdown':
        parent = config.get('parent_issue', 'KAT-10938')
        report = generate_markdown_report(analysis, parent)
        output_path = OUTPUT_DIR / 'jira-report.md'
    else:
        parent = config.get('parent_issue', 'KAT-10938')
        report = generate_html_report(analysis, base_url, parent)
        output_path = OUTPUT_DIR / 'jira-report.html'

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report)

    _write_report_version()

    if not quiet:
        print(f"\n✅ 报告已生成: {output_path}")

    if open_browser:
        open_file(output_path)

    return analysis, output_path


def main():
    """主流程：加载配置 → 分析任务 → 生成报告"""
    print("=" * 50)
    print("Jira 任务分析器")
    print("=" * 50)

    is_ci = os.environ.get('CI') or os.environ.get('GITHUB_ACTIONS')
    run_analyzer(open_browser=not is_ci)


if __name__ == '__main__':
    main()
