#!/usr/bin/env python3
"""
Jira 列表条目迁移 CLI。

实现 skills/jira-item-migrate.md 中的迁移与标记流程。

用法示例：

  # 完整迁移（含附件）到 KAT-11496
  python3 scripts/jira-item-migrate.py migrate --target KAT-11496 \\
      KAT-11267:3 KAT-11267:5 KAT-11109:2

  # 仅更新源 issue 的 (moved …) 标记（内容已在目标 issue 中）
  python3 scripts/jira-item-migrate.py mark --target KAT-11496 --at 7 KAT-11349:2 KAT-11349:5

  # 预览，不写入 Jira
  python3 scripts/jira-item-migrate.py migrate --target KAT-11496 KAT-11267:3 --dry-run
"""

from __future__ import annotations

import argparse
import copy
import mimetypes
import re
import sys
import time
import uuid
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from analyzer.config import load_config
from analyzer.jira_http import build_jira_session, jira_request
from analyzer.parser import parse_list_items

TARGET_NUM_RE = re.compile(r'KAT-(\d+)', re.I)
SOURCE_SPEC_RE = re.compile(r'^KAT-(\d+):(\d+)$', re.I)


def parse_source_spec(spec: str) -> tuple[str, int, str]:
    m = SOURCE_SPEC_RE.match(spec.strip())
    if not m:
        raise argparse.ArgumentTypeError(f'无效条目格式: {spec!r}，应为 KAT-12345:3')
    issue_key = f'KAT-{m.group(1)}'
    index = int(m.group(2))
    source_num = m.group(1)
    return issue_key, index, source_num


def target_number(target_key: str) -> str:
    m = TARGET_NUM_RE.search(target_key)
    if not m:
        raise SystemExit(f'无法解析目标 issue 编号: {target_key}')
    return m.group(1)


def find_list_item_by_index(desc_content, target_index):
    def walk(nodes):
        for node in nodes:
            if not isinstance(node, dict):
                continue
            if node.get('type') == 'orderedList':
                start = node.get('attrs', {}).get('order', 1)
                for pos, child in enumerate(node.get('content', [])):
                    if child.get('type') != 'listItem':
                        continue
                    jira_index = start + pos
                    if jira_index == target_index:
                        para = next(
                            (c for c in child.get('content', []) if c.get('type') == 'paragraph'),
                            None,
                        )
                        return child, para, node
            if 'content' in node and node.get('type') != 'listItem':
                found = walk(node['content'])
                if found[0]:
                    return found
        return None, None, None

    content = desc_content if isinstance(desc_content, list) else desc_content.get('content', [])
    return walk(content)


def get_trailing_media(top_content, ol_node, list_item):
    items_in_ol = [c for c in ol_node.get('content', []) if c.get('type') == 'listItem']
    if not items_in_ol or items_in_ol[-1] is not list_item:
        return []
    ol_idx = next(i for i, n in enumerate(top_content) if n is ol_node)
    trailing = []
    for j in range(ol_idx + 1, len(top_content)):
        n = top_content[j]
        if n.get('type') == 'mediaSingle':
            trailing.append(n)
        else:
            break
    return trailing


def empty_adf_doc():
    return {'type': 'doc', 'version': 1, 'content': []}


def ensure_adf_doc(description):
    if not description:
        return empty_adf_doc()
    return description


def compute_new_number(target_description_content, extra_count=0):
    target_description_content = ensure_adf_doc(target_description_content)
    top = (
        target_description_content
        if isinstance(target_description_content, list)
        else target_description_content.get('content', [])
    )
    used_orders = set()
    empty_slots = {}
    for node in top:
        if isinstance(node, dict) and node.get('type') == 'orderedList':
            order = node.get('attrs', {}).get('order', 1)
            used_orders.add(order)
            items_in = [c for c in node.get('content', []) if c.get('type') == 'listItem']
            if len(items_in) == 1:
                para = next((c for c in items_in[0].get('content', []) if c.get('type') == 'paragraph'), None)
                texts = para.get('content', []) if para else []
                has_text = any(n.get('type') == 'text' and n.get('text', '').strip() for n in texts)
                has_mention = any(n.get('type') == 'mention' for n in texts)
                has_media = any(c.get('type') == 'mediaSingle' for c in items_in[0].get('content', []))
                if not has_text and not has_mention and not has_media:
                    empty_slots[order] = node

    items, _ = parse_list_items(target_description_content)
    parsed_indices = {i['index'] for i in items}
    all_used = used_orders | parsed_indices

    for slot_order in sorted(empty_slots):
        if slot_order not in parsed_indices:
            return slot_order + extra_count

    base = (max(all_used) if all_used else 0) + 1
    return base + extra_count


