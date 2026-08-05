"""
报告生成模块

将分析结果渲染为 HTML 或 Markdown 格式的可视化报告。
"""

import re
from datetime import datetime
from zoneinfo import ZoneInfo

_REPORT_TZ = ZoneInfo('Asia/Shanghai')


def _report_timestamp():
    """报告展示的拉取时间（东八区）。"""
    return datetime.now(_REPORT_TZ).strftime('%Y-%m-%d %H:%M:%S')


# 与外部 cron（北京时间 9–20 点整点）一致；推送 main / 手动触发也会更新
_UPDATE_RULE_SHORT = '9:00–20:00 每小时自动更新'

from analyzer.config import OUTPUT_DIR
from analyzer.jira_client import DEFAULT_ACTIVE_STATUSES, is_active_issue_status
from analyzer.owners import OWNERS, OWNER_DISPLAY_NAMES, OWNER_REGISTRY


def _active_statuses_for_analysis(analysis):
    return tuple(analysis.get('active_statuses') or DEFAULT_ACTIVE_STATUSES)


def _counts_as_unprocessed(item, analysis):
    """描述未处理，且子任务 Jira 状态在活跃集合内。"""
    if item.get('is_processed'):
        return False
    return is_active_issue_status(item.get('issue_status', ''), analysis)


_DEFAULT_OWNER_COLOR = ('#f3f4f6', '#374151')
_DAILY_TASK_RE = re.compile(r'\bDaily\b', re.IGNORECASE)


def _is_daily_task(summary):
    return bool(_DAILY_TASK_RE.search(summary or ''))


def _count_daily_processed_by_owner(analysis):
    """统计 owner 在 Daily 子任务中的已处理量。"""
    daily_issues = {owner: set() for owner in OWNERS}
    item_counts = {owner: 0 for owner in OWNERS}

    for task_key, task in analysis.get('grouped', {}).items():
        if not _is_daily_task(task.get('summary', '')):
            continue
        for item in task.get('items', []):
            if not item.get('is_processed'):
                continue
            for owner in (item.get('owners') or []):
                if owner not in daily_issues:
                    continue
                daily_issues[owner].add(task_key)
                item_counts[owner] += 1

    return {
        owner: {
            'daily_count': len(daily_issues[owner]),
            'item_count': item_counts[owner],
        }
        for owner in OWNERS
        if item_counts[owner] > 0
    }


def _owner_color(owner):
    return (OWNER_REGISTRY.get(owner) or {}).get('color') or _DEFAULT_OWNER_COLOR


def _count_unprocessed_by_owner(analysis):
    """
    统计未处理条目中各 owner 的条目数（一条含多人时分别计入各 owner）
    """
    counts = {owner: 0 for owner in OWNERS}
    counts['unassigned'] = 0
    counts['all'] = 0

    for task in analysis.get('grouped', {}).values():
        for item in task.get('items', []):
            if not _counts_as_unprocessed(item, analysis):
                continue
            counts['all'] += 1
            owners = item.get('owners') or []
            if not owners:
                counts['unassigned'] += 1
            else:
                for o in owners:
                    if o in counts:
                        counts[o] += 1
    return counts


def _visible_filter_owners(analysis):
    """返回在未处理条目中有数量的 owner 标识列表"""
    counts = _count_unprocessed_by_owner(analysis)
    return [o for o in OWNERS if counts.get(o, 0) > 0]


def _owners_needing_css(analysis, visible_owners):
    """条目标签与筛选按钮所需的 owner 样式集合"""
    needed = set(visible_owners)
    for task in analysis.get('grouped', {}).values():
        for item in task.get('items', []):
            if not _counts_as_unprocessed(item, analysis):
                continue
            needed.update(item.get('owners') or [])
    return needed


