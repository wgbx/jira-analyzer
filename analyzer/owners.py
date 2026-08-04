"""
Owner 识别模块

定义团队成员列表及其关键词映射，
用于从 Jira 任务描述中自动识别负责人。

新增成员只需在 OWNER_REGISTRY 加一条：
    'key': {
        'mentions': ['@Jira 显示名'],   # 必填，与 Jira @mention 完全一致
        'display': '前端按钮名',         # 必填
        'color': ('#背景色', '#文字色'), # 可选，不填用默认灰
    }
"""

# 唯一真相来源：所有 owner 信息集中在这里维护
# 书写顺序 = 筛选栏展示顺序
OWNER_REGISTRY = {
    # —— 武汉团队 ——
    # 前端
    'jayce':    {'mentions': ['@Jayce'],         'display': 'Jayce',     'color': ('#dbeafe', '#1e40af')},
    'zhiyong':  {'mentions': ['@zhiyong song'],  'display': 'Zhiyong',   'color': ('#dcfce7', '#166534')},
    'tiancheng':{'mentions': ['@Tiancheng Tang'],'display': 'Tiancheng', 'color': ('#f3e8ff', '#6b21a8')},
    'jun':      {'mentions': ['@Jun Li'],         'display': 'Jun',       'color': ('#fef3c7', '#92400e')},
    'cici':     {'mentions': ['@cici Huang'],     'display': 'Cici',      'color': ('#fdf2f8', '#9d174d')},
    'jiaqi':    {'mentions': ['@Jiaqi Yu'],       'display': 'Jiaqi',     'color': ('#fee2e2', '#991b1b')},
    'zhengzhu': {'mentions': ['@Zheng Zhu'],      'display': 'Zheng Zhu', 'color': ('#ffedd5', '#9a3412')},
    'dajiang':  {'mentions': ['@Dajiang Zuo'],    'display': 'Dajiang',   'color': ('#faf5ff', '#6b21a8')},
    # 后端
    'fengxia':  {'mentions': ['@Feng Xia'],       'display': 'Feng Xia',  'color': ('#fef9c3', '#854d0e')},
    'june':     {'mentions': ['@June Teng'],      'display': 'June',      'color': ('#ecfdf5', '#065f46')},
    'neo':      {'mentions': ['@Neo Wang'],       'display': 'Neo',       'color': ('#eff6ff', '#1e3a8a')},
    'pengfei':  {'mentions': ['@Pengfei Wu'],     'display': 'Pengfei',   'color': ('#f0fdf4', '#15803d')},
    'zhengchun':{'mentions': ['@zhengchun Zhou'], 'display': 'Zhengchun', 'color': ('#fff7ed', '#c2410c')},
    # —— 成都团队 ——
    'lory':     {'mentions': ['@Lory Jiang'],     'display': 'Lory',      'color': ('#e0f2fe', '#0c4a6e')},
    'tianye':   {'mentions': ['@Tian Ye'],        'display': 'Tian Ye',   'color': ('#fce7f3', '#9d174d')},
    # —— 美国团队 ——
    'fred':     {'mentions': ['@Fred Steger'],    'display': 'Fred',      'color': ('#e2e8f0', '#334155')},
    'jiangtian':{'mentions': ['@Jiangtian Hou'], 'display': 'Joey',      'color': ('#d1fae5', '#065f46')},
    'chenglim': {'mentions': ['@Cheng Lim'],      'display': 'Cheng Lim', 'color': ('#ede9fe', '#5b21b6')},
}

# 兼容导出（供现有 import 使用，勿手动编辑）
OWNERS = {k: v['mentions'] for k, v in OWNER_REGISTRY.items()}
OWNER_DISPLAY_NAMES = {k: v['display'] for k, v in OWNER_REGISTRY.items()}


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