def regenerate_local_ids(node):
    if isinstance(node, dict):
        attrs = node.get('attrs')
        if isinstance(attrs, dict) and 'localId' in attrs:
            attrs['localId'] = str(uuid.uuid4())
        if 'localId' in node:
            node['localId'] = str(uuid.uuid4())
        for v in node.values():
            regenerate_local_ids(v)
    elif isinstance(node, list):
        for item in node:
            regenerate_local_ids(item)


def para_text(para):
    if not para:
        return ''
    return ''.join(n.get('text', '') for n in para.get('content', []) if n.get('type') == 'text')


def strip_moved_prefix(para):
    content = para.get('content', [])
    if not re.search(r'\(moved\s+\d+', para_text(para), re.I):
        return
    while content:
        node = content[0]
        if node.get('type') == 'text' and any(m.get('type') == 'strong' for m in node.get('marks', [])):
            content.pop(0)
            if ')' in node.get('text', ''):
                break
        else:
            break


def strip_from_prefix(para):
    content = para.get('content', [])
    if not re.search(r'\(From\s+\d+', para_text(para), re.I):
        return
    while content:
        node = content[0]
        if node.get('type') == 'text' and any(m.get('type') == 'strong' for m in node.get('marks', [])):
            content.pop(0)
            if ')' in node.get('text', ''):
                break
        else:
            break


def make_moved_prefix(target_num, new_number):
    return [
        {'type': 'text', 'text': f'(moved {target_num} No.', 'marks': [{'type': 'strong'}]},
        {'type': 'text', 'text': str(new_number), 'marks': [{'type': 'strong'}]},
        {'type': 'text', 'text': ') ', 'marks': [{'type': 'strong'}]},
    ]


def replace_moved_prefix(para, target_num, new_number):
    strip_moved_prefix(para)
    para['content'] = make_moved_prefix(target_num, new_number) + para['content']


def collect_media_singles(node, result=None):
    if result is None:
        result = []
    if isinstance(node, dict):
        if node.get('type') == 'mediaSingle':
            result.append(node)
        for v in node.values():
            collect_media_singles(v, result)
    elif isinstance(node, list):
        for item in node:
            collect_media_singles(item, result)
    return result


