"""
列表项括号状态标记字典

括号内以这些前缀开头时，视为对应处理状态（与 Jira Description 写法一致）。
"""

import re

# backlog 族：均视为已搁置（is_backlog=True），展示标签可不同
BACKLOG_STATUS_PREFIXES = {
    'backlog': 'Backlog',
    'invalid': 'Invalid',
}

DONE_PREFIX_PATTERN = re.compile(
    r'[\(（]\s*done\b|^done[\)）\s]',
    re.IGNORECASE,
)
MOVED_PREFIX_PATTERN = re.compile(r'[\(（]\s*move', re.IGNORECASE)


def _match_backlog_prefix(lower_text):
    """返回命中的 backlog 前缀，未命中返回 None。"""
    for prefix in BACKLOG_STATUS_PREFIXES:
        if re.search(rf'[\(（]\s*{re.escape(prefix)}\b', lower_text):
            return prefix
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
    is_backlog = backlog_prefix is not None
    backlog_label = BACKLOG_STATUS_PREFIXES.get(backlog_prefix) if backlog_prefix else None
    is_moved = bool(MOVED_PREFIX_PATTERN.search(lower_text))
    return is_done, is_backlog, backlog_label, is_moved
