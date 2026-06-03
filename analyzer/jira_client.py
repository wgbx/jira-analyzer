"""
Jira API 客户端模块

封装与 Jira REST API 的交互逻辑，
包括子任务查询、任务详情获取和批量分析。
"""

import time

from analyzer.jira_http import build_jira_session, jira_request
from analyzer.parser import parse_list_items
from analyzer.scheduled import get_scheduled_lookup

# 连续请求间隔，减轻 macOS LibreSSL 下偶发 SSLEOFError
_ISSUE_FETCH_DELAY_SEC = 0.35

# 「未处理 / 已排期」口径：仅统计这些 Jira 状态的子任务（如 QA Staging 不计入）
DEFAULT_ACTIVE_STATUSES = ('未处理', '进行中')


def get_active_statuses(config):
    statuses = config.get('filters', {}).get('active_statuses')
    if statuses is None:
        return list(DEFAULT_ACTIVE_STATUSES)
    return list(statuses)


def _subtasks_jql(config):
    """
    子任务 JQL。

    默认 parent 下全部子任务（统计含已转交领导的条目）；
    filters.subtasks_scope = "mine" 时仅当前用户经办。
    """
    jql = f"parent = {config['parent_issue']}"
    scope = config.get('filters', {}).get('subtasks_scope', 'all')
    if scope == 'mine':
        jql += ' AND assignee = currentUser()'
    return jql


def get_subtasks(config, session=None):
    """
    获取父任务下的子任务列表（支持分页）。

    Args:
        config: 配置字典，需包含 jira、parent_issue；可选 filters.subtasks_scope

    Returns:
        list[dict]: 子任务列表，每个元素包含 key、fields 等信息
    """
    session = session or build_jira_session(config)
    url = f"{config['jira']['base_url']}/rest/api/3/search/jql"
    jql = _subtasks_jql(config)

    issues = []
    next_page_token = None

    while True:
        body = {
            'jql': jql,
            'fields': ['summary', 'description', 'status', 'key'],
            'maxResults': 100,
        }
        if next_page_token:
            body['nextPageToken'] = next_page_token

        try:
            response = jira_request(session, 'POST', url, json=body)
        except Exception as exc:
            print(f'获取子任务失败: {exc}')
            break

        if response.status_code != 200:
            print(f'获取子任务失败: {response.status_code} - {response.text}')
            break

        data = response.json()
        issues.extend(data.get('issues', []))

        if data.get('isLast', True):
            break
        next_page_token = data.get('nextPageToken')
        if not next_page_token:
            break

    return issues


def get_issue_description(config, issue_key, session=None):
    """
    获取单个任务的详细信息

    Args:
        config: 配置字典
        issue_key: 任务编号（如 KAT-11330）

    Returns:
        dict | None: 任务信息，包含 key、summary、status、description；
                     获取失败时返回 None
    """
    session = session or build_jira_session(config)
    url = f"{config['jira']['base_url']}/rest/api/3/issue/{issue_key}"

    try:
        response = jira_request(
            session,
            'GET',
            url,
            params={'fields': 'description,summary,status'},
        )
    except Exception as exc:
        print(f'获取任务 {issue_key} 失败: {exc}')
        return None

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
    scope = config.get('filters', {}).get('subtasks_scope', 'all')
    scope_label = '全部子任务' if scope != 'mine' else '分配给当前用户的子任务'
    print(f"正在分析 {config['parent_issue']} 的{scope_label}...")

    session = build_jira_session(config)
    subtasks = get_subtasks(config, session=session)
    print(f"找到 {len(subtasks)} 个子任务（统计与列表均基于此范围）")

    all_items = []
    total_count = 0
    processed_count = 0
    scheduled_lookup = get_scheduled_lookup(config)
    fetch_failures = 0

    for i, issue in enumerate(subtasks):
        key = issue.get('key')
        summary = issue.get('fields', {}).get('summary', '')

        if i > 0:
            time.sleep(_ISSUE_FETCH_DELAY_SEC)

        issue_data = get_issue_description(config, key, session=session)
        if not issue_data:
            fetch_failures += 1
            continue
        issue_status = issue_data.get('status') or (
            issue.get('fields', {}).get('status', {}).get('name', '')
        )
        if not issue_data['description']:
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
            release_label = scheduled_lookup.get((key, item['index']))
            all_items.append({
                'task_key': key,
                'task_summary': summary,
                'issue_status': issue_status,
                'index': item['index'],
                'text': item['text'],
                'owners': item['owners'],
                'is_processed': item['is_processed'],
                'is_done': item.get('is_done', False),
                'is_backlog': item.get('is_backlog', False),
                'is_moved': item.get('is_moved', False),
                'is_strikethrough': item.get('is_strikethrough', False),
                'is_scheduled': release_label is not None,
                'scheduled_release': release_label,
            })

    # 按任务编号分组
    grouped = {}
    for item in all_items:
        key = item['task_key']
        if key not in grouped:
            grouped[key] = {
                'summary': item['task_summary'],
                'issue_status': item['issue_status'],
                'items': [],
            }
        grouped[key]['items'].append(item)

    if fetch_failures:
        print(f"警告: {fetch_failures} 个子任务因网络错误未拉取，将使用其余任务生成报告")

    active_statuses = get_active_statuses(config)
    # 总条目数 / 已处理：全部子任务；未处理 / 已排期：仅活跃 Jira 状态
    unprocessed = sum(
        1 for item in all_items
        if not item['is_processed'] and item['issue_status'] in active_statuses
    )
    scheduled_unprocessed = sum(
        1 for item in all_items
        if not item['is_processed'] and item.get('is_scheduled')
        and item['issue_status'] in active_statuses
    )
    scheduled_processed = sum(
        1 for item in all_items
        if item['is_processed'] and item.get('is_scheduled')
    )

    return {
        'total': total_count,
        'processed': processed_count,
        'unprocessed': unprocessed,
        'scheduled_unprocessed': scheduled_unprocessed,
        'scheduled_processed': scheduled_processed,
        'active_statuses': active_statuses,
        'grouped': grouped,
    }
