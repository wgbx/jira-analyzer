"""ADF list parsing tests."""

import unittest

from analyzer.parser import parse_list_items


def _text_item(text, *, strike=False):
    node = {'type': 'text', 'text': text}
    if strike:
        node['marks'] = [{'type': 'strike'}]
    return {
        'type': 'listItem',
        'content': [{'type': 'paragraph', 'content': [node]}],
    }


def _mention_item(mention_text, prefix='task '):
    return {
        'type': 'listItem',
        'content': [{
            'type': 'paragraph',
            'content': [
                {'type': 'text', 'text': prefix},
                {
                    'type': 'mention',
                    'attrs': {'text': mention_text, 'id': '1'},
                },
            ],
        }],
    }


class ParserTests(unittest.TestCase):
    def test_ordered_list_uses_order_attr(self):
        adf = {
            'type': 'orderedList',
            'attrs': {'order': 5},
            'content': [
                _text_item('(Done) first'),
                _text_item('second open'),
            ],
        }
        items, next_index = parse_list_items(adf)
        self.assertEqual([i['index'] for i in items], [5, 6])
        self.assertTrue(items[0]['is_done'])
        self.assertTrue(items[0]['is_processed'])
        self.assertFalse(items[1]['is_processed'])
        self.assertEqual(next_index, 7)

    def test_strikethrough_marks_processed(self):
        adf = {
            'type': 'orderedList',
            'attrs': {'order': 1},
            'content': [_text_item('obsolete', strike=True)],
        }
        items, _ = parse_list_items(adf)
        self.assertTrue(items[0]['is_strikethrough'])
        self.assertTrue(items[0]['is_processed'])

    def test_mention_detects_owner(self):
        adf = {
            'type': 'orderedList',
            'attrs': {'order': 1},
            'content': [_mention_item('@Jayce')],
        }
        items, _ = parse_list_items(adf)
        self.assertIn('jayce', items[0]['owners'])

    def test_nested_ordered_list_not_merged_into_parent_text(self):
        adf = {
            'type': 'orderedList',
            'attrs': {'order': 1},
            'content': [{
                'type': 'listItem',
                'content': [
                    {
                        'type': 'paragraph',
                        'content': [{'type': 'text', 'text': 'parent only'}],
                    },
                    {
                        'type': 'orderedList',
                        'attrs': {'order': 1},
                        'content': [_text_item('nested child')],
                    },
                ],
            }],
        }
        items, _ = parse_list_items(adf)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['text'], 'parent only')
        self.assertNotIn('nested child', items[0]['text'])


if __name__ == '__main__':
    unittest.main()
