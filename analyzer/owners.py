"""
Owner 识别模块

定义团队成员列表及其关键词映射，
用于从 Jira 任务描述中自动识别负责人。
"""

# 团队成员及其匹配关键词
# 每个 key 是内部标识符，value 为 Jira @mention 中的标准写法
OWNERS = {
    'jayce': ['@Jayce'],
    'zhiyong': ['@zhiyong song'],
    'tiancheng': ['@Tiancheng Tang'],
    'jun': ['@Jun Li'],
    'jiaqi': ['@Jiaqi Yu'],
    'lory': ['@Lory Jiang'],
    'tianye': ['@Tian Ye'],
    'fengxia': ['@Feng Xia'],
    'fred': ['@Fred Steger'],
    'joey': ['@Joey Hou'],
    'chenglim': ['@Cheng Lim'],
    'zhengzhu': ['@Zheng Zhu'],
}

# Owner 在 HTML 中的展示名称
OWNER_DISPLAY_NAMES = {
    'jayce': 'Jayce',
    'zhiyong': 'Zhiyong',
    'tiancheng': 'Tiancheng',
    'jun': 'Jun',
    'jiaqi': 'Jiaqi',
    'lory': 'Lory',
    'tianye': 'Tian Ye',
    'fengxia': 'Feng Xia',
    'fred': 'Fred',
    'joey': 'Joey',
    'chenglim': 'Cheng Lim',
    'zhengzhu': 'Zheng Zhu',
}


def detect_owner(text):
    """
    检测文本中提到的负责人

    遍历所有 owner 的关键词列表，检查文本中是否包含匹配项。
    匹配不区分大小写。

    Args:
        text: 待检测的文本字符串

    Returns:
        list[str]: 匹配到的 owner 标识符列表（去重）
    """
    detected = []
    lower_text = text.lower()

    for owner_name, keywords in OWNERS.items():
        for keyword in keywords:
            if keyword.lower() in lower_text:
                if owner_name not in detected:
                    detected.append(owner_name)
                break

    return detected