def _build_owner_css(owners):
    """生成 owner 标签和筛选按钮的 CSS 样式"""
    css = ""
    # owner 标签样式
    for owner in owners:
        bg, color = _owner_color(owner)
        css += f"        .owner-{owner} {{ background: {bg}; color: {color}; }}\n"
        css += (
            f"        .owner-daily-bar.owner-{owner} "
            f"{{ background: linear-gradient(90deg, {color} 0%, {color}cc 100%); }}\n"
        )
    # 筛选按钮激活样式
    for owner in owners:
        _, color = _owner_color(owner)
        css += f"        .filter-btn.active-{owner} {{ background: {color}; border-color: {color}; color: white; }}\n"
    css += "        .filter-btn.active-unassigned {{ background: #6b7280; border-color: #6b7280; color: white; }}\n"
    return css


def _find_all_done_active_tasks(analysis):
    """
    找出「所有条目都已处理，但 Jira 状态仍是活跃」的子任务。

    用于提醒用户去 Jira 上把状态改为 Done / Closed。
    """
    results = []
    active_statuses = tuple(analysis.get('active_statuses') or DEFAULT_ACTIVE_STATUSES)
    for task_key, task in analysis.get('grouped', {}).items():
        items = task.get('items', [])
        if not items:
            continue
        issue_status = task.get('issue_status', '')
        resolved = issue_status
        if not all(item.get('is_processed') for item in items):
            continue
        if resolved not in active_statuses:
            continue
        results.append({
            'key': task_key,
            'summary': task['summary'],
            'status': issue_status,
            'total': len(items),
        })
    return results


def _report_items(task_items, analysis):
    """报告中展示：活跃状态下的未处理 + 全部子任务的排期已处理。"""
    unprocessed = [
        i for i in task_items
        if _counts_as_unprocessed(i, analysis)
    ]
    processed_scheduled = [
        i for i in task_items
        if i.get('is_processed') and i.get('is_scheduled')
    ]
    return unprocessed + processed_scheduled


def _processed_status_label(item):
    """已处理条目的状态标签文案。"""
    if item.get('is_done'):
        return 'Done'
    if item.get('is_backlog'):
        return item.get('backlog_label') or 'Backlog'
    if item.get('is_moved'):
        return 'Moved'
    if item.get('is_strikethrough'):
        return '删除线'
    return '已处理'


def _escape_html(text):
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def _markdown_item_line(item, include_status=False):
    """Markdown 单条列表项。"""
    owners_str = ' '.join(f'`{OWNER_DISPLAY_NAMES.get(o, o)}`' for o in item['owners'])
    schedule_str = ''
    if item.get('is_scheduled') and item.get('scheduled_release'):
        schedule_str = f' `[已排期: {item["scheduled_release"]}]`'
    status_str = ''
    if include_status and item.get('is_processed'):
        status_str = f' `[{_processed_status_label(item)}]`'
    line = f"- **第 {item['index']} 点**: {item['text']}{schedule_str}{status_str}"
    if owners_str:
        line += f"  {owners_str}"
    return line + "\n"


def _render_item_li(item):
    """渲染单条列表项 HTML。"""
    owner_tags = ''.join(
        f'<span class="owner-tag owner-{o}">{OWNER_DISPLAY_NAMES.get(o, o)}</span>'
        for o in item['owners']
    )
    owners_attr = ','.join(item['owners']) if item['owners'] else ''
    is_scheduled = item.get('is_scheduled', False)
    is_processed = item.get('is_processed', False)
    scheduled_attr = 'true' if is_scheduled else 'false'
    processed_attr = 'true' if is_processed else 'false'
    release_label = item.get('scheduled_release') or ''
    scheduled_tag = (
        f'<span class="scheduled-tag">{release_label}</span>'
        if is_scheduled and release_label
        else ''
    )
    status_tag = ''
    if is_processed:
        status_label = _processed_status_label(item)
        status_tag = f'<span class="status-tag status-processed">{status_label}</span>'

    safe_text = _escape_html(item['text'])
    item_class = 'item item-row' + (' item-processed' if is_processed else '')

    return f"""
                <li class="{item_class}" data-owners="{owners_attr}" data-scheduled="{scheduled_attr}" data-processed="{processed_attr}">
                    <span class="item-index">{item['index']}</span>
                    <span class="item-content">
                        <span class="item-text">{safe_text}</span>
                        <div class="item-meta">
                            {scheduled_tag}{status_tag}
                            <div class="item-owners">{owner_tags}</div>
                        </div>
                    </span>
                </li>"""


