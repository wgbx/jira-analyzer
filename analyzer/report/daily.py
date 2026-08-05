"""Owner Daily HTML report."""

from analyzer.owners import OWNER_DISPLAY_NAMES, OWNERS
from analyzer.report.common import (
    _UPDATE_RULE_SHORT,
    _build_owner_css,
    _count_daily_processed_by_owner,
    _escape_html,
    _is_daily_task,
    _report_timestamp,
)
from analyzer.report.meeting import _build_meeting_report_html


def _build_owner_daily_chart(label, daily_stats):
    """生成 owner 季度 Daily 处理量柱状图。"""
    if not daily_stats:
        return ''

    rows = []
    max_items = max(stats['item_count'] for stats in daily_stats.values())
    sorted_stats = sorted(
        daily_stats.items(),
        key=lambda item: (item[1]['item_count'], item[1]['daily_count']),
        reverse=True,
    )

    for owner, stats in sorted_stats:
        display = OWNER_DISPLAY_NAMES.get(owner, owner)
        item_count = stats['item_count']
        width_pct = (item_count / max_items) * 100 if max_items else 0
        rows.append(
            f'<div class="owner-daily-row" data-owner="{owner}">'
            f'<div class="owner-daily-name"><span class="owner-tag owner-{owner}">{display}</span></div>'
            f'<div class="owner-daily-bar-track"><div class="owner-daily-bar owner-{owner}" style="width: {width_pct:.2f}%"></div></div>'
            f'<div class="owner-daily-value">{item_count} 条</div>'
            f'</div>'
        )

    return (
        f'<div class="owner-daily-chart" id="owner-daily-chart">'
        f'<div class="owner-daily-chart-title">{label} 季度 Daily 处理量</div>'
        f'<div class="owner-daily-chart-subtitle">按已处理条目数排序（多人协作条目会分别计入）</div>'
        f'<div class="owner-daily-chart-body">{"".join(rows)}</div>'
        f'</div>'
    )


def _build_owner_processed_item_rows(analysis, base_url):
    """生成统计页已处理条目明细行（仅 Daily 子任务）。"""
    rows = []
    for task_key in sorted(analysis.get('grouped', {}).keys(), reverse=True):
        task = analysis['grouped'][task_key]
        if not _is_daily_task(task.get('summary', '')):
            continue
        for item in task.get('items', []):
            if not item.get('is_processed'):
                continue
            owners = item.get('owners') or []
            owners_attr = ','.join(owners)
            owner_tags = ''.join(
                f'<span class="owner-tag owner-{o}">{OWNER_DISPLAY_NAMES.get(o, o)}</span>'
                for o in owners
            ) or '<span class="owner-tag">未分配</span>'
            rows.append(
                f'<li class="processed-item-row" data-owners="{owners_attr}">'
                f'<div class="processed-item-head">'
                f'<a class="processed-task-key" href="{base_url}/browse/{task_key}" target="_blank">{task_key}</a>'
                f'<span class="processed-item-index">{item["index"]}</span>'
                f'</div>'
                f'<div class="processed-item-content">{_escape_html(item["text"])}</div>'
                f'<div class="processed-item-owners">{owner_tags}</div>'
                f'</li>'
            )
    if not rows:
        return '<li class="processed-item-empty">暂无已处理条目</li>'
    return ''.join(rows)


def _build_owner_filter_buttons(daily_stats):
    """统计页人员筛选按钮。"""
    buttons = [
        '<button class="filter-btn active" data-filter="all" onclick="filterProcessedItems(\'all\')">全部</button>'
    ]
    for owner in OWNERS:
        if owner not in daily_stats:
            continue
        buttons.append(
            f'<button class="filter-btn" data-filter="{owner}" onclick="filterProcessedItems(\'{owner}\')">'
            f'{OWNER_DISPLAY_NAMES.get(owner, owner)}</button>'
        )
    return ''.join(buttons)


