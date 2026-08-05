"""Scheduled lookup tests."""

import json
import tempfile
import unittest
from pathlib import Path

from analyzer.scheduled import build_scheduled_lookup, load_scheduled


class ScheduledTests(unittest.TestCase):
    def test_missing_file_returns_empty(self):
        data = load_scheduled('/tmp/jira-analyzer-no-such-scheduled.json')
        self.assertEqual(data['releases'], [])
        self.assertEqual(build_scheduled_lookup(data), {})

    def test_lookup_keys_and_later_release_wins(self):
        payload = {
            'project_key': 'KAT',
            'releases': [
                {
                    'date': '2026-07-01',
                    'label': 'early',
                    'items': [{'issue': '100', 'index': 1}],
                },
                {
                    'date': '2026-08-01',
                    'label': 'late',
                    'items': [{'issue': '100', 'index': 1}],
                },
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'scheduled.json'
            path.write_text(json.dumps(payload), encoding='utf-8')
            data = load_scheduled(path)
            lookup = build_scheduled_lookup(data)
        self.assertEqual(lookup[('KAT-100', 1)], 'late')

    def test_real_scheduled_json_loads(self):
        data = load_scheduled()
        self.assertTrue(data.get('releases'))
        lookup = build_scheduled_lookup(data)
        self.assertTrue(lookup)


if __name__ == '__main__':
    unittest.main()