def _filter_count_badge(count):
    """筛选按钮上的固定条目数（不随人员筛选变化）。"""
    return str(count) if count else ''


def _build_filter_buttons(visible_owners, show_unassigned, owner_counts):
    """生成筛选栏按钮 HTML（仅包含有未处理条目的 owner）"""
    buttons = [
        '<button class="filter-btn active" data-filter="all" '
        'onclick="filterItems(\'all\')">全部<span class="filter-count" id="count-all">'
        f'{_filter_count_badge(owner_counts.get("all", 0))}</span></button>',
    ]
    for owner in visible_owners:
        display = OWNER_DISPLAY_NAMES[owner]
        cnt = owner_counts.get(owner, 0)
        buttons.append(
            f'<button class="filter-btn" data-filter="{owner}" '
            f'onclick="filterItems(\'{owner}\')">{display}'
            f'<span class="filter-count" id="count-{owner}">'
            f'{_filter_count_badge(cnt)}</span></button>'
        )
    if show_unassigned:
        buttons.append(
            '<button class="filter-btn" data-filter="unassigned" '
            'onclick="filterItems(\'unassigned\')">未分配'
            f'<span class="filter-count" id="count-unassigned">'
            f'{_filter_count_badge(owner_counts.get("unassigned", 0))}</span></button>'
        )
    return '\n            '.join(buttons)


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


def _build_owner_daily_table_rows(daily_stats):
    # 统计明细面板已下线，保留函数占位避免影响历史引用。
    return ''


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