def generate_owner_daily_html_report(
    analysis,
    base_url,
    parent_issue='KAT-11542',
    *,
    label='Q3',
    back_href='./',
    meeting_report=None,
):
    """生成独立的季度 Daily 统计页。"""
    now = _report_timestamp()
    daily_stats = _count_daily_processed_by_owner(analysis)
    style_owners = set(daily_stats.keys())
    if meeting_report:
        style_owners.update(
            row['owner'] for row in meeting_report.get('owners') or []
            if row.get('owner') and row['owner'] != 'unassigned'
        )
    owner_css = _build_owner_css(style_owners)
    meeting_html = _build_meeting_report_html(meeting_report, base_url)
    chart_html = _build_owner_daily_chart(label, daily_stats) or (
        '<div class="empty-state">暂无 Daily 处理数据</div>'
    )
    processed_item_rows = _build_owner_processed_item_rows(analysis, base_url)
    filter_buttons = _build_owner_filter_buttons(daily_stats)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Jira {label} Daily 处理量统计</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f5f5f5; padding: 20px; }}
        .container {{ max-width: 1100px; margin: 0 auto; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 24px 28px; border-radius: 12px; margin-bottom: 20px; }}
        .header h1 {{ font-size: 24px; }}
        .header p {{ margin-top: 8px; opacity: 0.92; }}
        .back-link {{ display: inline-block; margin-top: 12px; color: white; font-weight: 600; text-decoration: none; border-bottom: 1px solid rgba(255,255,255,0.7); }}
        .back-link:hover {{ opacity: 0.9; }}
        .panel {{ background: white; border-radius: 12px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); }}
        .owner-daily-chart-title {{ font-size: 16px; font-weight: 700; color: #111827; margin-bottom: 6px; }}
        .owner-daily-chart-subtitle {{ font-size: 12px; color: #6b7280; margin-bottom: 14px; }}
        .owner-daily-chart-body {{ display: flex; flex-direction: column; gap: 10px; }}
        .owner-daily-row {{ display: grid; grid-template-columns: 120px 1fr 150px; align-items: center; gap: 10px; padding: 6px 0; border-radius: 8px; }}
        .owner-daily-name {{ display: flex; justify-content: flex-start; }}
        .owner-daily-bar-track {{ position: relative; height: 14px; background: #e5e7eb; border-radius: 999px; overflow: hidden; }}
        .owner-daily-bar {{ height: 100%; border-radius: 999px; min-width: 4px; }}
        .owner-daily-value {{ font-size: 13px; color: #374151; font-weight: 600; text-align: right; white-space: nowrap; }}
        .meeting-stats {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 12px;
            margin: 14px 0 18px;
        }}
        .meeting-stat {{
            background: #f9fafb;
            border: 1px solid #e5e7eb;
            border-radius: 10px;
            padding: 14px 16px;
        }}
        .meeting-stat-added {{ border-color: #bbf7d0; background: #f0fdf4; }}
        .meeting-stat-leftover {{ border-color: #fde68a; background: #fffbeb; }}
        .meeting-stat-label {{ font-size: 12px; color: #6b7280; font-weight: 600; }}
        .meeting-stat-value {{ font-size: 28px; font-weight: 700; color: #111827; margin-top: 4px; }}
        .meeting-stat-note {{ font-size: 12px; color: #6b7280; margin-top: 6px; line-height: 1.4; }}
        .meeting-table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
        .meeting-table th, .meeting-table td {{ padding: 10px 12px; border-bottom: 1px solid #e5e7eb; text-align: left; }}
        .meeting-table th {{ color: #374151; background: #f9fafb; }}
        .meeting-owner-row {{ cursor: pointer; }}
        .meeting-owner-row:hover {{ background: #f3f4f6; }}
        .meeting-owner-row.active {{ background: #eef2ff; }}
        .num-added {{ color: #15803d; font-weight: 700; }}
        .meeting-hint {{ font-size: 12px; color: #9ca3af; margin-top: 10px; }}
        .meeting-owner-detail {{
            margin-top: 14px;
            padding: 14px;
            border-radius: 10px;
            background: #f9fafb;
            border: 1px solid #e5e7eb;
        }}
        .meeting-detail-title {{ font-weight: 700; margin-bottom: 10px; color: #111827; }}
        .meeting-detail-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 16px;
        }}
        .meeting-detail-label {{ font-size: 12px; color: #6b7280; font-weight: 600; margin-bottom: 6px; }}
        .meeting-owner-detail ul {{ margin: 0; padding-left: 18px; color: #374151; font-size: 13px; line-height: 1.55; }}
        .meeting-owner-detail a {{ color: #667eea; text-decoration: none; font-weight: 600; }}
        .meeting-owner-detail a:hover {{ text-decoration: underline; }}
        .muted {{ color: #9ca3af; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
        th, td {{ padding: 10px 12px; border-bottom: 1px solid #e5e7eb; text-align: left; }}
        th {{ color: #374151; background: #f9fafb; }}
        .filter-bar {{
            display: flex;
            gap: 12px;
            flex-wrap: wrap;
            align-items: center;
            margin: 10px 0 16px;
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
        .filter-btn.active {{
            background: #667eea;
            border-color: #667eea;
            color: white;
        }}
        .processed-item-list {{
            list-style: none;
            display: flex;
            flex-direction: column;
            gap: 10px;
        }}
        .processed-item-row {{
            border-left: 3px solid #e5e7eb;
            background: #f9fafb;
            border-radius: 0 8px 8px 0;
            padding: 12px 14px;
        }}
        .processed-item-head {{
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 8px;
        }}
        .processed-task-key {{
            color: #667eea;
            text-decoration: none;
            font-weight: 600;
            font-size: 14px;
        }}
        .processed-task-key:hover {{ text-decoration: underline; }}
        .processed-item-index {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 24px;
            height: 24px;
            border-radius: 50%;
            background: #667eea;
            color: white;
            font-size: 12px;
            font-weight: 700;
        }}
        .processed-item-content {{
            color: #1f2937;
            line-height: 1.5;
            margin-bottom: 8px;
            word-break: break-word;
        }}
        .processed-item-owners {{
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
        }}
        .processed-item-empty {{
            color: #9ca3af;
            padding: 12px 4px;
        }}
        .owner-tag {{ display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 500; }}
{owner_css}
        .empty-state {{ color: #9ca3af; padding: 16px 0; }}
        @media (max-width: 780px) {{
            .owner-daily-row {{ grid-template-columns: 1fr; gap: 6px; }}
            .owner-daily-value {{ text-align: left; }}
            .meeting-stats {{ grid-template-columns: 1fr; }}
            .meeting-detail-grid {{ grid-template-columns: 1fr; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{label} 季度 Daily 处理量统计</h1>
            <p>父任务：{parent_issue} · 数据更新到 {now}（UTC+8）{_UPDATE_RULE_SHORT}</p>
            <a class="back-link" href="{back_href}">← 返回主报告</a>
        </div>
        {meeting_html}
        <div class="panel">{chart_html}</div>
        <div class="panel">
            <div class="owner-daily-chart-title">已处理条目明细</div>
            <div class="owner-daily-chart-subtitle">筛选某人可查看他处理过的具体条目；默认显示全部</div>
            <div class="filter-bar">
                <span class="filter-label">筛选人员:</span>
                {filter_buttons}
            </div>
            <ul id="processed-items-body" class="processed-item-list">{processed_item_rows}</ul>
        </div>
    </div>
    <script>
        let currentOwnerFilter = 'all';
        let currentMeetingOwner = null;
        function applyFilterButtonUI(owner) {{
            document.querySelectorAll('.filter-bar .filter-btn').forEach(btn => {{
                btn.classList.remove('active');
            }});
            const activeBtn = document.querySelector(`.filter-bar .filter-btn[data-filter="${{owner}}"]`);
            if (activeBtn) activeBtn.classList.add('active');
        }}
        function filterProcessedItems(owner) {{
            currentOwnerFilter = owner;
            applyFilterButtonUI(owner);
            const rows = document.querySelectorAll('#processed-items-body .processed-item-row');
            rows.forEach(row => {{
                if (owner === 'all') {{
                    row.style.display = '';
                    return;
                }}
                const owners = row.getAttribute('data-owners') || '';
                const ownerList = owners ? owners.split(',') : [];
                row.style.display = ownerList.includes(owner) ? '' : 'none';
            }});
        }}
        function toggleMeetingOwner(owner) {{
            const detail = document.getElementById('meeting-detail-' + owner);
            document.querySelectorAll('.meeting-owner-row').forEach(row => {{
                row.classList.toggle('active', row.getAttribute('data-owner') === owner && currentMeetingOwner !== owner);
            }});
            document.querySelectorAll('.meeting-owner-detail').forEach(el => {{
                el.hidden = true;
            }});
            if (!detail) {{
                currentMeetingOwner = null;
                return;
            }}
            if (currentMeetingOwner === owner) {{
                currentMeetingOwner = null;
                return;
            }}
            detail.hidden = false;
            currentMeetingOwner = owner;
        }}
    </script>
</body>
</html>"""
