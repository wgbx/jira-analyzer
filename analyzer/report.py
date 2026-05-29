"""
报告生成模块

将分析结果渲染为 HTML 或 Markdown 格式的可视化报告。
"""

from datetime import datetime

from analyzer.config import OUTPUT_DIR
from analyzer.owners import OWNERS, OWNER_DISPLAY_NAMES


# ============================================================
# Owner 相关的样式和筛选配置（集中管理，便于维护）
# ============================================================

# Owner 标签颜色：背景色 + 文字色
OWNER_COLORS = {
    'jayce': ('#dbeafe', '#1e40af'),
    'zhiyong': ('#dcfce7', '#166534'),
    'tiancheng': ('#f3e8ff', '#6b21a8'),
    'jun': ('#fef3c7', '#92400e'),
    'jiaqi': ('#fee2e2', '#991b1b'),
    'lory': ('#e0f2fe', '#0c4a6e'),
    'tianye': ('#fce7f3', '#9d174d'),
    'fengxia': ('#fef9c3', '#854d0e'),
    'fred': ('#e2e8f0', '#334155'),
    'joey': ('#d1fae5', '#065f46'),
    'chenglim': ('#ede9fe', '#5b21b6'),
    'zhengzhu': ('#ffedd5', '#9a3412'),
}


def _build_owner_css():
    """生成 owner 标签和筛选按钮的 CSS 样式"""
    css = ""
    # owner 标签样式
    for owner, (bg, color) in OWNER_COLORS.items():
        css += f"        .owner-{owner} {{ background: {bg}; color: {color}; }}\n"
    # 筛选按钮激活样式
    for owner, (_, color) in OWNER_COLORS.items():
        css += f"        .filter-btn.active-{owner} {{ background: {color}; border-color: {color}; color: white; }}\n"
    css += "        .filter-btn.active-unassigned {{ background: #6b7280; border-color: #6b7280; color: white; }}\n"
    return css


def _build_filter_buttons():
    """生成筛选栏按钮 HTML"""
    buttons = [
        '<button class="filter-btn active" data-filter="all" '
        'onclick="filterItems(\'all\')">全部<span class="filter-count" id="count-all"></span></button>',
    ]
    for owner in OWNERS:
        display = OWNER_DISPLAY_NAMES[owner]
        buttons.append(
            f'<button class="filter-btn" data-filter="{owner}" '
            f'onclick="filterItems(\'{owner}\')">{display}'
            f'<span class="filter-count" id="count-{owner}"></span></button>'
        )
    buttons.append(
        '<button class="filter-btn" data-filter="unassigned" '
        'onclick="filterItems(\'unassigned\')">未分配'
        '<span class="filter-count" id="count-unassigned"></span></button>'
    )
    return '\n            '.join(buttons)


def _build_filter_js():
    """生成筛选功能的 JavaScript 代码"""
    # 动态生成 owner 列表（从 OWNERS 字典读取，避免硬编码）
    owner_keys = list(OWNERS.keys())
    counts_init = ', '.join([f'{k}: 0' for k in ['all'] + owner_keys + ['unassigned']])
    counts_checks = '\n'.join([
        f"                    if (ownerList.includes('{k}')) counts.{k}++;"
        for k in owner_keys
    ])
    remove_classes = ', '.join([f"'active-{k}'" for k in owner_keys] + ["'active-unassigned'", "'active'"])

    return """
    <script>
        function updateCounts() {
            const allItems = document.querySelectorAll('li[data-owners]');
            const counts = { """ + counts_init + """ };
            allItems.forEach(li => {
                counts.all++;
                const owners = li.getAttribute('data-owners');
                if (!owners) {
                    counts.unassigned++;
                } else {
                    const ownerList = owners.split(',');
""" + counts_checks + """
                }
            });
            for (const [key, count] of Object.entries(counts)) {
                const el = document.getElementById('count-' + key);
                if (el) el.textContent = count;
            }
        }

        function filterItems(filter) {
            document.querySelectorAll('.filter-btn').forEach(btn => {
                btn.classList.remove(""" + remove_classes + """);
            });
            const activeBtn = document.querySelector(`.filter-btn[data-filter="${filter}"]`);
            if (activeBtn) {
                if (filter === 'all') {
                    activeBtn.classList.add('active');
                } else {
                    activeBtn.classList.add('active-' + filter);
                }
            }

            const allItems = document.querySelectorAll('li[data-owners]');
            allItems.forEach(li => {
                const owners = li.getAttribute('data-owners');
                let show = false;
                if (filter === 'all') {
                    show = true;
                } else if (filter === 'unassigned') {
                    show = !owners;
                } else {
                    show = owners && owners.split(',').includes(filter);
                }
                li.style.display = show ? '' : 'none';
            });

            document.querySelectorAll('.task-section').forEach(section => {
                const visibleItems = section.querySelectorAll('li[data-owners]:not([style*="display: none"])');
                section.style.display = visibleItems.length > 0 ? '' : 'none';
            });
        }

        updateCounts();
    </script>"""


