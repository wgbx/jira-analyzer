"""
报告生成模块

将分析结果渲染为 HTML 或 Markdown 格式的可视化报告。
"""

from datetime import datetime
from zoneinfo import ZoneInfo

_REPORT_TZ = ZoneInfo('Asia/Shanghai')


def _report_timestamp():
    """报告展示的拉取时间（东八区）。"""
    return datetime.now(_REPORT_TZ).strftime('%Y-%m-%d %H:%M:%S')

from analyzer.config import OUTPUT_DIR
from analyzer.jira_client import DEFAULT_ACTIVE_STATUSES, is_active_issue_status
from analyzer.owners import OWNERS, OWNER_DISPLAY_NAMES


def _active_statuses_for_analysis(analysis):
    return tuple(analysis.get('active_statuses') or DEFAULT_ACTIVE_STATUSES)


def _counts_as_unprocessed(item, analysis):
    """描述未处理，且子任务 Jira 状态在活跃集合内。"""
    if item.get('is_processed'):
        return False
    return is_active_issue_status(item.get('issue_status', ''), analysis)


# ============================================================
# Owner 相关的样式和筛选配置（集中管理，便于维护）
# ============================================================

# Owner 标签颜色：背景色 + 文字色
OWNER_COLORS = {
    'jayce': ('#dbeafe', '#1e40af'),
    'zhiyong': ('#dcfce7', '#166534'),
    'tiancheng': ('#f3e8ff', '#6b21a8'),
    'jun': ('#fef3c7', '#92400e'),
    'jiaqi': ('#fee2e2', '#991b1b'),
    'lory': ('#e0f2fe', '#0c4a6e'),
    'tianye': ('#fce7f3', '#9d174d'),
    'fengxia': ('#fef9c3', '#854d0e'),
    'fred': ('#e2e8f0', '#334155'),
    'jiangtian': ('#d1fae5', '#065f46'),
    'chenglim': ('#ede9fe', '#5b21b6'),
    'zhengzhu': ('#ffedd5', '#9a3412'),
    'cici': ('#fdf2f8', '#9d174d'),
}

_DEFAULT_OWNER_COLOR = ('#f3f4f6', '#374151')


def _owner_color(owner):
    return OWNER_COLORS.get(owner, _DEFAULT_OWNER_COLOR)


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


def _build_filter_js(visible_owners, show_unassigned):
    """生成筛选功能的 JavaScript 代码（人员 + 排期状态）"""
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
    visible_owners = _visible_filter_owners(analysis)
    show_unassigned = owner_counts.get('unassigned', 0) > 0
    owner_css = _build_owner_css(_owners_needing_css(analysis, visible_owners))
    filter_buttons = _build_filter_buttons(visible_owners, show_unassigned, owner_counts)
    filter_js = _build_filter_js(visible_owners, show_unassigned)
    title = f'Jira {label} 任务分析报告'
    nav_html = _build_report_nav(nav_links, label)

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
            {nav_html}
            <h1>{title}</h1>
            <p class="header-subtitle">{parent_issue} 所有项目概览</p>
            <p class="header-updated">数据更新到 {now}（UTC+8）</p>
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

**数据更新到**: {now}（UTC+8）
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