def _build_filter_js(visible_owners, show_unassigned):
    """生成筛选功能的 JavaScript 代码（人员 + 排期状态）。"""
    owner_keys = list(visible_owners)
    count_keys = ['all'] + owner_keys + (['unassigned'] if show_unassigned else [])
    counts_init = ', '.join([f'{k}: 0' for k in count_keys])
    counts_checks = '\n'.join([
        f"                    if (ownerList.includes('{k}')) counts.{k}++;"
        for k in owner_keys
    ])
    remove_class_parts = [f"'active-{k}'" for k in owner_keys]
    if show_unassigned:
        remove_class_parts.append("'active-unassigned'")
    remove_class_parts.append("'active'")
    remove_owner_classes = ', '.join(remove_class_parts)

    if show_unassigned:
        count_loop = """
                if (!owners) {
                    counts.unassigned++;
                } else {
                    const ownerList = owners.split(',');
""" + counts_checks + """
                }"""
    else:
        count_loop = """
                if (owners) {
                    const ownerList = owners.split(',');
""" + counts_checks + """
                }"""

    return """
    <script>
        let currentOwnerFilter = 'all';
        let currentScheduleFilter = 'all';
        let currentSort = 'key-desc';
        let currentProjectFilter = null;

        const URL_DEFAULTS = { sort: 'key-desc', schedule: 'all', owner: 'all' };
        const VALID_SORTS = ['key-desc', 'key-asc', 'count-desc', 'count-asc'];
        const VALID_SCHEDULES = ['all', 'scheduled', 'unscheduled', 'scheduled-processed'];

        function parseProjectParam(value) {
            if (!value) return null;
            const keys = value.split(',').map(k => k.trim().toUpperCase()).filter(Boolean);
            return keys.length ? new Set(keys) : null;
        }

        function matchesProjectFilter(sectionKey) {
            if (!currentProjectFilter) return true;
            return currentProjectFilter.has((sectionKey || '').toUpperCase());
        }

        function syncUrlParams() {
            const params = new URLSearchParams(window.location.search);
            if (currentSort === URL_DEFAULTS.sort) params.delete('sort');
            else params.set('sort', currentSort);
            if (currentScheduleFilter === URL_DEFAULTS.schedule) params.delete('schedule');
            else params.set('schedule', currentScheduleFilter);
            if (currentOwnerFilter === URL_DEFAULTS.owner) params.delete('owner');
            else params.set('owner', currentOwnerFilter);
            if (!currentProjectFilter) params.delete('project');
            else params.set('project', [...currentProjectFilter].join(','));
            const qs = params.toString();
            const newUrl = qs ? `${window.location.pathname}?${qs}` : window.location.pathname;
            history.replaceState(null, '', newUrl);
        }

        function matchesScheduleFilter(processed, scheduled) {
            if (currentScheduleFilter === 'all') {
                return !processed;
            }
            if (currentScheduleFilter === 'scheduled') {
                return scheduled && !processed;
            }
            if (currentScheduleFilter === 'unscheduled') {
                return !scheduled && !processed;
            }
            if (currentScheduleFilter === 'scheduled-processed') {
                return scheduled && processed;
            }
            return false;
        }

        function updateCounts() {
            const allItems = document.querySelectorAll('li.item-row');
            const counts = { """ + counts_init + """ };
            allItems.forEach(li => {
                const scheduled = li.getAttribute('data-scheduled') === 'true';
                const processed = li.getAttribute('data-processed') === 'true';
                if (!matchesScheduleFilter(processed, scheduled)) return;
                counts.all++;
                const owners = li.getAttribute('data-owners');
""" + count_loop + """
            });
            for (const [key, count] of Object.entries(counts)) {
                const el = document.getElementById('count-' + key);
                if (el) el.textContent = count || '';
            }
        }

        function applyFilters() {
            const allItems = document.querySelectorAll('li.item-row');
            allItems.forEach(li => {
                const owners = li.getAttribute('data-owners');
                const scheduled = li.getAttribute('data-scheduled') === 'true';
                const processed = li.getAttribute('data-processed') === 'true';

                let showOwner = false;
                if (currentOwnerFilter === 'all') {
                    showOwner = true;
                } else if (currentOwnerFilter === 'unassigned') {
                    showOwner = !owners;
                } else {
                    showOwner = owners && owners.split(',').includes(currentOwnerFilter);
                }

                const showSchedule = matchesScheduleFilter(processed, scheduled);
                li.style.display = showOwner && showSchedule ? '' : 'none';
            });

            document.querySelectorAll('.task-section').forEach(section => {
                const sectionKey = section.getAttribute('data-key');
                if (!matchesProjectFilter(sectionKey)) {
                    section.style.display = 'none';
                    return;
                }
                const visibleItems = section.querySelectorAll('li.item-row:not([style*="display: none"])');
                section.style.display = visibleItems.length > 0 ? '' : 'none';
            });
            updateCounts();
        }

        function applyOwnerFilterUI(filter) {
            document.querySelectorAll('.owner-bar .filter-btn').forEach(btn => {
                btn.classList.remove(""" + remove_owner_classes + """);
            });
            const activeBtn = document.querySelector(`.owner-bar .filter-btn[data-filter="${filter}"]`);
            if (activeBtn) {
                if (filter === 'all') {
                    activeBtn.classList.add('active');
                } else {
                    activeBtn.classList.add('active-' + filter);
                }
            }
        }

        function applyScheduleFilterUI(filter) {
            document.querySelectorAll('.schedule-bar .filter-btn').forEach(btn => {
                btn.classList.remove(
                    'active', 'active-scheduled', 'active-unscheduled', 'active-scheduled-processed'
                );
            });
            const activeBtn = document.querySelector(`.schedule-bar .filter-btn[data-schedule="${filter}"]`);
            if (activeBtn) {
                if (filter === 'all') {
                    activeBtn.classList.add('active');
                } else if (filter === 'scheduled') {
                    activeBtn.classList.add('active-scheduled');
                } else if (filter === 'scheduled-processed') {
                    activeBtn.classList.add('active-scheduled-processed');
                } else {
                    activeBtn.classList.add('active-unscheduled');
                }
            }
        }

        function applySortUI(sortBy) {
            document.querySelectorAll('.sort-btn').forEach(btn => btn.classList.remove('active'));
            const activeBtn = document.querySelector(`.sort-btn[data-sort="${sortBy}"]`);
            if (activeBtn) activeBtn.classList.add('active');
        }

        function filterItems(filter, options = {}) {
            const btn = document.querySelector(`.owner-bar .filter-btn[data-filter="${filter}"]`);
            if (!btn) return;
            currentOwnerFilter = filter;
            applyOwnerFilterUI(filter);
            if (!options.skipApply) {
                applyFilters();
                if (!options.skipUrl) syncUrlParams();
            }
        }

        function filterSchedule(filter, options = {}) {
            if (!VALID_SCHEDULES.includes(filter)) return;
            currentScheduleFilter = filter;
            applyScheduleFilterUI(filter);
            if (!options.skipApply) {
                applyFilters();
                if (!options.skipUrl) syncUrlParams();
            }
        }

        function sortSections(sortBy, options = {}) {
            if (!VALID_SORTS.includes(sortBy)) return;
            currentSort = sortBy;
            applySortUI(sortBy);

            const container = document.getElementById('task-container');
            if (!container) return;
            const sections = Array.from(container.querySelectorAll('.task-section'));

            sections.sort((a, b) => {
                const keyA = a.getAttribute('data-key') || '';
                const keyB = b.getAttribute('data-key') || '';
                const numA = parseInt(keyA.replace(/[^0-9]/g, '')) || 0;
                const numB = parseInt(keyB.replace(/[^0-9]/g, '')) || 0;
                const countA = parseInt(a.getAttribute('data-count')) || 0;
                const countB = parseInt(b.getAttribute('data-count')) || 0;

                switch (sortBy) {
                    case 'key-desc': return numB - numA;
                    case 'key-asc': return numA - numB;
                    case 'count-desc': return countB - countA || numB - numA;
                    case 'count-asc': return countA - countB || numA - numB;
                    default: return numB - numA;
                }
            });

            sections.forEach(section => container.appendChild(section));
            if (!options.skipUrl) syncUrlParams();
        }

        function initFromUrl() {
            const params = new URLSearchParams(window.location.search);
            currentProjectFilter = parseProjectParam(params.get('project'));

            const schedule = params.get('schedule');
            if (schedule && VALID_SCHEDULES.includes(schedule)) {
                filterSchedule(schedule, { skipApply: true, skipUrl: true });
            } else {
                applyScheduleFilterUI(currentScheduleFilter);
            }

            const owner = params.get('owner');
            if (owner) {
                const ownerBtn = document.querySelector(`.owner-bar .filter-btn[data-filter="${owner}"]`);
                if (ownerBtn) {
                    currentOwnerFilter = owner;
                    applyOwnerFilterUI(owner);
                } else {
                    applyOwnerFilterUI(currentOwnerFilter);
                }
            } else {
                applyOwnerFilterUI(currentOwnerFilter);
            }

            const sort = params.get('sort');
            if (sort && VALID_SORTS.includes(sort)) {
                sortSections(sort, { skipUrl: true });
            } else {
                applySortUI(currentSort);
            }

            applyFilters();
            syncUrlParams();
        }

        initFromUrl();
    </script>"""


