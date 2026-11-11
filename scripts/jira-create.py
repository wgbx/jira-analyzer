#!/usr/bin/env python3
"""Create a standalone Jira issue (no parent) from a plain-text body file.

Body format (blank line separates blocks):
  - lines starting with "- "      -> bullet list
  - lines starting with "1) " ... -> ordered list
  - other consecutive lines       -> one paragraph (hard breaks between lines)
  - "@Display Name" listed via --mention becomes a real Jira mention

Default is dry-run; pass --create to POST. See skills/create-jira.md.
"""
import argparse
import re
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from analyzer.config import load_config
from analyzer.jira_http import build_jira_session, jira_request

LIST_ITEM = {'bullet': re.compile(r'^- (.*)$'), 'ordered': re.compile(r'^\d+\) (.*)$')}


def inline_nodes(text, mentions):
    """Split text into text/mention ADF nodes for the given {name: accountId}."""
    if not mentions:
        return [{'type': 'text', 'text': text}] if text else []
    pattern = re.compile('(' + '|'.join(re.escape('@' + n) for n in mentions) + ')')
    nodes = []
    for part in pattern.split(text):
        if not part:
            continue
        name = part[1:]
        if part.startswith('@') and name in mentions:
            nodes.append({'type': 'mention', 'attrs': {
                'id': mentions[name], 'text': part, 'accessLevel': '', 'localId': str(uuid.uuid4())}})
        else:
            nodes.append({'type': 'text', 'text': part})
    return nodes


def to_adf(body, mentions):
    blocks, lines = [], body.strip('\n').split('\n')
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        kind = next((k for k, rx in LIST_ITEM.items() if rx.match(line)), None)
        group = []
        while i < len(lines) and lines[i].strip():
            cur = next((k for k, rx in LIST_ITEM.items() if rx.match(lines[i])), None)
            if cur != kind:
                break
            group.append(LIST_ITEM[kind].match(lines[i]).group(1) if kind else lines[i])
            i += 1
        if kind:
            blocks.append({'type': 'bulletList' if kind == 'bullet' else 'orderedList',
                           'content': [{'type': 'listItem', 'content': [
                               {'type': 'paragraph', 'content': inline_nodes(t, mentions)}]} for t in group]})
        else:
            content = []
            for n, t in enumerate(group):
                if n:
                    content.append({'type': 'hardBreak'})
                content.extend(inline_nodes(t, mentions))
            blocks.append({'type': 'paragraph', 'content': content})
    return {'type': 'doc', 'version': 1, 'content': blocks}


def resolve_user(session, base, name):
    response = jira_request(session, 'GET', f'{base}/rest/api/3/user/search', params={'query': name})
    response.raise_for_status()
    users = [u for u in response.json()
             if u.get('displayName', '').casefold() == name.casefold() and u.get('active', True)]
    if len(users) != 1:
        raise RuntimeError(f'{name}: expected one active Jira user, found {len(users)}')
    return users[0]['accountId']


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--project', required=True, help='Project key, e.g. KAT')
    parser.add_argument('--summary', required=True)
    parser.add_argument('--body-file', required=True, type=Path)
    parser.add_argument('--issue-type', default='Task')
    parser.add_argument('--mention', action='append', default=[], help='Display name to turn into a mention')
    parser.add_argument('--create', action='store_true', help='Actually POST (default: dry-run)')
    args = parser.parse_args()

    cfg = load_config()
    session = build_jira_session(cfg)
    base = cfg['jira']['base_url'].rstrip('/')
    mentions = {name: resolve_user(session, base, name) for name in args.mention}
    payload = {'fields': {
        'project': {'key': args.project},
        'issuetype': {'name': args.issue_type},
        'summary': args.summary,
        'description': to_adf(args.body_file.read_text(encoding='utf-8'), mentions),
    }}
    print(f'Project: {args.project}  Type: {args.issue_type}  Parent: none')
    print(f'Summary: {args.summary}')
    print(f'Mentions resolved: {list(mentions)}')
    print(f'Description blocks: {[b["type"] for b in payload["fields"]["description"]["content"]]}')
    if not args.create:
        print('[dry-run] no POST; pass --create to create the issue')
        return
    # Retry adapter also retries POST on 5xx; check before re-running if a response was lost.
    response = jira_request(session, 'POST', f'{base}/rest/api/3/issue', json=payload)
    if not response.ok:
        raise RuntimeError(f'Create failed: {response.status_code} {response.text[:500]}')
    key = response.json()['key']
    print(f'Created {key}: {base}/browse/{key}')


if __name__ == '__main__':
    main()
