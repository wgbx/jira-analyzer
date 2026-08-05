"""Status prefix detection tests."""

import unittest

from analyzer.statuses import detect_processed_flags


class StatusFlagTests(unittest.TestCase):
    def test_done(self):
        done, backlog, label, moved = detect_processed_flags('(Done) fix login')
        self.assertTrue(done)
        self.assertFalse(backlog)
        self.assertIsNone(label)
        self.assertFalse(moved)

    def test_backlog_and_invalid(self):
        _, backlog, label, _ = detect_processed_flags('(Backlog) later')
        self.assertTrue(backlog)
        self.assertEqual(label, 'Backlog')

        _, backlog, label, _ = detect_processed_flags('(Invalid) wont fix')
        self.assertTrue(backlog)
        self.assertEqual(label, 'Invalid')

    def test_moved(self):
        _, _, _, moved = detect_processed_flags('(Moved to KAT-1) note')
        self.assertTrue(moved)

    def test_plain_text_unprocessed(self):
        done, backlog, label, moved = detect_processed_flags('plain item @Jayce')
        self.assertFalse(done)
        self.assertFalse(backlog)
        self.assertIsNone(label)
        self.assertFalse(moved)

    def test_fullwidth_parens(self):
        done, _, _, _ = detect_processed_flags('（Done）fullwidth')
        self.assertTrue(done)


if __name__ == '__main__':
    unittest.main()