def _build_report_nav(nav_links, current_label):
    """报告间切换导航（如 Q3 ↔ Q2）。"""
    if not nav_links or len(nav_links) < 2:
        return ''
    items = []
    for link in nav_links:
        label = link.get('label', '')
        href = link.get('href', './')
        if label == current_label:
            items.append(f'<span class="nav-current">{label}</span>')
        else:
            items.append(f'<a class="nav-link" href="{href}">{label}</a>')
    return f'<nav class="report-nav" aria-label="季度切换">{"".join(items)}</nav>'


def generate_html_report(
    analysis,
    base_url,
    parent_issue='KAT-11542',
    *,
    label='Q3',
    nav_links=None,
    daily_stats_href=None,
    favicon_href='favicon.svg',
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
    <link rel="shortcut icon" href="{favicon_href}">
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


def _escape_attr(text):
    return _escape_html(text).replace('"', '&quot;')


def _build_meeting_report_html(meeting, base_url):
    """统计页顶部：发布周排期进度三列 + 按人表。"""
    if not meeting:
        return ''

    release = _escape_html(meeting.get('release_label') or '当前发布周')
    week_start = meeting.get('week_start') or meeting.get('previous_date')
    week_end = meeting.get('week_end') or meeting.get('release_date')
    if meeting.get('has_diff'):
        added_value = f"+{meeting['unique_added']}"
        range_parts = []
        if week_start and week_end:
            range_parts.append(f"发布周 {week_start} → {week_end}")
        range_parts.append(
            f"快照 {meeting.get('baseline_date')} → {meeting.get('current_date')}"
        )
        range_parts.append(
            f"已处理 {meeting.get('baseline_count')} → {meeting.get('current_count')}"
        )
        range_note = '；'.join(range_parts)
    else:
        added_value = '—'
        if week_start:
            range_note = (
                f"发布周自 {week_start} 起；尚无周起点快照，净增暂不可算"
            )
        else:
            range_note = '尚无上一发布周，净增暂不可算'

    if meeting.get('previous_label'):
        leftover_note = (
            f"上一发布周未清 {meeting.get('leftover_previous', 0)} + "
            f"当前发布周未完成 {meeting.get('leftover_current', 0)}"
        )
    else:
        leftover_note = '当前发布周仍未处理的排期条目'

    promise_rate = ''
    if meeting.get('promised'):
        rate = round(100 * meeting['done_promised'] / meeting['promised'])
        promise_rate = f"已完成 {meeting['done_promised']}/{meeting['promised']}（{rate}%）"

    owner_rows = []
    detail_blocks = []
    for row in meeting.get('owners') or []:
        owner = row['owner']
        display = _escape_html(row['display'])
        rate = '—' if row.get('promise_rate') is None else f"{row['promise_rate']}%"
        owner_rows.append(
            f'<tr class="meeting-owner-row" data-owner="{owner}" '
            f'onclick="toggleMeetingOwner(\'{owner}\')">'
            f'<td><span class="owner-tag owner-{owner}">{display}</span></td>'
            f'<td>{row["promised"]}</td>'
            f'<td>{row["done_promised"]}</td>'
            f'<td class="num-added">+{row["added"]}</td>'
            f'<td>{row["leftover"]}</td>'
            f'<td>{rate}</td>'
            f'</tr>'
        )

        added_lines = []
        for item in row.get('added_items') or []:
            href = f'{base_url}/browse/{item["key"]}'
            added_lines.append(
                f'<li><a href="{href}" target="_blank">{item["key"]}</a> '
                f'No.{item["index"]} — {_escape_html(item["summary"])}</li>'
            )
        leftover_lines = []
        for item in row.get('leftover_items') or []:
            href = f'{base_url}/browse/{item["key"]}'
            empty_summary = '（无摘要）'
            summary = _escape_html(item["summary"]) or empty_summary
            leftover_lines.append(
                f'<li><a href="{href}" target="_blank">{item["key"]}</a> '
                f'No.{item["index"]} — {summary}</li>'
            )
        if not added_lines and not leftover_lines:
            continue
        added_list = ''.join(added_lines) or '<li class="muted">无</li>'
        leftover_list = ''.join(leftover_lines) or '<li class="muted">无</li>'
        detail_blocks.append(
            f'<div class="meeting-owner-detail" id="meeting-detail-{owner}" hidden>'
            f'<div class="meeting-detail-title">{display}</div>'
            f'<div class="meeting-detail-grid">'
            f'<div><div class="meeting-detail-label">区间净增</div>'
            f'<ul>{added_list}</ul></div>'
            f'<div><div class="meeting-detail-label">未完成排期</div>'
            f'<ul>{leftover_list}</ul></div>'
            f'</div></div>'
        )

    table_body = ''.join(owner_rows) or (
        '<tr><td colspan="6" class="muted">暂无按人数据</td></tr>'
    )
    range_note_html = _escape_html(range_note)
    promise_note = _escape_html(promise_rate) or '当前发布周排期条数'
    leftover_note_html = _escape_html(leftover_note)

    return f"""
        <div class="panel meeting-panel" id="meeting-report">
            <div class="owner-daily-chart-title">{release}</div>
            <div class="owner-daily-chart-subtitle">{range_note_html}</div>
            <div class="meeting-stats">
                <div class="meeting-stat">
                    <div class="meeting-stat-label">排期</div>
                    <div class="meeting-stat-value">{meeting['promised']}</div>
                    <div class="meeting-stat-note">{promise_note}</div>
                </div>
                <div class="meeting-stat meeting-stat-added">
                    <div class="meeting-stat-label">已处理净增</div>
                    <div class="meeting-stat-value">{added_value}</div>
                    <div class="meeting-stat-note">Daily 条目，含 Done / Backlog / Moved</div>
                </div>
                <div class="meeting-stat meeting-stat-leftover">
                    <div class="meeting-stat-label">未完成</div>
                    <div class="meeting-stat-value">{meeting['leftover']}</div>
                    <div class="meeting-stat-note">{leftover_note_html}</div>
                </div>
            </div>
            <table class="meeting-table">
                <thead>
                    <tr>
                        <th>负责人</th>
                        <th>排期</th>
                        <th>已完成</th>
                        <th>净增</th>
                        <th>未完成</th>
                        <th>完成率</th>
                    </tr>
                </thead>
                <tbody>{table_body}</tbody>
            </table>
            <div class="meeting-hint">点击某人展开净增 / 未完成明细</div>
            <div class="meeting-details">{''.join(detail_blocks)}</div>
        </div>
    """


def generate_owner_daily_html_report(
    analysis,
    base_url,
    parent_issue='KAT-11542',
    *,
    label='Q3',
    back_href='./',
    favicon_href='favicon.svg',
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
    <link rel="shortcut icon" href="{favicon_href}">
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


def generate_markdown_report(analysis, parent_issue='KAT-11542', *, label='Q3'):
    """
    生成 Markdown 格式的分析报告

    Args:
        analysis: analyze_issues() 返回的分析结果

    Returns:
        str: Markdown 文档字符串
    """
    now = _report_timestamp()
    md = f"""# Jira {label} 任务分析报告

**数据更新到**: {now}（UTC+8）{_UPDATE_RULE_SHORT}
**父任务**: {parent_issue}

## 统计概览

| 指标 | 数量 |
|------|------|
| **总条目数** | {analysis['total']} |
| **已处理** | {analysis['processed']}（{analysis.get('processed_jira', 0)} 个子任务） |
| **未处理** | {analysis['unprocessed']}（{analysis.get('unprocessed_jira', 0)} 个子任务） |
| **已排期** | {analysis.get('scheduled_unprocessed', 0)} |
| **排期已处理** | {analysis.get('scheduled_processed', 0)} |

---

"""

    # 提醒：所有条目已完成但 Jira 状态仍是活跃的子任务
    stale_tasks = _find_all_done_active_tasks(analysis)
    if stale_tasks:
        md += "## ⚠️ 请更新 Jira 状态\n\n"
        md += "以下子任务的所有条目都已处理，但 Jira 状态仍为活跃，请及时更新：\n\n"
        for t in stale_tasks:
            md += f"- **{t['key']}** {t['summary']} — 状态: {t['status']}，{t['total']} 条已完成\n"
        md += "\n---\n\n"

    md += """## 未处理项目

"""

    if analysis['grouped']:
        for task_key in sorted(analysis['grouped'].keys(), reverse=True):
            task = analysis['grouped'][task_key]
            unprocessed_items = [
                item for item in task['items']
                if _counts_as_unprocessed(item, analysis)
            ]
            if not unprocessed_items:
                continue
            md += f"### [{task_key}] {task['summary']}\n\n"
            for item in unprocessed_items:
                md += _markdown_item_line(item)
            md += "\n"

        md += "## 排期已处理\n\n"
        has_scheduled_processed = False
        for task_key in sorted(analysis['grouped'].keys(), reverse=True):
            task = analysis['grouped'][task_key]
            done_scheduled = [
                i for i in task['items']
                if i.get('is_processed') and i.get('is_scheduled')
            ]
            if not done_scheduled:
                continue
            has_scheduled_processed = True
            md += f"### [{task_key}] {task['summary']}\n\n"
            for item in done_scheduled:
                md += _markdown_item_line(item, include_status=True)
            md += "\n"
        if not has_scheduled_processed:
            md += "（无）\n\n"
    else:
        md += "🎉 太棒了！没有未处理的项目。\n"

    md += """---

*Generated by Jira Analyzer*"""

    return md
