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

import os
import subprocess
import sys

from analyzer.config import load_config, ensure_output_dir, OUTPUT_DIR
from analyzer.jira_client import analyze_issues
from analyzer.report import generate_html_report, generate_markdown_report


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


def main():
    """主流程：加载配置 → 分析任务 → 生成报告"""
    print("=" * 50)
    print("Jira 任务分析器")
    print("=" * 50)

    # 加载配置（支持环境变量和配置文件两种方式）
    config = load_config()

    # 检查 API Token 是否已填写
    if config['jira']['api_token'] == "YOUR_JIRA_API_TOKEN_HERE":
        print("\n⚠️ 请先在 config.json 中填写你的 Jira API Token")
        print("API Token 获取地址: https://id.atlassian.net/manage-profile/security/api-tokens")
        sys.exit(1)

    # 确保输出目录存在
    ensure_output_dir()

    # 分析任务
    analysis = analyze_issues(config)

    # 打印统计结果
    print(f"\n统计结果:")
    print(f"  总条目数: {analysis['total']}")
    print(f"  已处理: {analysis['processed']}")
    print(f"  未处理: {analysis['unprocessed']}")

    # 根据配置选择报告格式
    output_format = config.get('output', {}).get('format', 'html')
    base_url = config['jira']['base_url']

    if output_format == 'markdown':
        report = generate_markdown_report(analysis)
        output_path = OUTPUT_DIR / "jira-report.md"
    else:
        report = generate_html_report(analysis, base_url)
        output_path = OUTPUT_DIR / "jira-report.html"

    # 写入报告文件
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"\n✅ 报告已生成: {output_path}")

    # 本地运行时自动在浏览器中打开（CI 环境跳过）
    is_ci = os.environ.get('CI') or os.environ.get('GITHUB_ACTIONS')
    if not is_ci:
        open_file(output_path)


if __name__ == '__main__':
    main()
