"""
列表项括号状态标记字典

括号内以这些前缀开头时，视为对应处理状态（与 Jira Description 写法一致）。
括号内含 reproduce / duplication 也视为 backlog 族已处理。
"""

import re

# backlog 族：均视为已搁置（is_backlog=True），展示标签可不同
BACKLOG_STATUS_PREFIXES = {
    'backlog': 'Backlog',
    'invalid': 'Invalid',
    'cannot reproduce': 'Cannot reproduce',
}

# 括号内「包含」即命中（不要求段首前缀）
BACKLOG_PAREN_CONTAINS = {
    'reproduce': 'Cannot reproduce',
    'duplication': 'Duplication',
}

DONE_PREFIX_PATTERN = re.compile(
    r'[\(（]\s*done\b|^done[\)）\s]',
    re.IGNORECASE,
)
MOVED_PREFIX_PATTERN = re.compile(r'[\(（]\s*move', re.IGNORECASE)
_PAREN_CHUNK_PATTERN = re.compile(r'[\(（][^\)）]*[\)）]')


def _match_backlog_prefix(lower_text):
    """返回命中的 backlog 前缀，未命中返回 None。"""
    for prefix in BACKLOG_STATUS_PREFIXES:
        if re.search(rf'[\(（]\s*{re.escape(prefix)}\b', lower_text):
            return prefix
    return None


def _match_backlog_paren_contains(lower_text):
    """括号内含关键词时返回展示标签，否则 None。"""
    for chunk in _PAREN_CHUNK_PATTERN.findall(lower_text):
        for keyword, label in BACKLOG_PAREN_CONTAINS.items():
            if keyword in chunk:
                return label
    return None


def detect_processed_flags(text):
    """
    检测列表项括号状态标记。

    Returns:
        tuple: (is_done, is_backlog, backlog_label, is_moved)
    """
    lower_text = text.lower()
    is_done = bool(DONE_PREFIX_PATTERN.search(lower_text))
    backlog_prefix = _match_backlog_prefix(lower_text)
    if backlog_prefix is not None:
        backlog_label = BACKLOG_STATUS_PREFIXES[backlog_prefix]
    else:
        backlog_label = _match_backlog_paren_contains(lower_text)
    is_backlog = backlog_label is not None
    is_moved = bool(MOVED_PREFIX_PATTERN.search(lower_text))
    return is_done, is_backlog, backlog_label, is_moved
