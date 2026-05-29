"""
Jira API 客户端模块

封装与 Jira REST API 的交互逻辑，
包括子任务查询、任务详情获取和批量分析。
"""

import requests
from requests.auth import HTTPBasicAuth

from analyzer.parser import parse_list_items


def get_subtasks(config):
    """
    获取父任务下的所有分配给当前用户的子任务

    通过 JQL 查询 parent = {parent_issue} AND assignee = currentUser() 的任务。

    Args:
        config: 配置字典，需包含 jira.base_url、jira.email、jira.api_token、parent_issue

    Returns:
        list[dict]: 子任务列表，每个元素包含 key、fields 等信息
    """
    url = f"{config['jira']['base_url']}/rest/api/3/search/jql"
    auth = HTTPBasicAuth(config['jira']['email'], config['jira']['api_token'])

    jql = f"parent = {config['parent_issue']} AND assignee = currentUser()"

    response = requests.post(
        url,
        auth=auth,
        headers={"Content-Type": "application/json"},
        json={
            "jql": jql,
            "fields": ["summary", "description", "status", "key"],
            "maxResults": 100,
        },
        timeout=30,
    )

    if response.status_code != 200:
        print(f"获取子任务失败: {response.status_code} - {response.text}")
        return []

    return response.json().get('issues', [])


def get_issue_description(config, issue_key):
    """
    获取单个任务的详细信息

    Args:
        config: 配置字典
        issue_key: 任务编号（如 KAT-11330）

    Returns:
        dict | None: 任务信息，包含 key、summary、status、description；
                     获取失败时返回 None
    """
    url = f"{config['jira']['base_url']}/rest/api/3/issue/{issue_key}"
    auth = HTTPBasicAuth(config['jira']['email'], config['jira']['api_token'])

    response = requests.get(
        url,
        auth=auth,
        headers={"Content-Type": "application/json"},
        params={"fields": "description,summary,status"},
        timeout=30,
    )

    if response.status_code != 200:
        print(f"获取任务 {issue_key} 失败: {response.status_code}")
        return None

    data = response.json()
    return {
        'key': data.get('key'),
        'summary': data.get('fields', {}).get('summary', ''),
        'status': data.get('fields', {}).get('status', {}).get('name', ''),
        'description': data.get('fields', {}).get('description', {}),
    }


def analyze_issues(config):
    """
    分析父任务下所有子任务的条目

    逐个获取子任务的描述，解析其中的列表项，
    统计处理状态并按任务分组返回。

    Args:
        config: 配置字典

    Returns:
        dict: 分析结果，包含:
            - total: 总条目数
            - processed: 已处理条目数
            - unprocessed: 未处理条目数
            - grouped: 按任务编号分组的数据，每组包含 summary 和 items
    """
    print(f"正在分析 {config['parent_issue']} 的子任务...")

    subtasks = get_subtasks(config)
    print(f"找到 {len(subtasks)} 个子任务")

    all_items = []
    total_count = 0
    processed_count = 0

    for issue in subtasks:
        key = issue.get('key')
        summary = issue.get('fields', {}).get('summary', '')

        issue_data = get_issue_description(config, key)
        if not issue_data or not issue_data['description']:
            continue

        description = issue_data['description']
        if 'content' not in description:
            continue

        # 解析任务描述中的列表项
        items, _ = parse_list_items(description['content'])

        for item in items:
            total_count += 1
            if item['is_processed']:
                processed_count += 1
            all_items.append({
                'task_key': key,
                'task_summary': summary,
                'index': item['index'],
                'text': item['text'],
                'owners': item['owners'],
                'is_processed': item['is_processed'],
            })

    # 按任务编号分组
    grouped = {}
    for item in all_items:
        key = item['task_key']
        if key not in grouped:
            grouped[key] = {
                'summary': item['task_summary'],
                'items': [],
            }
        grouped[key]['items'].append(item)

    return {
        'total': total_count,
        'processed': processed_count,
        'unprocessed': total_count - processed_count,
        'grouped': grouped,
    }
