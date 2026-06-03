"""
ADF（Atlassian Document Format）解析模块

负责将 Jira 的结构化文档格式（ADF）转换为可读的文本，
提取列表项、检测处理状态和识别负责人。
"""

from analyzer.owners import detect_owner
from analyzer.statuses import detect_processed_flags


def extract_text_from_adf(content):
    """
    从 Atlassian Document Format 中提取纯文本

    递归遍历 ADF 节点树，提取文本节点和 mention 节点的内容。
    同时检测文本是否带有删除线标记。

    Args:
        content: ADF 节点（dict 或 list）

    Returns:
        list[tuple[str, bool]]: [(文本内容, 是否有删除线), ...]
    """
    texts = []

    if isinstance(content, dict):
        content_type = content.get('type', '')

        if content_type == 'text':
            # 纯文本节点
            text = content.get('text', '')
            marks = content.get('marks', [])
            is_strikethrough = any(m.get('type') == 'strike' for m in marks)
            return [(text, is_strikethrough)]

        elif content_type == 'mention':
            # @mention 节点，提取 mention 的显示文本（如 @Zhiyong Song）
            mention_text = content.get('attrs', {}).get('text', '')
            if mention_text:
                return [(mention_text, False)]

        elif 'content' in content:
            return extract_text_from_adf(content['content'])

    elif isinstance(content, list):
        for item in content:
            texts.extend(extract_text_from_adf(item))

    return texts


def extract_mentions_from_adf(content):
    """
    从 ADF 中提取所有 @mention 的文本

    专门用于 owner 识别，遍历整个 ADF 树查找 mention 类型的节点。

    Args:
        content: ADF 节点（dict 或 list）

    Returns:
        list[str]: mention 文本列表（如 ['@Zhiyong Song', '@Jun Li']）
    """
    mentions = []

    if isinstance(content, dict):
        if content.get('type') == 'mention':
            mention_text = content.get('attrs', {}).get('text', '')
            if mention_text:
                mentions.append(mention_text)
        for v in content.values():
            if isinstance(v, (dict, list)):
                mentions.extend(extract_mentions_from_adf(v))
    elif isinstance(content, list):
        for item in content:
            mentions.extend(extract_mentions_from_adf(item))

    return mentions


def _detect_item_owners(item_content, full_text):
    """
    综合检测列表项的负责人

    先从文本内容匹配，如果未命中则从 @mention 节点中查找。

    Args:
        item_content: 列表项的 ADF 内容
        full_text: 列表项的完整文本

    Returns:
        list[str]: 匹配到的 owner 标识符列表
    """
    owners = detect_owner(full_text)

    # 文本中未匹配到 owner，尝试从 @mention 节点中查找
    if not owners:
        mention_texts = extract_mentions_from_adf(item_content)
        for mention_text in mention_texts:
            owners.extend(detect_owner(mention_text))
        # 利用 dict 去重并保持顺序
        owners = list(dict.fromkeys(owners))

    return owners


def _extract_list_item_direct_text(list_item):
    """
    提取 listItem 的直接文本（不含嵌套 orderedList 内的条目）。

    Jira 中嵌套子列表会单独编号；若把子列表文字合并进父条目，
    会导致序号与 Jira 界面不一致。
    """
    parts = []
    for child in list_item.get('content', []):
        if child.get('type') == 'orderedList':
            continue
        parts.extend(extract_text_from_adf(child))
    return parts


def _make_parsed_item(jira_index, full_text, list_item_content, is_strikethrough):
    """构建单条解析结果。"""
    is_done, is_backlog, backlog_label, is_moved = detect_processed_flags(full_text)
    owners = _detect_item_owners(list_item_content, full_text)
    return {
        'index': jira_index,
        'text': full_text,
        'is_done': is_done,
        'is_backlog': is_backlog,
        'backlog_label': backlog_label,
        'is_moved': is_moved,
        'is_strikethrough': is_strikethrough,
        'is_processed': is_done or is_backlog or is_moved or is_strikethrough,
        'owners': owners,
    }


def _parse_ordered_list(ordered_list):
    """
    解析有序列表，序号与 Jira 一致：orderedList.attrs.order + 段内位置。
    """
    items = []
    start_order = ordered_list.get('attrs', {}).get('order', 1)

    for position, child in enumerate(ordered_list.get('content', [])):
        if child.get('type') != 'listItem':
            continue

        jira_index = start_order + position
        parts = _extract_list_item_direct_text(child)
        full_text = ' '.join(t[0] for t in parts).strip()
        is_strikethrough = any(t[1] for t in parts)

        if full_text:
            items.append(_make_parsed_item(
                jira_index, full_text, child.get('content', []), is_strikethrough,
            ))

        # 嵌套子列表在 Jira 中通常不占全局编号，不单独成条，避免与父级 order 冲突

    return items


def _parse_bullet_list(bullet_list, start_index):
    """无序列表无 order 属性，按文档内顺序从 start_index 递增编号。"""
    items = []
    index = start_index
    for child in bullet_list.get('content', []):
        if child.get('type') != 'listItem':
            continue
        parts = _extract_list_item_direct_text(child)
        full_text = ' '.join(t[0] for t in parts).strip()
        is_strikethrough = any(t[1] for t in parts)
        if full_text:
            items.append(_make_parsed_item(
                index, full_text, child.get('content', []), is_strikethrough,
            ))
            index += 1
    return items, index


def _walk_adf_for_list_items(node, items, bullet_start_index):
    """遍历 ADF，遇到 orderedList / bulletList 时解析列表项。"""
    if isinstance(node, list):
        next_bullet = bullet_start_index
        for child in node:
            next_bullet = _walk_adf_for_list_items(child, items, next_bullet)
        return next_bullet

    if not isinstance(node, dict):
        return bullet_start_index

    node_type = node.get('type', '')
    if node_type == 'orderedList':
        items.extend(_parse_ordered_list(node))
        return bullet_start_index
    if node_type == 'bulletList':
        sub_items, next_index = _parse_bullet_list(node, bullet_start_index)
        items.extend(sub_items)
        return next_index
    if 'content' in node and node_type != 'listItem':
        return _walk_adf_for_list_items(node['content'], items, bullet_start_index)

    return bullet_start_index


def parse_list_items(content, index=1):
    """
    解析 ADF 中的列表项

    有序列表条目序号取自 Jira ADF 的 orderedList.attrs.order（与 Jira 界面一致）。
    嵌套在 listItem 内的子列表单独成条，不再合并进父条目文本。

    Args:
        content: ADF 内容（list 或 dict）
        index: 无序列表的起始编号（orderedList 不使用此参数）

    Returns:
        tuple[list[dict], int]:
            - items: 解析后的条目列表
            - next_index: 供无序列表续编的最大序号 + 1
    """
    items = []
    _walk_adf_for_list_items(content, items, index)
    next_index = max((item['index'] for item in items), default=index - 1) + 1
    return items, next_index
