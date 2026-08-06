"""Shared helpers for HTML/Markdown report rendering."""

import re
from datetime import datetime
from zoneinfo import ZoneInfo

from analyzer.jira_client import DEFAULT_ACTIVE_STATUSES, is_active_issue_status
from analyzer.owners import OWNERS, OWNER_DISPLAY_NAMES, OWNER_REGISTRY

_REPORT_TZ = ZoneInfo('Asia/Shanghai')

# 与外部 cron（北京时间 9–20 点整点）一致；推送 main / 手动触发也会更新
_UPDATE_RULE_SHORT = '9:00–20:00 每小时自动更新'

_DEFAULT_OWNER_COLOR = ('#f3f4f6', '#374151')
_DAILY_TASK_RE = re.compile(r'\bDaily\b', re.IGNORECASE)


def _report_timestamp():
    """报告展示的拉取时间（东八区）。"""
    return datetime.now(_REPORT_TZ).strftime('%Y-%m-%d %H:%M:%S')


def _counts_as_unprocessed(item, analysis):
    """描述未处理，且子任务 Jira 状态在活跃集合内。"""
    if item.get('is_processed'):
        return False
    return is_active_issue_status(item.get('issue_status', ''), analysis)


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


def _count_unprocessed_by_team(analysis):
    """
    按地区团队统计未处理条目数。

    每条只计 1 次；取第一个在 OWNER_REGISTRY 内的 owner 的 team。
    无已知 owner 的条目不计。
    """
    counts = {'wuhan': 0, 'chengdu': 0, 'us': 0}
    for task in analysis.get('grouped', {}).values():
        for item in task.get('items', []):
            if not _counts_as_unprocessed(item, analysis):
                continue
            for owner in item.get('owners') or []:
                team = (OWNER_REGISTRY.get(owner) or {}).get('team')
                if team in counts:
                    counts[team] += 1
                    break
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
