#!/usr/bin/env python3
"""
Jira 任务分析器
定期分析 KAT-10938 子任务，统计未处理的项目
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path
import requests
from requests.auth import HTTPBasicAuth

# 加载配置
CONFIG_PATH = Path(__file__).parent / "config.json"
OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# 关注的 owner 列表（支持多种匹配方式）
OWNERS = {
    'jayce': ['Jayce', 'jayce', '@Jayce', '@jayce chen'],
    'zhiyong': ['Zhiyong', 'zhiyong', 'Song', 'song', '@Zhiyong', '@zhiyong', '@zhiyong song'],
    'tiancheng': ['Tiancheng', 'tiancheng', '@Tiancheng', '@tiancheng', 'Tiancheng Tang', '@Tiancheng Tang'],
    'jun': ['Jun', 'jun', '@Jun', '@jun', 'Jun Li', '@Jun Li'],
    'jiaqi': ['Jiaqi', 'jiaqi', '@Jiaqi', '@jiaqi', 'Jiaqi Yu', '@Jiaqi Yu'],
    'lory': ['Lory', 'lory', '@Lory', '@lory', 'Lory Jiang', '@Lory Jiang'],
    'tianye': ['Tian Ye', 'tian ye', '@Tian Ye'],
    'fengxia': ['Feng Xia', 'feng xia', '@Feng Xia']
}


def load_config():
    """加载配置文件"""
    if not CONFIG_PATH.exists():
        print(f"配置文件不存在: {CONFIG_PATH}")
        print("请复制 config.example.json 并填写你的 Jira API Token")
        sys.exit(1)

    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def extract_text_from_adf(content):
    """从 Atlassian Document Format 中提取纯文本"""
    texts = []

    if isinstance(content, dict):
        content_type = content.get('type', '')
        if content_type == 'text':
            text = content.get('text', '')
            marks = content.get('marks', [])
            is_strikethrough = any(m.get('type') == 'strike' for m in marks)
            return [(text, is_strikethrough)]
        elif content_type == 'mention':
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
    """从 ADF 中提取所有 @mention 的文本"""
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


def detect_owner(text):
    """检测文本中提到的 owner"""
    detected = []
    lower_text = text.lower()

    for owner_name, keywords in OWNERS.items():
        for keyword in keywords:
            if keyword.lower() in lower_text:
                if owner_name not in detected:
                    detected.append(owner_name)
                break

    return detected


def parse_list_items(content, index=1):
    """解析列表项，返回 (items, next_index)"""
    items = []

    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict):
                item_type = item.get('type', '')

                if item_type == 'listItem':
                    texts = extract_text_from_adf(item.get('content', []))
                    full_text = ' '.join([t[0] for t in texts]).strip()
                    is_strikethrough = any(t[1] for t in texts)

                    if not full_text:
                        continue

                    lower_text = full_text.lower()
                    # 匹配各种 done/backlog/moved 标记模式：
                    # (done), ( done ), （done）, （ done ）, (Done), 等
                    is_done = bool(re.search(r'[\(（]\s*done\s*[\)）]|^done[\)）\s]', lower_text))
                    is_backlog = bool(re.search(r'[\(（]\s*backlog\s*[\)）]', lower_text))
                    is_moved = bool(re.search(r'[\(（]\s*moved\s*[\)）]', lower_text))

                    # 检测 owner：同时从文本和 @mention 节点匹配
                    owners = detect_owner(full_text)
                    if not owners:
                        mention_texts = extract_mentions_from_adf(item.get('content', []))
                        for mention_text in mention_texts:
                            owners.extend(detect_owner(mention_text))
                        owners = list(dict.fromkeys(owners))

                    items.append({
                        'index': index,
                        'text': full_text,
                        'is_done': is_done,
                        'is_backlog': is_backlog,
                        'is_moved': is_moved,
                        'is_strikethrough': is_strikethrough,
                        'is_processed': is_done or is_backlog or is_moved or is_strikethrough,
                        'owners': owners
                    })
                    index += 1

                elif 'content' in item:
                    sub_items, new_index = parse_list_items(item['content'], index)
                    items.extend(sub_items)
                    index = new_index

    return items, index


def get_subtasks(config):
    """获取子任务列表"""
    url = f"{config['jira']['base_url']}/rest/api/3/search/jql"
    auth = HTTPBasicAuth(config['jira']['email'], config['jira']['api_token'])

    # 使用 currentUser() 而不是硬编码的 assignee 名称
    jql = f"parent = {config['parent_issue']} AND assignee = currentUser()"

    response = requests.post(
        url,
        auth=auth,
        headers={"Content-Type": "application/json"},
        json={"jql": jql, "fields": ["summary", "description", "status", "key"], "maxResults": 100},
        timeout=30
    )

    if response.status_code != 200:
        print(f"获取子任务失败: {response.status_code} - {response.text}")
        return []

    return response.json().get('issues', [])


def get_issue_description(config, issue_key):
    """获取单个任务的描述"""
    url = f"{config['jira']['base_url']}/rest/api/3/issue/{issue_key}"
    auth = HTTPBasicAuth(config['jira']['email'], config['jira']['api_token'])

    response = requests.get(
        url,
        auth=auth,
        headers={"Content-Type": "application/json"},
        params={"fields": "description,summary,status"},
        timeout=30
    )

    if response.status_code != 200:
        print(f"获取任务 {issue_key} 失败: {response.status_code}")
        return None

    data = response.json()
    return {
        'key': data.get('key'),
        'summary': data.get('fields', {}).get('summary', ''),
        'status': data.get('fields', {}).get('status', {}).get('name', ''),
        'description': data.get('fields', {}).get('description', {})
    }


def analyze_issues(config):
    """分析所有子任务"""
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

        items, _ = parse_list_items(description['content'])

        for item in items:
            total_count += 1
            if item['is_processed']:
                processed_count += 1
            # 显示所有项目，带 owner 和处理状态信息
            all_items.append({
                'task_key': key,
                'task_summary': summary,
                'index': item['index'],
                'text': item['text'],
                'owners': item['owners'],
                'is_processed': item['is_processed'],
                'is_done': item['is_done'],
                'is_backlog': item['is_backlog'],
                'is_moved': item['is_moved']
            })

    # 按任务分组
    grouped = {}
    for item in all_items:
        key = item['task_key']
        if key not in grouped:
            grouped[key] = {
                'summary': item['task_summary'],
                'items': []
            }
        grouped[key]['items'].append(item)

    return {
        'total': total_count,
        'processed': processed_count,
        'unprocessed': total_count - processed_count,
        'grouped': grouped
    }


def generate_html_report(analysis):
    """生成 HTML 报告"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Jira 任务分析报告</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #f5f5f5;
            padding: 20px;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 12px;
            margin-bottom: 30px;
        }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 20px;
            margin-bottom: 30px;
        }}
        .stat-card {{
            background: white;
            padding: 25px;
            border-radius: 12px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
            text-align: center;
        }}
        .stat-number {{ font-size: 36px; font-weight: bold; margin: 10px 0; }}
        .stat-label {{ color: #666; font-size: 14px; }}
        .total {{ color: #667eea; }}
        .processed {{ color: #10b981; }}
        .unprocessed {{ color: #ef4444; }}

        .task-section {{
            background: white;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        }}
        .task-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-bottom: 15px;
            border-bottom: 1px solid #eee;
            margin-bottom: 15px;
        }}
        .task-key {{
            font-size: 18px;
            font-weight: 600;
        }}
        .task-key a {{
            color: #667eea;
            text-decoration: none;
        }}
        .task-key a:hover {{
            text-decoration: underline;
        }}
        .task-count {{
            background: #fef3c7;
            color: #92400e;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 14px;
        }}
        .item-list {{ list-style: none; }}
        .item {{
            padding: 12px 15px;
            border-left: 3px solid #e5e7eb;
            margin-bottom: 10px;
            background: #f9fafb;
            border-radius: 0 8px 8px 0;
        }}
        .item.processed {{
            opacity: 0.5;
            text-decoration: line-through;
            background: #f3f4f6;
        }}
        .status-tag {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 10px;
            margin-left: 8px;
            background: #e5e7eb;
            color: #6b7280;
        }}
        .status-done {{ background: #d1fae5; color: #065f46; }}
        .status-backlog {{ background: #fef3c7; color: #92400e; }}
        .status-moved {{ background: #e0e7ff; color: #3730a3; }}
        .item-index {{
            display: inline-block;
            background: #667eea;
            color: white;
            width: 24px;
            height: 24px;
            border-radius: 50%;
            text-align: center;
            line-height: 24px;
            font-size: 12px;
            margin-right: 10px;
        }}
        .item-content {{ display: inline-block; vertical-align: top; max-width: calc(100% - 40px); }}
        .item-text {{
            display: -webkit-box;
            -webkit-line-clamp: 3;
            -webkit-box-orient: vertical;
            overflow: hidden;
            line-height: 1.5;
            max-height: 4.5em;
        }}
        .item-owners {{
            margin-top: 8px;
            display: flex;
            gap: 6px;
            flex-wrap: wrap;
        }}
        .owner-tag {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 500;
        }}
        .owner-jayce {{ background: #dbeafe; color: #1e40af; }}
        .owner-zhiyong {{ background: #dcfce7; color: #166534; }}
        .owner-tiancheng {{ background: #f3e8ff; color: #6b21a8; }}
        .owner-jun {{ background: #fef3c7; color: #92400e; }}
        .owner-jiaqi {{ background: #fee2e2; color: #991b1b; }}
        .owner-lory {{ background: #e0f2fe; color: #0c4a6e; }}
        .owner-tianye {{ background: #fce7f3; color: #9d174d; }}
        .owner-fengxia {{ background: #fef9c3; color: #854d0e; }}

        .empty-state {{
            text-align: center;
            padding: 60px 20px;
            color: #9ca3af;
        }}
        .empty-icon {{ font-size: 64px; margin-bottom: 20px; }}

        .footer {{
            text-align: center;
            color: #9ca3af;
            margin-top: 40px;
            font-size: 14px;
        }}
        .timestamp {{ margin-top: 10px; }}

        .filter-bar {{
            background: white;
            padding: 20px;
            border-radius: 12px;
            margin-bottom: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
            display: flex;
            align-items: center;
            gap: 12px;
            flex-wrap: wrap;
        }}
        .filter-label {{
            font-weight: 600;
            color: #374151;
            margin-right: 8px;
        }}
        .filter-btn {{
            padding: 6px 16px;
            border-radius: 20px;
            border: 2px solid #e5e7eb;
            background: white;
            color: #374151;
            font-size: 13px;
            cursor: pointer;
            transition: all 0.2s;
        }}
        .filter-btn:hover {{
            border-color: #667eea;
            color: #667eea;
        }}
        .filter-btn.active {{
            background: #667eea;
            color: white;
            border-color: #667eea;
        }}
        .filter-btn.active-jayce {{ background: #1e40af; border-color: #1e40af; color: white; }}
        .filter-btn.active-zhiyong {{ background: #166534; border-color: #166534; color: white; }}
        .filter-btn.active-tiancheng {{ background: #6b21a8; border-color: #6b21a8; color: white; }}
        .filter-btn.active-jun {{ background: #92400e; border-color: #92400e; color: white; }}
        .filter-btn.active-jiaqi {{ background: #991b1b; border-color: #991b1b; color: white; }}
        .filter-btn.active-unassigned {{ background: #6b7280; border-color: #6b7280; color: white; }}
        .filter-btn.active-lory {{ background: #0c4a6e; border-color: #0c4a6e; color: white; }}
        .filter-btn.active-tianye {{ background: #9d174d; border-color: #9d174d; color: white; }}
        .filter-btn.active-fengxia {{ background: #854d0e; border-color: #854d0e; color: white; }}
        .filter-count {{
            font-size: 11px;
            background: rgba(255,255,255,0.3);
            padding: 1px 6px;
            border-radius: 10px;
            margin-left: 4px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Jira 任务分析报告</h1>
            <p>KAT-10938 所有项目概览</p>
        </div>

        <div class="stats">
            <div class="stat-card">
                <div class="stat-label">总条目数</div>
                <div class="stat-number total">{analysis['total']}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">已处理</div>
                <div class="stat-number processed">{analysis['processed']}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">未处理</div>
                <div class="stat-number unprocessed">{analysis['unprocessed']}</div>
            </div>
        </div>

        <div class="filter-bar">
            <span class="filter-label">筛选人员:</span>
            <button class="filter-btn active" data-filter="all" onclick="filterItems('all')">全部<span class="filter-count" id="count-all"></span></button>
            <button class="filter-btn" data-filter="jayce" onclick="filterItems('jayce')">Jayce<span class="filter-count" id="count-jayce"></span></button>
            <button class="filter-btn" data-filter="zhiyong" onclick="filterItems('zhiyong')">Zhiyong<span class="filter-count" id="count-zhiyong"></span></button>
            <button class="filter-btn" data-filter="tiancheng" onclick="filterItems('tiancheng')">Tiancheng<span class="filter-count" id="count-tiancheng"></span></button>
            <button class="filter-btn" data-filter="jun" onclick="filterItems('jun')">Jun<span class="filter-count" id="count-jun"></span></button>
            <button class="filter-btn" data-filter="jiaqi" onclick="filterItems('jiaqi')">Jiaqi<span class="filter-count" id="count-jiaqi"></span></button>
            <button class="filter-btn" data-filter="lory" onclick="filterItems('lory')">Lory<span class="filter-count" id="count-lory"></span></button>
            <button class="filter-btn" data-filter="tianye" onclick="filterItems('tianye')">Tian Ye<span class="filter-count" id="count-tianye"></span></button>
            <button class="filter-btn" data-filter="fengxia" onclick="filterItems('fengxia')">Feng Xia<span class="filter-count" id="count-fengxia"></span></button>
            <button class="filter-btn" data-filter="unassigned" onclick="filterItems('unassigned')">未分配<span class="filter-count" id="count-unassigned"></span></button>
        </div>
"""

    if analysis['grouped']:
        for task_key in sorted(analysis['grouped'].keys(), reverse=True):
            task = analysis['grouped'][task_key]
            unprocessed_items = [item for item in task['items'] if not item.get('is_processed')]
            if not unprocessed_items:
                continue
            html += f"""
        <div class="task-section">
            <div class="task-header">
                <span class="task-key"><a href="https://pearshop.atlassian.net/browse/{task_key}" target="_blank">{task_key}</a></span>
                <span class="task-summary">{task['summary'][:50]}...</span>
                <span class="task-count">{len(unprocessed_items)} 个未处理</span>
            </div>
            <ul class="item-list">"""
            for item in unprocessed_items:
                # 生成 owner 标签
                owner_tags = ''.join(f'<span class="owner-tag owner-{owner}">{owner.capitalize()}</span>' for owner in item['owners'])
                owners_attr = ','.join(item['owners']) if item['owners'] else ''

                html += f"""
                <li class="item" data-owners="{owners_attr}">
                    <span class="item-index">{item['index']}</span>
                    <span class="item-content">
                        <span class="item-text">{item['text']}</span>
                        <div class="item-owners">{owner_tags}</div>
                    </span>
                </li>"""
            html += """
            </ul>
        </div>"""
    else:
        html += """
        <div class="empty-state">
            <div class="empty-icon">🎉</div>
            <h3>太棒了！</h3>
            <p>没有未处理的项目</p>
        </div>"""

    html += f"""
        <div class="footer">
            <p>Generated by Jira Analyzer</p>
            <p class="timestamp">更新时间: {now}</p>
        </div>
    </div>
    <script>
        // 初始化计数
        function updateCounts() {{
            const allItems = document.querySelectorAll('li[data-owners]');
            const counts = {{ all: 0, jayce: 0, zhiyong: 0, tiancheng: 0, jun: 0, jiaqi: 0, lory: 0, tianye: 0, fengxia: 0, unassigned: 0 }};
            allItems.forEach(li => {{
                counts.all++;
                const owners = li.getAttribute('data-owners');
                if (!owners) {{
                    counts.unassigned++;
                }} else {{
                    const ownerList = owners.split(',');
                    if (ownerList.includes('jayce')) counts.jayce++;
                    if (ownerList.includes('zhiyong')) counts.zhiyong++;
                    if (ownerList.includes('tiancheng')) counts.tiancheng++;
                    if (ownerList.includes('jun')) counts.jun++;
                    if (ownerList.includes('jiaqi')) counts.jiaqi++;
                    if (ownerList.includes('lory')) counts.lory++;
                    if (ownerList.includes('tianye')) counts.tianye++;
                    if (ownerList.includes('fengxia')) counts.fengxia++;
                }}
            }});
            for (const [key, count] of Object.entries(counts)) {{
                const el = document.getElementById('count-' + key);
                if (el) el.textContent = count;
            }}
        }}

        function filterItems(filter) {{
            // 更新按钮状态
            document.querySelectorAll('.filter-btn').forEach(btn => {{
                btn.classList.remove('active', 'active-jayce', 'active-zhiyong', 'active-tiancheng', 'active-jun', 'active-jiaqi', 'active-lory', 'active-tianye', 'active-fengxia', 'active-unassigned');
            }});
            const activeBtn = document.querySelector(`.filter-btn[data-filter="${{filter}}"]`);
            if (activeBtn) {{
                if (filter === 'all') {{
                    activeBtn.classList.add('active');
                }} else {{
                    activeBtn.classList.add('active-' + filter);
                }}
            }}

            // 筛选条目
            const allItems = document.querySelectorAll('li[data-owners]');
            allItems.forEach(li => {{
                const owners = li.getAttribute('data-owners');
                let show = false;
                if (filter === 'all') {{
                    show = true;
                }} else if (filter === 'unassigned') {{
                    show = !owners;
                }} else {{
                    show = owners && owners.split(',').includes(filter);
                }}
                li.style.display = show ? '' : 'none';
            }});

            // 隐藏没有可见条目的任务区块
            document.querySelectorAll('.task-section').forEach(section => {{
                const visibleItems = section.querySelectorAll('li[data-owners]:not([style*="display: none"])');
                section.style.display = visibleItems.length > 0 ? '' : 'none';
            }});
        }}

        updateCounts();
    </script>
</body>
</html>"""

    return html


def generate_markdown_report(analysis):
    """生成 Markdown 报告"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    md = f"""# Jira 任务分析报告

**更新时间**: {now}
**父任务**: KAT-10938

## 统计概览

| 指标 | 数量 |
|------|------|
| **总条目数** | {analysis['total']} |
| **已处理** | {analysis['processed']} |
| **未处理** | {analysis['unprocessed']} |

---

## 未处理项目

"""

    if analysis['grouped']:
        for task_key in sorted(analysis['grouped'].keys(), reverse=True):
            task = analysis['grouped'][task_key]
            unprocessed_items = [item for item in task['items'] if not item.get('is_processed')]
            if not unprocessed_items:
                continue
            md += f"### [{task_key}] {task['summary']}\n\n"
            for item in unprocessed_items:
                md += f"- **第 {item['index']} 点**: {item['text']}\n"
            md += "\n"
    else:
        md += "🎉 太棒了！没有未处理的项目。\n"

    md += f"""
---

*Generated by Jira Analyzer*
"""
    return md


def main():
    """主函数"""
    print("=" * 50)
    print("Jira 任务分析器")
    print("=" * 50)

    # 加载配置
    config = load_config()

    # 检查 API Token
    if config['jira']['api_token'] == "YOUR_JIRA_API_TOKEN_HERE":
        print("\n⚠️ 请先在 config.json 中填写你的 Jira API Token")
        print("API Token 获取地址: https://id.atlassian.net/manage-profile/security/api-tokens")
        sys.exit(1)

    # 分析任务
    analysis = analyze_issues(config)

    # 打印统计
    print(f"\n统计结果:")
    print(f"  总条目数: {analysis['total']}")
    print(f"  已处理: {analysis['processed']}")
    print(f"  未处理: {analysis['unprocessed']}")

    # 生成报告
    output_format = config.get('output', {}).get('format', 'html')

    if output_format == 'markdown':
        report = generate_markdown_report(analysis)
        output_path = OUTPUT_DIR / "jira-report.md"
    else:
        report = generate_html_report(analysis)
        output_path = OUTPUT_DIR / "jira-report.html"

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"\n✅ 报告已生成: {output_path}")

    # 打开报告（可选）
    import subprocess
    if sys.platform == 'darwin':  # macOS
        subprocess.run(['open', str(output_path)])
    elif sys.platform == 'win32':
        subprocess.run(['start', str(output_path)], shell=True)
    elif sys.platform.startswith('linux'):
        subprocess.run(['xdg-open', str(output_path)])


if __name__ == '__main__':
    main()
