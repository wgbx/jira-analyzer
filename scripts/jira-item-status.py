#!/usr/bin/env python3
"""
Jira 列表条目状态标记 CLI。

实现 skills/jira-item-status.md：在条目前写入加粗的 (Done)/(Backlog) 等标记。

用法：

  # 默认 Backlog
  python3 scripts/jira-item-status.py KAT-11816:5

  # 指定状态
  python3 scripts/jira-item-status.py --status Done KAT-11816:1 KAT-11816:3
  python3 scripts/jira-item-status.py done 11816:1
  python3 scripts/jira-item-status.py --status "Cannot reproduce" KAT-11675:2

  # 预览
  python3 scripts/jira-item-status.py --dry-run KAT-11816:5
"""

from __future__ import annotations

import argparse
import copy
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from analyzer.config import load_config
from analyzer.jira_http import build_jira_session, jira_request
from analyzer.parser import parse_list_items
from analyzer.statuses import BACKLOG_STATUS_PREFIXES, detect_processed_flags

# 写入 Jira 时的规范文案（首字母大写）；默认 Backlog
STATUS_CANONICAL = {
    'done': 'Done',
    'backlog': 'Backlog',
    **{k: v for k, v in BACKLOG_STATUS_PREFIXES.items()},
}

KNOWN_STATUS_RE = re.compile(
    r'^\(\s*(?:'
    + '|'.join(re.escape(k) for k in sorted(STATUS_CANONICAL, key=len, reverse=True))
    + r')\s*\)',
    re.IGNORECASE,
)

ITEM_SPEC_RE = re.compile(
    r'^(?:KAT-)?(\d+):(\d+)$',
    re.IGNORECASE,
)


def parse_item_spec(spec: str) -> tuple[str, int]:
    m = ITEM_SPEC_RE.match(spec.strip())
    if not m:
        raise argparse.ArgumentTypeError(
            f'无效条目格式: {spec!r}，应为 KAT-11816:5 或 11816:5'
        )
    return f'KAT-{m.group(1)}', int(m.group(2))


def resolve_status_label(raw: str | None) -> str:
    if raw is None or not str(raw).strip():
        return 'Backlog'
    key = str(raw).strip().lower()
    # 去掉用户可能带上的括号
    key = key.strip('()（）').strip()
    if key in STATUS_CANONICAL:
        return STATUS_CANONICAL[key]
    # 自由文案：Title Case 单词（保留用户原意，但括号内首字母大写）
    return ' '.join(w.capitalize() if w.islower() else w for w in key.split())


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
                    if start + pos == target_index:
                        para = next(
                            (c for c in child.get('content', []) if c.get('type') == 'paragraph'),
                            None,
                        )
                        return child, para
            if 'content' in node and node.get('type') != 'listItem':
                found = walk(node['content'])
                if found[0]:
                    return found
        return None, None

    content = desc_content if isinstance(desc_content, list) else desc_content.get('content', [])
    return walk(content)


def make_status_prefix(label: str) -> dict:
    """标准：单个加粗 text 节点，形如 (Done) / (Backlog)。"""
    return {
        'type': 'text',
        'text': f'({label})',
        'marks': [{'type': 'strong'}],
    }


def _text_of(node: dict) -> str:
    return node.get('text', '') if node.get('type') == 'text' else ''


def strip_known_status_prefix(para: dict) -> None:
    """去掉段首已有的已知状态标记（Done / Backlog 族），保留其余正文与标记。"""
    content = para.get('content')
    if not content:
        return

    # 情况 A：首个 text 节点以 (Done) / (Backlog)… 开头（可与后续括号连写）
    first = content[0]
    if first.get('type') == 'text':
        text = first.get('text', '')
        m = KNOWN_STATUS_RE.match(text)
        if m:
            rest = text[m.end():]
            if rest:
                first['text'] = rest
            else:
                content.pop(0)
            return

    # 情况 B：拆成 "(" + "backlog"(strong) + ")…" 的历史写法
    if (
        len(content) >= 3
        and content[0].get('type') == 'text'
        and content[1].get('type') == 'text'
        and content[2].get('type') == 'text'
        and _text_of(content[0]).strip() == '('
        and _text_of(content[1]).strip().lower() in STATUS_CANONICAL
        and _text_of(content[2]).lstrip().startswith(')')
    ):
        third = content[2]
        third_text = third.get('text', '')
        # 去掉第一个 ')'
        idx = third_text.find(')')
        rest = third_text[idx + 1:]
        content.pop(0)
        content.pop(0)
        if rest:
            third['text'] = rest
        else:
            content.pop(0)


