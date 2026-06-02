"""
发布排期数据

从 data/scheduled.json 加载已排期条目（issue 编号 + 列表序号），
供分析与报告标记「已排期」。
"""

import json
from pathlib import Path

_DEFAULT_PATH = Path(__file__).resolve().parent.parent / 'data' / 'scheduled.json'


def load_scheduled(path=None):
    """
    加载排期配置

    Returns:
        dict: 含 project_key、releases 列表；文件不存在时返回空结构
    """
    file_path = Path(path) if path else _DEFAULT_PATH
    if not file_path.is_file():
        return {'project_key': 'KAT', 'releases': []}

    with open(file_path, encoding='utf-8') as f:
        return json.load(f)


def build_scheduled_lookup(data):
    """
    构建 (task_key, index) -> 发布周标签 的查找表

    同一条目出现在多周时保留日期较晚的一周。
    """
    project = data.get('project_key', 'KAT')
    lookup = {}

    for release in sorted(data.get('releases', []), key=lambda r: r.get('date', '')):
        label = release.get('label', release.get('date', ''))
        for entry in release.get('items', []):
            issue_num = str(entry['issue'])
            task_key = f"{project}-{issue_num}"
            index = int(entry['index'])
            lookup[(task_key, index)] = label

    return lookup


def get_scheduled_lookup(config=None):
    """根据 config 可选路径加载查找表"""
    path = None
    if config:
        path = config.get('scheduled', {}).get('path')
    return build_scheduled_lookup(load_scheduled(path))
