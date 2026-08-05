"""Owner registry and detect_owner tests."""

import unittest

from analyzer.owners import (
    OWNER_DISPLAY_NAMES,
    OWNER_REGISTRY,
    OWNERS,
    detect_owner,
)


class OwnerRegistryTests(unittest.TestCase):
    def test_registry_keys_align_with_exports(self):
        self.assertEqual(set(OWNERS), set(OWNER_REGISTRY))
        self.assertEqual(set(OWNER_DISPLAY_NAMES), set(OWNER_REGISTRY))

    def test_entries_have_required_fields(self):
        for key, entry in OWNER_REGISTRY.items():
            self.assertTrue(entry.get('mentions'), msg=key)
            self.assertTrue(entry.get('display'), msg=key)

    def test_detect_owner_by_mention_text(self):
        self.assertIn('zhiyong', detect_owner('please ask @zhiyong song'))
        self.assertEqual(detect_owner('nobody here'), [])

    def test_detect_owner_case_insensitive(self):
        mention = OWNER_REGISTRY['jayce']['mentions'][0]
        self.assertIn('jayce', detect_owner(mention.upper()))


if __name__ == '__main__':
    unittest.main()