def apply_status(para: dict, label: str) -> None:
    strip_known_status_prefix(para)
    content = para.setdefault('content', [])
    # 若正文不以空白或 '(' 开头，在状态后补空格（单独非加粗节点），避免粘连
    prefix = make_status_prefix(label)
    if content:
        nxt = content[0]
        if nxt.get('type') == 'text':
            t = nxt.get('text', '')
            if t and not t[0].isspace() and not t.startswith('('):
                content.insert(0, {'type': 'text', 'text': ' '})
    content.insert(0, prefix)


def para_plain_text(para: dict) -> str:
    parts = []
    for n in para.get('content', []):
        if n.get('type') == 'text':
            parts.append(n.get('text', ''))
        elif n.get('type') == 'mention':
            parts.append(n.get('attrs', {}).get('text', ''))
    return ''.join(parts)


def group_by_issue(specs: list[tuple[str, int]]) -> dict[str, list[int]]:
    grouped: dict[str, list[int]] = {}
    for key, index in specs:
        grouped.setdefault(key, []).append(index)
    return grouped


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description='Jira 列表条目状态标记（Done / Backlog 等）')
    p.add_argument(
        '--dry-run',
        action='store_true',
        help='预览，不写入 Jira',
    )
    p.add_argument(
        '--status', '-s',
        default=None,
        help='状态文案，默认 Backlog；如 Done / Backlog / Invalid / "Cannot reproduce"',
    )
    p.add_argument(
        'items',
        nargs='+',
        help='条目：KAT-11816:5 或 11816:5；也可把状态写在首位：done 11816:5',
    )
    return p


def normalize_args(args: argparse.Namespace) -> tuple[str, list[tuple[str, int]]]:
    """支持 `done 11816:5` 把状态写在位置参数首位。"""
    raw_items = list(args.items)
    status_raw = args.status
    if status_raw is None and raw_items:
        first = raw_items[0].strip().lower().strip('()（）')
        if first in STATUS_CANONICAL and not ITEM_SPEC_RE.match(raw_items[0]):
            status_raw = raw_items.pop(0)
    if not raw_items:
        raise SystemExit('至少需要一个条目，如 KAT-11816:5')
    specs = [parse_item_spec(s) for s in raw_items]
    return resolve_status_label(status_raw), specs


def main() -> int:
    args = build_parser().parse_args()
    label, specs = normalize_args(args)
    cfg = load_config()
    session = build_jira_session(cfg)
    base = cfg['jira']['base_url'].rstrip('/')

    results = []
    for issue_key, indices in group_by_issue(specs).items():
        r = jira_request(session, 'GET', f'{base}/rest/api/3/issue/{issue_key}?fields=description')
        r.raise_for_status()
        desc = copy.deepcopy(r.json()['fields']['description'])
        if not desc or not desc.get('content'):
            print(f'ERROR: {issue_key} 描述为空', file=sys.stderr)
            return 1

        items, _ = parse_list_items(desc['content'])
        by_index = {it['index']: it for it in items}

        changed = False
        for index in indices:
            if index not in by_index:
                print(f'ERROR: {issue_key} 找不到条目 #{index}', file=sys.stderr)
                return 1
            li, para = find_list_item_by_index(desc['content'], index)
            if not para:
                print(f'ERROR: {issue_key} #{index} 无 paragraph', file=sys.stderr)
                return 1

            before = para_plain_text(para)
            apply_status(para, label)
            after = para_plain_text(para)
            flags = detect_processed_flags(after)
            results.append({
                'issue': issue_key,
                'index': index,
                'label': label,
                'before': before[:120],
                'after': after[:120],
                'is_done': flags[0],
                'is_backlog': flags[1],
                'backlog_label': flags[2],
            })
            changed = True
            print(f'{issue_key} #{index} → ({label})')
            print(f'  was: {before[:100]}')
            print(f'  now: {after[:100]}')

        if not changed:
            continue
        if args.dry_run:
            print(f'[dry-run] skip PUT {issue_key}')
            continue

        put = jira_request(
            session,
            'PUT',
            f'{base}/rest/api/3/issue/{issue_key}',
            json={'fields': {'description': desc}},
        )
        if put.status_code not in (200, 204):
            print(f'PUT {issue_key} failed: {put.status_code}\n{put.text[:500]}', file=sys.stderr)
            return 1
        print(f'PUT {issue_key}: {put.status_code}')

    print(f'Done. marked {len(results)} item(s) as ({label})')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