class JiraMigrator:
    def __init__(self, config, dry_run=False):
        self.config = config
        self.base = config['jira']['base_url']
        self.session = build_jira_session(config)
        self.dry_run = dry_run

    def fetch_issue(self, key, fields='description,attachment'):
        resp = jira_request(self.session, 'GET', f'{self.base}/rest/api/3/issue/{key}?fields={fields}')
        resp.raise_for_status()
        return resp.json()['fields']

    def put_description(self, key, description):
        if self.dry_run:
            print(f'  [dry-run] PUT {key} description')
            return
        resp = jira_request(
            self.session,
            'PUT',
            f'{self.base}/rest/api/3/issue/{key}',
            json={'fields': {'description': description}},
        )
        if resp.status_code not in (200, 204):
            raise RuntimeError(f'PUT {key} failed: {resp.status_code} {resp.text[:500]}')

    def upload_attachment(self, target_key, filename, data, max_attempts=5):
        mime, _ = mimetypes.guess_type(filename)
        mime = mime or 'application/octet-stream'
        url = f'{self.base}/rest/api/3/issue/{target_key}/attachments'
        last_exc = None
        for attempt in range(max_attempts):
            try:
                resp = requests.post(
                    url,
                    auth=self.session.auth,
                    headers={'X-Atlassian-Token': 'no-check'},
                    files={'file': (filename, data, mime)},
                    timeout=300,
                )
                if resp.status_code in (200, 201):
                    return resp.json()[0]
                raise RuntimeError(f'Upload failed {filename}: {resp.status_code} {resp.text[:300]}')
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
                last_exc = exc
                wait = 2 ** attempt
                print(f'    上传中断，{wait}s 后重试 ({attempt + 1}/{max_attempts}): {exc.__class__.__name__}')
                time.sleep(wait)
        raise RuntimeError(f'Upload failed after {max_attempts} attempts: {filename}') from last_exc

    def get_media_uuid(self, attachment_id):
        resp = jira_request(
            self.session,
            'GET',
            f'{self.base}/rest/api/3/attachment/content/{attachment_id}',
            allow_redirects=False,
            timeout=30,
        )
        location = resp.headers.get('Location', '')
        m = re.search(r'/file/([a-f0-9-]+)/binary', location)
        if not m:
            raise RuntimeError(f'Cannot get media UUID for attachment {attachment_id}')
        return m.group(1)

    @staticmethod
    def find_attachment_by_filename(attachments, filename):
        for att in attachments:
            if att.get('filename') == filename:
                return att
        norm = filename.replace('\u202f', ' ')
        for att in attachments:
            if att.get('filename', '').replace('\u202f', ' ') == norm:
                return att
        return None

    def download_attachment(self, att_id):
        resp = jira_request(self.session, 'GET', f'{self.base}/rest/api/3/attachment/content/{att_id}', timeout=120)
        resp.raise_for_status()
        return resp.content

    def process_media_in_copy(self, migrated_li, source_attachments, target_key):
        uploaded = []
        for ms in collect_media_singles(migrated_li):
            med = ms['content'][0]
            alt = med.get('attrs', {}).get('alt', '')
            att = self.find_attachment_by_filename(source_attachments, alt)
            if not att:
                raise RuntimeError(f'Attachment not found: {alt!r}')
            data = self.download_attachment(att['id'])
            if self.dry_run:
                print(f'    [dry-run] upload {att["filename"]} -> {target_key}')
                med['attrs']['id'] = str(uuid.uuid4())
            else:
                new_att = self.upload_attachment(target_key, att['filename'], data)
                med['attrs']['id'] = self.get_media_uuid(new_att['id'])
            uploaded.append(att['filename'])
        return uploaded

    def build_migrated_list_item(self, source_desc, source_attachments, source_idx, target_key):
        top = source_desc.get('content', [])
        li, para, ol = find_list_item_by_index(top, source_idx)
        if not li or not para:
            raise RuntimeError(f'Cannot find source item #{source_idx}')

        migrated_li = copy.deepcopy(li)
        regenerate_local_ids(migrated_li)

        for tm in get_trailing_media(top, ol, li):
            trailing_copy = copy.deepcopy(tm)
            regenerate_local_ids(trailing_copy)
            migrated_li['content'].append(trailing_copy)

        migrated_para = next(c for c in migrated_li['content'] if c.get('type') == 'paragraph')
        strip_moved_prefix(migrated_para)
        strip_from_prefix(migrated_para)

        uploaded = self.process_media_in_copy(migrated_li, source_attachments, target_key)
        return migrated_li, uploaded

    def strip_from_on_target(self, target_key, indices):
        fields = self.fetch_issue(target_key, fields='description')
        desc = copy.deepcopy(ensure_adf_doc(fields['description']))
        top = desc.get('content', [])
        for idx in indices:
            _, para, _ = find_list_item_by_index(top, idx)
            if not para:
                raise RuntimeError(f'Cannot find target item #{idx} on {target_key}')
            strip_from_prefix(para)
            print(f'  {target_key} #{idx}: 已移除 (From …) 前缀')
        self.put_description(target_key, desc)

    def cmd_migrate(self, target_key, sources):
        target_num = target_number(target_key)
        print(f'目标: {target_key}，迁移 {len(sources)} 条')

        target_fields = self.fetch_issue(target_key, fields='description')
        target_desc = copy.deepcopy(ensure_adf_doc(target_fields['description']))

        source_cache = {}
        new_ols = []
        source_updates = {}

        for extra, (source_key, source_idx, source_num) in enumerate(sources):
            new_number = compute_new_number(target_desc, extra)
            print(f'  {source_key} #{source_idx} -> {target_key} #{new_number}')

            if source_key not in source_cache:
                fields = self.fetch_issue(source_key)
                source_cache[source_key] = {
                    'description': fields['description'],
                    'attachments': fields.get('attachment', []),
                }

            migrated_li, uploaded = self.build_migrated_list_item(
                source_cache[source_key]['description'],
                source_cache[source_key]['attachments'],
                source_idx,
                target_key,
            )
            if uploaded:
                print(f'    附件: {", ".join(uploaded)}')

            new_ol = {
                'type': 'orderedList',
                'attrs': {'order': new_number, 'localId': f'migrated_{uuid.uuid4().hex[:12]}'},
                'content': [migrated_li],
            }
            new_ols.append(new_ol)
            target_desc['content'].append(new_ol)
            source_updates.setdefault(source_key, []).append((source_idx, new_number))

        print('写入目标 issue...')
        self.put_description(target_key, target_desc)

        print('更新源 issue moved 标记...')
        for source_key, updates in source_updates.items():
            fields = self.fetch_issue(source_key, fields='description')
            src_desc = copy.deepcopy(fields['description'])
            top = src_desc.get('content', [])
            for source_idx, new_number in updates:
                _, para, _ = find_list_item_by_index(top, source_idx)
                replace_moved_prefix(para, target_num, new_number)
                print(f'  {source_key} #{source_idx} -> (moved {target_num} No. {new_number})')
            self.put_description(source_key, src_desc)

        self._verify_migrate(target_key, sources, source_updates)

    def cmd_mark(self, target_key, sources, target_indices):
        target_num = target_number(target_key)
        print(f'目标: {target_key}，仅标记 {len(sources)} 条源条目')

        by_issue = {}
        for (source_key, source_idx, _), new_number in zip(sources, target_indices):
            print(f'  {source_key} #{source_idx} -> (moved {target_num} No. {new_number})')
            by_issue.setdefault(source_key, []).append((source_idx, new_number))

        for source_key, updates in by_issue.items():
            fields = self.fetch_issue(source_key, fields='description')
            src_desc = copy.deepcopy(fields['description'])
            top = src_desc.get('content', [])
            for source_idx, new_number in updates:
                _, para, _ = find_list_item_by_index(top, source_idx)
                replace_moved_prefix(para, target_num, new_number)
            self.put_description(source_key, src_desc)

        print('完成。')

    def _verify_migrate(self, target_key, sources, source_updates):
        print('\n校验:')
        target_fields = self.fetch_issue(target_key, fields='description')
        target_items, _ = parse_list_items(target_fields['description'])

        for source_key, source_idx, _ in sources:
            new_number = dict(source_updates[source_key])[source_idx]
            item = next((i for i in target_items if i['index'] == new_number), None)
            ok = item is not None and not re.search(r'\(From\s+\d+', item['text'], re.I)
            print(f'  {target_key} #{new_number} [{"OK" if ok else "FAIL"}]')

        for source_key, updates in source_updates.items():
            fields = self.fetch_issue(source_key, fields='description')
            src_items, _ = parse_list_items(fields['description'])
            for source_idx, new_number in updates:
                item = next((i for i in src_items if i['index'] == source_idx), None)
                m = re.search(rf'moved\s+{target_number(target_key)}\s+no\.?\s*(\d+)', item['text'], re.I)
                ok = item and item['is_moved'] and m and int(m.group(1)) == new_number
                print(f'  {source_key} #{source_idx} [{"OK" if ok else "FAIL"}]')