def generate_html_report(analysis, base_url):
    """
    生成 HTML 格式的分析报告

    报告包含统计概览、人员筛选栏和按任务分组的未处理条目列表。
    筛选功能通过前端 JavaScript 实现，无需后端支持。

    Args:
        analysis: analyze_issues() 返回的分析结果
        base_url: Jira 实例地址（如 https://xxx.atlassian.net）

    Returns:
        str: 完整的 HTML 文档字符串
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    owner_css = _build_owner_css()
    filter_buttons = _build_filter_buttons()
    filter_js = _build_filter_js()

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
        .task-key {{ font-size: 18px; font-weight: 600; }}
        .task-key a {{ color: #667eea; text-decoration: none; }}
        .task-key a:hover {{ text-decoration: underline; }}
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
        .item-owners {{ margin-top: 8px; display: flex; gap: 6px; flex-wrap: wrap; }}
        .owner-tag {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 500;
        }}
{owner_css}
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
        .filter-label {{ font-weight: 600; color: #374151; margin-right: 8px; }}
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
        .filter-btn:hover {{ border-color: #667eea; color: #667eea; }}
        .filter-btn.active {{ background: #667eea; color: white; border-color: #667eea; }}
        .filter-count {{
            font-size: 11px;
            background: rgba(255,255,255,0.3);
            padding: 1px 6px;
            border-radius: 10px;
            margin-left: 4px;
        }}
        .empty-state {{ text-align: center; padding: 60px 20px; color: #9ca3af; }}
        .empty-icon {{ font-size: 64px; margin-bottom: 20px; }}
        .footer {{ text-align: center; color: #9ca3af; margin-top: 40px; font-size: 14px; }}
        .timestamp {{ margin-top: 10px; }}
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
            {filter_buttons}
        </div>
"""

    # 渲染各任务的未处理条目
    if analysis['grouped']:
        for task_key in sorted(analysis['grouped'].keys(), reverse=True):
            task = analysis['grouped'][task_key]
            unprocessed_items = [item for item in task['items'] if not item.get('is_processed')]
            if not unprocessed_items:
                continue

            summary_display = task['summary'][:50] + ('...' if len(task['summary']) > 50 else '')
            html += f"""
        <div class="task-section">
            <div class="task-header">
                <span class="task-key"><a href="{base_url}/browse/{task_key}" target="_blank">{task_key}</a></span>
                <span class="task-summary">{summary_display}</span>
                <span class="task-count">{len(unprocessed_items)} 个未处理</span>
            </div>
            <ul class="item-list">"""

            for item in unprocessed_items:
                owner_tags = ''.join(
                    f'<span class="owner-tag owner-{o}">{OWNER_DISPLAY_NAMES.get(o, o)}</span>'
                    for o in item['owners']
                )
                owners_attr = ','.join(item['owners']) if item['owners'] else ''

                # HTML 转义，防止文本中的特殊字符破坏页面结构
                safe_text = item['text'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

                html += f"""
                <li class="item" data-owners="{owners_attr}">
                    <span class="item-index">{item['index']}</span>
                    <span class="item-content">
                        <span class="item-text">{safe_text}</span>
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
{filter_js}
</body>
</html>"""

    return html


def generate_markdown_report(analysis):
    """
    生成 Markdown 格式的分析报告

    Args:
        analysis: analyze_issues() 返回的分析结果

    Returns:
        str: Markdown 文档字符串
    """
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
                owners_str = ' '.join(f'`{OWNER_DISPLAY_NAMES.get(o, o)}`' for o in item['owners'])
                md += f"- **第 {item['index']} 点**: {item['text']}"
                if owners_str:
                    md += f"  {owners_str}"
                md += "\n"
            md += "\n"
    else:
        md += "🎉 太棒了！没有未处理的项目。\n"

    md += """---

*Generated by Jira Analyzer*"""

    return md
