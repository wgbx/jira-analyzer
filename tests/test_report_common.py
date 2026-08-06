"""Tests for report common helpers."""

import unittest

from analyzer.report.common import _count_unprocessed_by_team


def _analysis(items_by_task):
    """Build minimal analysis: {task_key: [item, ...]}."""
    return {
        'grouped': {
            key: {'summary': key, 'items': items}
            for key, items in items_by_task.items()
        },
    }


def _item(*, owners=None, is_processed=False, issue_status='待办'):
    return {
        'owners': owners or [],
        'is_processed': is_processed,
        'issue_status': issue_status,
    }


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


if __name__ == '__main__':
    unittest.main()