def parse_target_index_spec(spec: str) -> tuple[str, int]:
    m = re.match(r'^KAT-(\d+):(\d+)$', spec.strip(), re.I)
    if not m:
        raise argparse.ArgumentTypeError(f'无效目标条目格式: {spec!r}，应为 KAT-12345:1')
    return f'KAT-{m.group(1)}', int(m.group(2))


def parse_indices(value: str) -> list[int]:
    parts = [p.strip() for p in value.split(',') if p.strip()]
    if not parts:
        raise argparse.ArgumentTypeError('--at 不能为空')
    try:
        return [int(p) for p in parts]
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f'--at 必须是整数列表: {value!r}') from exc


def build_parser():
    parser = argparse.ArgumentParser(description='Jira 列表条目迁移工具')
    parser.add_argument('--dry-run', action='store_true', help='预览操作，不写入 Jira')
    sub = parser.add_subparsers(dest='command', required=True)

    migrate_p = sub.add_parser('migrate', help='完整迁移：复制内容+附件到目标，并更新源 moved 标记')
    migrate_p.add_argument('--target', required=True, help='目标 issue，如 KAT-11496')
    migrate_p.add_argument('sources', nargs='+', type=parse_source_spec, help='源条目，如 KAT-11267:3')

    mark_p = sub.add_parser('mark', help='仅标记：按指定目标编号更新源 moved 标记')
    mark_p.add_argument('--target', required=True, help='目标 issue，如 KAT-11496')
    mark_p.add_argument(
        '--at',
        required=True,
        help='目标条目编号，多条用逗号分隔，与 sources 一一对应，如 1 或 7,8',
    )
    mark_p.add_argument('sources', nargs='+', type=parse_source_spec, help='源条目，如 KAT-11349:2')

    strip_p = sub.add_parser('strip-from', help='移除目标 issue 条目上的 (From …) 前缀')
    strip_p.add_argument('targets', nargs='+', type=parse_target_index_spec, help='目标条目，如 KAT-11751:1')

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    config = load_config()
    migrator = JiraMigrator(config, dry_run=args.dry_run)

    if args.command == 'migrate':
        migrator.cmd_migrate(args.target.upper(), args.sources)
    elif args.command == 'mark':
        indices = parse_indices(args.at)
        if len(indices) != len(args.sources):
            raise SystemExit(f'--at 条目数 ({len(indices)}) 必须与 sources 数 ({len(args.sources)}) 一致')
        migrator.cmd_mark(args.target.upper(), args.sources, indices)
    elif args.command == 'strip-from':
        by_issue = {}
        for issue_key, idx in args.targets:
            by_issue.setdefault(issue_key, []).append(idx)
        for issue_key, indices in by_issue.items():
            print(f'移除 {issue_key} 上的 (From …) 前缀:')
            migrator.strip_from_on_target(issue_key, indices)


if __name__ == '__main__':
    main()
