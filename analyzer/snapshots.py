"""
已处理条目快照

每次生成报告时落一份当日快照，供「会汇报」做区间净增对比。
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from pathlib import Path

from analyzer.config import OUTPUT_DIR

SNAPSHOTS_DIR = OUTPUT_DIR / 'snapshots'
_DAILY_TASK_RE = re.compile(r'\bDaily\b', re.IGNORECASE)


def _is_daily_task(summary):
    return bool(_DAILY_TASK_RE.search(summary or ''))


def item_ref(task_key: str, index: int) -> str:
    return f'{task_key}:{int(index)}'


def snapshot_dir_for(report_id: str = 'q3') -> Path:
    path = SNAPSHOTS_DIR / report_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def build_processed_snapshot(analysis, *, label='Q3', parent_issue='KAT-11542'):
    """从分析结果提取 Daily 已处理条目集合。"""
    items = []
    for task_key, task in analysis.get('grouped', {}).items():
        if not _is_daily_task(task.get('summary', '')):
            continue
        for item in task.get('items', []):
            if not item.get('is_processed'):
                continue
            items.append({
                'ref': item_ref(task_key, item['index']),
                'key': task_key,
                'index': int(item['index']),
                'owners': list(item.get('owners') or []),
                'text': item.get('text', ''),
                'is_done': bool(item.get('is_done')),
                'is_backlog': bool(item.get('is_backlog')),
                'backlog_label': item.get('backlog_label'),
                'is_moved': bool(item.get('is_moved')),
            })

    items.sort(key=lambda row: (row['key'], row['index']), reverse=True)
    now = datetime.now(timezone.utc)
    return {
        'date': now.astimezone().date().isoformat(),
        'updated': now.strftime('%Y-%m-%dT%H:%M:%SZ'),
        'label': label,
        'parent_issue': parent_issue,
        'processed_count': len(items),
        'items': items,
    }


def save_processed_snapshot(snapshot, report_id: str = 'q3') -> Path:
    """写入当日快照（同日重复运行覆盖）。"""
    day = snapshot.get('date') or date.today().isoformat()
    path = snapshot_dir_for(report_id) / f'{day}.json'
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)
    return path


def load_snapshot(path: Path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def list_snapshots(report_id: str = 'q3') -> list[Path]:
    directory = snapshot_dir_for(report_id)
    return sorted(directory.glob('????-??-??.json'))


def find_snapshot_on_or_before(report_id: str = 'q3', *, on_or_before: str):
    """取 date <= on_or_before 的最近一份快照。"""
    candidates = [p for p in list_snapshots(report_id) if p.stem <= on_or_before]
    if not candidates:
        return None
    return load_snapshot(candidates[-1])


def find_earliest_snapshot_before(report_id: str = 'q3', *, before_date: str):
    """取 date < before_date 的最早一份快照。"""
    candidates = [p for p in list_snapshots(report_id) if p.stem < before_date]
    if not candidates:
        return None
    return load_snapshot(candidates[0])


def find_week_baseline_snapshot(
    report_id: str = 'q3',
    *,
    week_start: str | None,
    week_end: str | None,
):
    """
    发布周净增基线：
    1. 优先上一发布日 week_start 当日或之前最近快照
    2. 否则取当前发布日之前最早的一份（周初附近）
    """
    if week_start:
        snap = find_snapshot_on_or_before(report_id, on_or_before=week_start)
        if snap:
            return snap
    if week_end:
        return find_earliest_snapshot_before(report_id, before_date=week_end)
    return None


def snapshot_item_map(snapshot) -> dict[str, dict]:
    return {item['ref']: item for item in snapshot.get('items', []) if item.get('ref')}


def diff_processed_snapshots(baseline, current):
    """
    计算净增条目（当前有、基线无）。

    Returns:
        dict: unique_added, by_owner (owner -> [items]), baseline_count, current_count
    """
    before = snapshot_item_map(baseline or {'items': []})
    after = snapshot_item_map(current or {'items': []})
    added_refs = sorted(set(after) - set(before), reverse=True)
    added_items = [after[ref] for ref in added_refs]

    by_owner: dict[str, list] = {}
    for item in added_items:
        owners = item.get('owners') or []
        keys = owners if owners else ['unassigned']
        for owner in keys:
            by_owner.setdefault(owner, []).append(item)

    return {
        'baseline_date': (baseline or {}).get('date'),
        'current_date': (current or {}).get('date'),
        'baseline_count': len(before),
        'current_count': len(after),
        'unique_added': len(added_items),
        'added_items': added_items,
        'by_owner': by_owner,
    }
