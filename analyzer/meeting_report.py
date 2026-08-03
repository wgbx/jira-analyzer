"""
发布周进度指标

维度固定为「当前发布周」（scheduled.json 最新一周）：
- 排期 / 未完成：该周（+ 上一周仍未清）排期条目
- 净增：上一发布日 → 当前 的已处理快照差集
"""

from __future__ import annotations

from analyzer.owners import OWNER_DISPLAY_NAMES, OWNERS
from analyzer.scheduled import load_scheduled
from analyzer.snapshots import (
    build_processed_snapshot,
    diff_processed_snapshots,
    find_week_baseline_snapshot,
)


def _short_text(text: str, limit: int = 48) -> str:
    cleaned = ' '.join((text or '').split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1] + '…'


def _release_sort_key(release):
    return release.get('date') or ''


def get_current_and_previous_releases(scheduled=None):
    data = scheduled if scheduled is not None else load_scheduled()
    releases = sorted(data.get('releases') or [], key=_release_sort_key)
    if not releases:
        return None, None
    current = releases[-1]
    previous = releases[-2] if len(releases) >= 2 else None
    return current, previous


def _item_lookup(analysis):
    lookup = {}
    for task_key, task in analysis.get('grouped', {}).items():
        for item in task.get('items', []):
            lookup[(task_key, int(item['index']))] = item
    return lookup


def _scheduled_rows(release, project_key, item_lookup):
    rows = []
    for entry in release.get('items') or []:
        issue_num = str(entry['issue'])
        task_key = f'{project_key}-{issue_num}'
        index = int(entry['index'])
        owner = entry.get('owner') or 'unassigned'
        live = item_lookup.get((task_key, index))
        processed = bool(live and live.get('is_processed'))
        text = (live or {}).get('text', '')
        rows.append({
            'issue': issue_num,
            'key': task_key,
            'index': index,
            'owner': owner,
            'processed': processed,
            'text': text,
            'summary': _short_text(text),
        })
    return rows


def build_meeting_report(
    analysis,
    *,
    label='Q3',
    parent_issue='KAT-11542',
    report_id='q3',
    scheduled=None,
    current_snapshot=None,
    baseline_snapshot=None,
):
    """
    组装当前发布周进度。

    - 排期：当前发布周排期条数
    - 未完成：当前周未处理 + 上一发布周仍未处理
    - 净增：相对「上一发布日」周起点快照的已处理差集（全库 Daily）
    """
    scheduled = scheduled if scheduled is not None else load_scheduled()
    project_key = scheduled.get('project_key', 'KAT')
    current_release, previous_release = get_current_and_previous_releases(scheduled)
    item_lookup = _item_lookup(analysis)

    week_start = (previous_release or {}).get('date')
    week_end = (current_release or {}).get('date')

    if current_snapshot is None:
        current_snapshot = build_processed_snapshot(
            analysis, label=label, parent_issue=parent_issue,
        )
    if baseline_snapshot is None:
        baseline_snapshot = find_week_baseline_snapshot(
            report_id,
            week_start=week_start,
            week_end=week_end or current_snapshot.get('date'),
        )

    diff = diff_processed_snapshots(baseline_snapshot, current_snapshot)

    current_rows = (
        _scheduled_rows(current_release, project_key, item_lookup)
        if current_release else []
    )
    previous_rows = (
        _scheduled_rows(previous_release, project_key, item_lookup)
        if previous_release else []
    )
    previous_open = [row for row in previous_rows if not row['processed']]
    current_open = [row for row in current_rows if not row['processed']]
    leftover_rows = previous_open + current_open

    promised = len(current_rows)
    leftover = len(leftover_rows)
    done_in_promise = sum(1 for row in current_rows if row['processed'])

    owner_stats = {}

    def ensure_owner(owner):
        if owner not in owner_stats:
            owner_stats[owner] = {
                'owner': owner,
                'promised': 0,
                'done_promised': 0,
                'leftover': 0,
                'added': 0,
                'added_items': [],
                'leftover_items': [],
            }
        return owner_stats[owner]

    for row in current_rows:
        stats = ensure_owner(row['owner'])
        stats['promised'] += 1
        if row['processed']:
            stats['done_promised'] += 1

    for row in leftover_rows:
        stats = ensure_owner(row['owner'])
        stats['leftover'] += 1
        stats['leftover_items'].append(row)

    for owner, items in diff['by_owner'].items():
        stats = ensure_owner(owner)
        stats['added'] = len(items)
        stats['added_items'] = [
            {
                'ref': item['ref'],
                'key': item['key'],
                'index': item['index'],
                'text': item.get('text', ''),
                'summary': _short_text(item.get('text', '')),
            }
            for item in items
        ]

    ordered_owners = []
    seen = set()
    for owner in list(OWNERS) + ['unassigned']:
        if owner in owner_stats:
            ordered_owners.append(owner_stats[owner])
            seen.add(owner)
    for owner, stats in owner_stats.items():
        if owner not in seen:
            ordered_owners.append(stats)

    ordered_owners.sort(
        key=lambda row: (row['added'], row['promised'], row['leftover']),
        reverse=True,
    )

    for row in ordered_owners:
        row['display'] = (
            '未分配' if row['owner'] == 'unassigned'
            else OWNER_DISPLAY_NAMES.get(row['owner'], row['owner'])
        )
        if row['promised']:
            row['promise_rate'] = round(100 * row['done_promised'] / row['promised'])
        else:
            row['promise_rate'] = None

    has_diff = baseline_snapshot is not None
    return {
        'label': label,
        'parent_issue': parent_issue,
        'release_label': (current_release or {}).get('label') or '当前发布周',
        'release_date': week_end,
        'previous_label': (previous_release or {}).get('label'),
        'previous_date': week_start,
        'week_start': week_start,
        'week_end': week_end,
        'promised': promised,
        'done_promised': done_in_promise,
        'leftover': leftover,
        'leftover_previous': len(previous_open),
        'leftover_current': len(current_open),
        'unique_added': diff['unique_added'] if has_diff else None,
        'baseline_count': diff['baseline_count'] if has_diff else None,
        'current_count': diff['current_count'],
        'baseline_date': diff.get('baseline_date'),
        'current_date': diff.get('current_date'),
        'has_diff': has_diff,
        'owners': ordered_owners,
        'leftover_items': leftover_rows,
    }
