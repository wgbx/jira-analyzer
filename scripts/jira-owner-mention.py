#!/usr/bin/env python3
"""Replace a list item's registered owner mention, preserving other content."""
import argparse
import copy
import runpy
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from analyzer.config import load_config
from analyzer.jira_http import build_jira_session, jira_request
from analyzer.owners import OWNERS
from analyzer.parser import parse_list_items

helpers = runpy.run_path(str(ROOT / 'scripts/jira-item-status.py'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('item', type=helpers['parse_item_spec'])
    parser.add_argument('--owner', required=True, choices=OWNERS)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    key, index = args.item
    cfg = load_config()
    session = build_jira_session(cfg)
    base = cfg['jira']['base_url'].rstrip('/')
    url = f'{base}/rest/api/3/issue/{key}'

    def fetch():
        response = jira_request(session, 'GET', url, params={'fields': 'description'})
        response.raise_for_status()
        return response.json()['fields']['description']

    original = fetch()
    desc = copy.deepcopy(original)
    items, _ = parse_list_items(desc)
    matches = [item for item in items if item['index'] == index]
    if len(matches) != 1:
        raise RuntimeError(f'Expected one item #{index}, found {len(matches)}')
    li, _ = helpers['find_list_item_by_index'](desc, index)
    para = next((n for n in li.get('content', []) if n.get('type') == 'paragraph'
                 and any(c.get('type') == 'mention' or c.get('text', '').strip()
                         for c in n.get('content', []))), None)
    if para is None:
        raise RuntimeError('No paragraph with text/mention')
    mention_text = OWNERS[args.owner][0]
    response = jira_request(session, 'GET', f'{base}/rest/api/3/user/search',
                            params={'query': mention_text.lstrip('@')})
    response.raise_for_status()
    users = [u for u in response.json() if u.get('displayName', '').casefold()
             == mention_text.lstrip('@').casefold() and u.get('active', True)]
    if len(users) != 1:
        raise RuntimeError(f'Expected one matching active Jira user, found {len(users)}')
    account_id = users[0]['accountId']
    known = {name.casefold() for names in OWNERS.values() for name in names}
    content = para.get('content', [])
    team_mentions = [n for n in content if n.get('type') == 'mention'
                     and n.get('attrs', {}).get('text', '').casefold() in known]
    if len(team_mentions) == 1 and team_mentions[0].get('attrs', {}).get('id') == account_id:
        print(f'{key} #{index}: already {mention_text}; no change')
        return
    content = [n for n in content if n not in team_mentions]
    if not any(n.get('type') == 'mention' and
               (n.get('attrs', {}).get('id') == account_id or
                n.get('attrs', {}).get('text', '').casefold() == mention_text.casefold())
               for n in content):
        end = next((i for i, n in enumerate(content) if n.get('type') == 'hardBreak'), len(content))
        while end and content[end - 1].get('type') == 'text' and not content[end - 1].get('text', '').strip():
            end -= 1
        content[end:end] = [{'type': 'text', 'text': ' '}, {'type': 'mention', 'attrs': {
            'id': account_id, 'text': mention_text, 'accessLevel': '', 'localId': str(uuid.uuid4())}}]
    para['content'] = content
    print(f'{key} #{index}: {matches[0]["text"][:200]}')
    print(f'Owner: {[n["attrs"].get("text") for n in team_mentions]} -> {mention_text}')
    if args.dry_run:
        print('[dry-run] no write')
        return
    if fetch() != original:
        raise RuntimeError('Description changed; aborting before PUT')
    response = jira_request(session, 'PUT', url, json={'fields': {'description': desc}})
    response.raise_for_status()
    if response.status_code not in (200, 204):
        raise RuntimeError(f'Unexpected PUT status {response.status_code}')
    if fetch() != desc:
        raise RuntimeError('Post-write description differs from expected; inspect Jira')
    print(f'PUT {response.status_code}; verified full description')


if __name__ == '__main__':
    main()
