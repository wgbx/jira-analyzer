"""
ADF（Atlassian Document Format）解析模块

负责将 Jira 的结构化文档格式（ADF）转换为可读的文本，
提取列表项、检测处理状态和识别负责人。
"""

import re

from analyzer.owners import detect_owner


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


def _check_status_flags(text):
    """
    检测列表项的处理状态标记

    支持的标记格式（中英文括号、有无空格）：
    - (done), ( done ), （done）, （ done ）
    - (backlog), （backlog）
    - (moved), （moved）

    注意：不匹配普通句子中出现的 done/backlog/moved 单词，
    避免将 "this should be done by..." 等误判为已完成。

    Args:
        text: 待检测的文本（建议先转小写）

    Returns:
        tuple[bool, bool, bool]: (是否完成, 是否搁置, 是否已转移)
    """
    lower_text = text.lower()
    is_done = bool(re.search(r'[\(（]\s*done\s*[\)）]|^done[\)）\s]', lower_text))
    is_backlog = bool(re.search(r'[\(（]\s*backlog\s*[\)）]', lower_text))
    is_moved = bool(re.search(r'[\(（]\s*moved\s*[\)）]', lower_text))
    return is_done, is_backlog, is_moved


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


def parse_list_items(content, index=1):
    """
    解析 ADF 中的列表项

    递归遍历 ADF 结构，提取所有 listItem 类型的节点，
    识别每个条目的处理状态和负责人。

    Args:
        content: ADF 内容（list 或 dict）
        index: 当前条目编号（用于递归时传递计数）

    Returns:
        tuple[list[dict], int]:
            - items: 解析后的条目列表，每条包含:
                - index: 序号
                - text: 文本内容
                - is_done/is_backlog/is_moved: 各种状态标记
                - is_strikethrough: 是否有删除线
                - is_processed: 是否已处理（任一状态为 True）
                - owners: 负责人列表
            - next_index: 下一个可用的序号
    """
    items = []

    if isinstance(content, list):
        for item in content:
            if not isinstance(item, dict):
                continue

            item_type = item.get('type', '')

            if item_type == 'listItem':
                # 提取列表项的文本内容
                texts = extract_text_from_adf(item.get('content', []))
                full_text = ' '.join([t[0] for t in texts]).strip()
                is_strikethrough = any(t[1] for t in texts)

                if not full_text:
                    continue

                # 检测状态标记
                is_done, is_backlog, is_moved = _check_status_flags(full_text)

                # 检测负责人
                owners = _detect_item_owners(item.get('content', []), full_text)

                items.append({
                    'index': index,
                    'text': full_text,
                    'is_done': is_done,
                    'is_backlog': is_backlog,
                    'is_moved': is_moved,
                    'is_strikethrough': is_strikethrough,
                    'is_processed': is_done or is_backlog or is_moved or is_strikethrough,
                    'owners': owners,
                })
                index += 1

            elif 'content' in item:
                # 递归解析嵌套结构（如 bulletList > listItem）
                sub_items, new_index = parse_list_items(item['content'], index)
                items.extend(sub_items)
                index = new_index

    return items, index
