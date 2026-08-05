"""报告生成包：HTML / Markdown / Daily 统计。"""

from analyzer.report.daily import generate_owner_daily_html_report
from analyzer.report.html_main import generate_html_report
from analyzer.report.markdown import generate_markdown_report

__all__ = [
    'generate_html_report',
    'generate_markdown_report',
    'generate_owner_daily_html_report',
]
