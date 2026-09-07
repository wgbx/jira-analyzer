"""Tests for report common helpers."""

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from analyzer.report.common import (
    _count_unprocessed_by_team,
    _find_all_done_active_tasks,
)


def _analysis(items_by_task, *, task_meta=None):
    """Build minimal analysis: {task_key: [item, ...]}."""
    task_meta = task_meta or {}
    grouped = {}
    for key, items in items_by_task.items():
        meta = task_meta.get(key, {})
        grouped[key] = {
            'summary': meta.get('summary', key),
            'issue_status': meta.get('issue_status', '待办'),
            'created': meta.get('created'),
            'items': items,
        }
    return {'grouped': grouped, 'active_statuses': ['待办', '正在进行']}


def _item(*, owners=None, is_processed=False, issue_status='待办'):
    return {
        'owners': owners or [],
        'is_processed': is_processed,
        'issue_status': issue_status,
    }


def _iso_days_ago(days, *, hours=0):
    """Jira-style created timestamp N days ago (UTC)."""
    dt = datetime.now(timezone.utc) - timedelta(days=days, hours=hours)
    return dt.strftime('%Y-%m-%dT%H:%M:%S.000+0000')


class CountUnprocessedByTeamTests(unittest.TestCase):
    def test_counts_by_first_owner_team(self):
        analysis = _analysis({
            'T1': [
                _item(owners=['jayce']),           # wuhan
                _item(owners=['lory']),            # chengdu
                _item(owners=['fred']),            # us
            ],
        })
        self.assertEqual(
            _count_unprocessed_by_team(analysis),
            {'wuhan': 1, 'chengdu': 1, 'us': 1},
        )

    def test_cross_team_uses_first_owner(self):
        analysis = _analysis({
            'T1': [
                _item(owners=['lory', 'jayce']),  # chengdu first
            ],
        })
        self.assertEqual(
            _count_unprocessed_by_team(analysis),
            {'wuhan': 0, 'chengdu': 1, 'us': 0},
        )

    def test_skips_unassigned_and_inactive(self):
        analysis = _analysis({
            'T1': [
                _item(owners=[]),
                _item(owners=['jayce'], is_processed=True),
                _item(owners=['fred'], issue_status='Done'),
                _item(owners=['neo']),
            ],
        })
        self.assertEqual(
            _count_unprocessed_by_team(analysis),
            {'wuhan': 1, 'chengdu': 0, 'us': 0},
        )


class FindAllDoneActiveTasksTests(unittest.TestCase):
    def _done_active(self, *, created):
        return _analysis(
            {'T1': [_item(owners=['jayce'], is_processed=True)]},
            task_meta={'T1': {'issue_status': '待办', 'created': created}},
        )

    def test_includes_when_created_older_than_3_days(self):
        # 3 days + 1 hour ago → age > 3 days
        analysis = self._done_active(created=_iso_days_ago(3, hours=1))
        keys = [t['key'] for t in _find_all_done_active_tasks(analysis)]
        self.assertEqual(keys, ['T1'])

    def test_excludes_when_created_exactly_3_days(self):
        fixed_now = datetime(2026, 9, 7, 12, 0, 0, tzinfo=timezone.utc)
        created = '2026-09-04T12:00:00.000+0000'
        analysis = self._done_active(created=created)
        with patch('analyzer.report.common._utcnow', return_value=fixed_now):
            keys = [t['key'] for t in _find_all_done_active_tasks(analysis)]
        self.assertEqual(keys, [])

    def test_excludes_when_created_within_3_days(self):
        analysis = self._done_active(created=_iso_days_ago(2))
        keys = [t['key'] for t in _find_all_done_active_tasks(analysis)]
        self.assertEqual(keys, [])

    def test_excludes_when_created_missing(self):
        analysis = self._done_active(created=None)
        keys = [t['key'] for t in _find_all_done_active_tasks(analysis)]
        self.assertEqual(keys, [])


if __name__ == '__main__':
    unittest.main()
