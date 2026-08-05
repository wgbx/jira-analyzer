"""Main HTML analysis report."""

from analyzer.report.common import (
    _UPDATE_RULE_SHORT,
    _build_filter_buttons,
    _build_owner_css,
    _count_daily_processed_by_owner,
    _count_unprocessed_by_owner,
    _find_all_done_active_tasks,
    _owners_needing_css,
    _render_item_li,
    _report_items,
    _report_timestamp,
    _visible_filter_owners,
)
from analyzer.report.filters import _build_filter_js, _build_report_nav


def generate_html_report(
    analysis,
    base_url,
    parent_issue='KAT-11542',
    *,
    label='Q3',
    nav_links=None,
    daily_stats_href=None,
):
    """
    生成 HTML 格式的分析报告

    报告包含统计概览、人员筛选栏和按任务分组的未处理条目列表。
    筛选功能通过前端 JavaScript 实现，无需后端支持。

    Args:
        analysis: analyze_issues() 返回的分析结果
        base_url: Jira 实例地址（如 https://xxx.atlassian.net）
        parent_issue: 父任务编号（用于标题展示）
        label: 季度标签，如 Q2 / Q3
        nav_links: 报告间导航 [{label, href}, ...]

    Returns:
        str: 完整的 HTML 文档字符串
    """
    now = _report_timestamp()
    owner_counts = _count_unprocessed_by_owner(analysis)
    daily_stats = _count_daily_processed_by_owner(analysis)
    visible_owners = _visible_filter_owners(analysis)
    show_unassigned = owner_counts.get('unassigned', 0) > 0
    style_owners = _owners_needing_css(analysis, visible_owners)
    style_owners.update(daily_stats.keys())
    owner_css = _build_owner_css(style_owners)
    filter_buttons = _build_filter_buttons(visible_owners, show_unassigned, owner_counts)
    filter_js = _build_filter_js(visible_owners, show_unassigned)
    title = f'Jira {label} 任务分析报告'
    nav_html = _build_report_nav(nav_links, label)
    header_daily_link = ''
    if daily_stats_href and daily_stats:
        header_daily_link = (
            f'<a class="header-stats-link" href="{daily_stats_href}">统计</a>'
        )

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #f5f5f5;
            padding: 20px;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 12px;
            margin-bottom: 30px;
            position: relative;
        }}
        .header-top {{
            margin-bottom: 4px;
        }}
        .header-stats-link {{
            position: absolute;
            right: 20px;
            top: 14px;
            font-size: 14px;
            font-weight: 600;
            text-decoration: none;
            color: #ffffff;
            white-space: nowrap;
        }}
        .header-stats-link:hover {{
            text-decoration: underline;
        }}
        .report-nav {{
            display: flex;
            gap: 8px;
            margin-bottom: 16px;
            flex-wrap: wrap;
        }}
        .report-nav .nav-link,
        .report-nav .nav-current {{
            display: inline-block;
            padding: 6px 14px;
            border-radius: 999px;
            font-size: 13px;
            font-weight: 600;
            text-decoration: none;
            color: white;
            border: 1px solid rgba(255, 255, 255, 0.45);
        }}
        .report-nav .nav-link:hover {{
            background: rgba(255, 255, 255, 0.18);
        }}
        .report-nav .nav-current {{
            background: rgba(255, 255, 255, 0.28);
            border-color: transparent;
        }}
        .header-subtitle {{
            margin-top: 8px;
            font-size: 16px;
            opacity: 0.95;
        }}
        .header-updated {{
            margin-top: 12px;
            font-size: 14px;
            opacity: 0.88;
            font-weight: 500;
        }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 16px;
            margin-bottom: 30px;
        }}
        @media (max-width: 1100px) {{
            .stats {{ grid-template-columns: repeat(3, 1fr); }}
        }}
        @media (max-width: 700px) {{
            .stats {{ grid-template-columns: repeat(2, 1fr); }}
            .header-stats-link {{
                right: 16px;
                top: 12px;
            }}
        }}
        .stat-card {{
            background: white;
            padding: 25px;
            border-radius: 12px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
            text-align: center;
        }}
        .stat-number {{ font-size: 36px; font-weight: bold; margin: 10px 0; }}
        .stat-sublabel {{ color: #9ca3af; font-size: 13px; margin-top: -4px; }}
        .stat-label {{ color: #666; font-size: 14px; }}
        .total {{ color: #667eea; }}
        .processed {{ color: #10b981; }}
        .unprocessed {{ color: #ef4444; }}
        .scheduled {{ color: #0d9488; }}
        .scheduled-processed {{ color: #6366f1; }}
        .task-section {{
            background: white;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        }}
        .task-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-bottom: 15px;
            border-bottom: 1px solid #eee;
            margin-bottom: 15px;
        }}
        .task-key {{ font-size: 18px; font-weight: 600; }}
        .task-key a {{ color: #667eea; text-decoration: none; }}
        .task-key a:hover {{ text-decoration: underline; }}
        .task-count {{
            background: #fef3c7;
            color: #92400e;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 14px;
        }}
        .item-list {{ list-style: none; }}
        .item {{
            padding: 12px 15px;
            border-left: 3px solid #e5e7eb;
            margin-bottom: 10px;
            background: #f9fafb;
            border-radius: 0 8px 8px 0;
        }}
        .item-index {{
            display: inline-block;
            background: #667eea;
            color: white;
            width: 24px;
            height: 24px;
            border-radius: 50%;
            text-align: center;
            line-height: 24px;
            font-size: 12px;
            margin-right: 10px;
        }}
        .item-content {{ display: inline-block; vertical-align: top; max-width: calc(100% - 40px); }}
        .item-text {{
            display: -webkit-box;
            -webkit-line-clamp: 3;
            -webkit-box-orient: vertical;
            overflow: hidden;
            line-height: 1.5;
            max-height: 4.5em;
        }}
        .item-meta {{ margin-top: 8px; display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }}
        .item-owners {{ display: flex; gap: 6px; flex-wrap: wrap; }}
        .scheduled-tag {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 600;
            background: #ccfbf1;
            color: #0f766e;
        }}
        .filter-btn.active-scheduled {{ background: #0d9488; border-color: #0d9488; color: white; }}
        .filter-btn.active-unscheduled {{ background: #f59e0b; border-color: #f59e0b; color: white; }}
        .filter-btn.active-scheduled-processed {{ background: #6366f1; border-color: #6366f1; color: white; }}
        .item-processed {{
            opacity: 0.85;
            border-left-color: #c7d2fe;
            background: #f5f3ff;
        }}
        .status-tag {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 600;
            background: #e0e7ff;
            color: #4338ca;
        }}
        .owner-tag {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 500;
        }}
{owner_css}
        .schedule-bar, .owner-bar {{
            background: white;
            padding: 20px;
            border-radius: 12px;
            margin-bottom: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
            display: flex;
            align-items: center;
            gap: 12px;
            flex-wrap: wrap;
        }}
        .filter-label {{ font-weight: 600; color: #374151; margin-right: 8px; }}
        .filter-btn {{
            padding: 6px 16px;
            border-radius: 20px;
            border: 2px solid #e5e7eb;
            background: white;
            color: #374151;
            font-size: 13px;
            cursor: pointer;
            transition: all 0.2s;
        }}
        .filter-btn:hover {{ border-color: #667eea; color: #667eea; }}
        .filter-btn.active {{ background: #667eea; color: white; border-color: #667eea; }}
        .filter-count {{
            font-size: 11px;
            background: rgba(255,255,255,0.3);
            padding: 1px 6px;
            border-radius: 10px;
            margin-left: 4px;
        }}
        .sort-bar {{
            background: white;
            padding: 20px;
            border-radius: 12px;
            margin-bottom: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
            display: flex;
            align-items: center;
            gap: 12px;
            flex-wrap: wrap;
        }}
        .sort-label {{ font-weight: 600; color: #374151; margin-right: 8px; }}
        .sort-btn {{
            padding: 6px 16px;
            border-radius: 20px;
            border: 2px solid #e5e7eb;
            background: white;
            color: #374151;
            font-size: 13px;
            cursor: pointer;
            transition: all 0.2s;
        }}
        .sort-btn:hover {{ border-color: #667eea; color: #667eea; }}
        .sort-btn.active {{ background: #667eea; color: white; border-color: #667eea; }}
        .stale-tasks {{
            background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
            border: 1px solid #f59e0b;
            border-radius: 12px;
            padding: 20px 24px;
            margin-bottom: 20px;
        }}
        .stale-tasks-title {{
            font-size: 16px;
            font-weight: 600;
            color: #92400e;
            margin-bottom: 12px;
        }}
        .stale-task-list {{
            list-style: none;
            display: flex;
            flex-direction: column;
            gap: 8px;
        }}
        .stale-task-item {{
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 8px 12px;
            background: rgba(255,255,255,0.7);
            border-radius: 8px;
            font-size: 14px;
        }}
        .stale-task-item a {{
            color: #92400e;
            font-weight: 600;
            text-decoration: none;
        }}
        .stale-task-item a:hover {{
            text-decoration: underline;
        }}
        .stale-task-summary {{
            color: #78350f;
            flex: 1;
        }}
        .stale-task-badge {{
            background: #f59e0b;
            color: white;
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 11px;
            font-weight: 600;
            white-space: nowrap;
        }}
        .empty-state {{ text-align: center; padding: 60px 20px; color: #9ca3af; }}
        .empty-icon {{ font-size: 64px; margin-bottom: 20px; }}
        .footer {{ text-align: center; color: #9ca3af; margin-top: 40px; font-size: 14px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="header-top">
                {nav_html}{header_daily_link}
            </div>
            <h1>{title}</h1>
            <p class="header-subtitle">{parent_issue} 所有项目概览</p>
            <p class="header-updated">数据更新到 {now}（UTC+8）{_UPDATE_RULE_SHORT}</p>
        </div>

        <div class="stats">
            <div class="stat-card">
                <div class="stat-label">总条目数</div>
                <div class="stat-number total">{analysis['total']}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">已处理</div>
                <div class="stat-number processed">{analysis['processed']}</div>
                <div class="stat-sublabel">{analysis.get('processed_jira', 0)} 个子任务</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">未处理</div>
                <div class="stat-number unprocessed">{analysis['unprocessed']}</div>
                <div class="stat-sublabel">{analysis.get('unprocessed_jira', 0)} 个子任务</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">已排期</div>
                <div class="stat-number scheduled">{analysis.get('scheduled_unprocessed', 0)}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">排期已处理</div>
                <div class="stat-number scheduled-processed">{analysis.get('scheduled_processed', 0)}</div>
            </div>
        </div>
"""

    # 提醒：所有条目已完成但 Jira 状态仍是活跃的子任务
    stale_tasks = _find_all_done_active_tasks(analysis)
    if stale_tasks:
        html += """
        <div class="stale-tasks">
            <div class="stale-tasks-title">⚠️ 以下子任务的所有条目都已处理，但 Jira 状态仍为活跃，请及时更新状态</div>
            <ul class="stale-task-list">
"""
        for t in stale_tasks:
            summary_display = t['summary'][:45] + ('...' if len(t['summary']) > 45 else '')
            html += (
                f'                <li class="stale-task-item">'
                f'<a href="{base_url}/browse/{t["key"]}" target="_blank">{t["key"]}</a>'
                f'<span class="stale-task-summary">{_escape_html(summary_display)}</span>'
                f'<span class="stale-task-badge">{_escape_html(t["status"])} · {t["total"]} 条已完成</span>'
                f'</li>\n'
            )
        html += """            </ul>
        </div>
"""

    html += f"""
        <div class="sort-bar">
            <span class="sort-label">排序方式:</span>
            <button class="sort-btn active" data-sort="key-desc" onclick="sortSections('key-desc')">任务编号 ↓</button>
            <button class="sort-btn" data-sort="key-asc" onclick="sortSections('key-asc')">任务编号 ↑</button>
            <button class="sort-btn" data-sort="count-desc" onclick="sortSections('count-desc')">未处理数量 ↓</button>
            <button class="sort-btn" data-sort="count-asc" onclick="sortSections('count-asc')">未处理数量 ↑</button>
        </div>

        <div class="schedule-bar">
            <span class="filter-label">排期状态:</span>
            <button class="filter-btn active" data-schedule="all" onclick="filterSchedule('all')">全部</button>
            <button class="filter-btn" data-schedule="scheduled" onclick="filterSchedule('scheduled')">已排期</button>
            <button class="filter-btn" data-schedule="scheduled-processed" onclick="filterSchedule('scheduled-processed')">排期已处理</button>
            <button class="filter-btn" data-schedule="unscheduled" onclick="filterSchedule('unscheduled')">未排期</button>
        </div>

        <div class="owner-bar">
            <span class="filter-label">筛选人员:</span>
            {filter_buttons}
        </div>
"""

    # 渲染条目（未处理 + 排期已处理）
    html += '    <div id="task-container" class="task-container">' + "\n"
    has_any_items = False
    if analysis['grouped']:
        for task_key in sorted(analysis['grouped'].keys(), reverse=True):
            task = analysis['grouped'][task_key]
            display_items = _report_items(task['items'], analysis)
            if not display_items:
                continue
            has_any_items = True

            unprocessed_count = sum(1 for i in display_items if not i.get('is_processed'))
            scheduled_unprocessed_count = sum(
                1 for i in display_items
                if not i.get('is_processed') and i.get('is_scheduled')
            )
            scheduled_done_count = sum(
                1 for i in display_items if i.get('is_processed') and i.get('is_scheduled')
            )
            summary_display = task['summary'][:50] + ('...' if len(task['summary']) > 50 else '')
            count_hint = (
                f"{unprocessed_count} 未处理 · "
                f"{scheduled_unprocessed_count} 已排期 · "
                f"{scheduled_done_count} 排期已处理"
            )

            html += f"""
        <div class="task-section" data-key="{task_key}" data-count="{unprocessed_count}">
            <div class="task-header">
                <span class="task-key"><a href="{base_url}/browse/{task_key}" target="_blank">{task_key}</a></span>
                <span class="task-summary">{summary_display}</span>
                <span class="task-count">{count_hint}</span>
            </div>
            <ul class="item-list">"""

            for item in display_items:
                html += _render_item_li(item)

            html += """
            </ul>
        </div>"""
    if not has_any_items:
        html += """
        <div class="empty-state">
            <div class="empty-icon">🎉</div>
            <h3>太棒了！</h3>
            <p>没有未处理的项目</p>
        </div>"""
    html += "    </div>\n"

    html += f"""
        <div class="footer">
            <p>Generated by Jira Analyzer</p>
        </div>
    </div>
{filter_js}
</body>
</html>"""

    return html
