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

    def test_paren_contains_reproduce(self):
        _, backlog, label, _ = detect_processed_flags('(Unable to reproduce) flake')
        self.assertTrue(backlog)
        self.assertEqual(label, 'Cannot reproduce')

        _, backlog, label, _ = detect_processed_flags('（cannot reproduce）fullwidth')
        self.assertTrue(backlog)
        self.assertEqual(label, 'Cannot reproduce')

    def test_paren_contains_duplication(self):
        _, backlog, label, _ = detect_processed_flags('(Duplication of KAT-1) same bug')
        self.assertTrue(backlog)
        self.assertEqual(label, 'Duplication')

        _, backlog, label, _ = detect_processed_flags('（duplication）fullwidth')
        self.assertTrue(backlog)
        self.assertEqual(label, 'Duplication')

    def test_reproduce_outside_parens_not_processed(self):
        done, backlog, label, moved = detect_processed_flags('try to reproduce @Jayce')
        self.assertFalse(done)
        self.assertFalse(backlog)
        self.assertIsNone(label)
        self.assertFalse(moved)


if __name__ == '__main__':
    unittest.main()
