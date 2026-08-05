"""Meeting / release-week stats block for the Daily report."""

from analyzer.report.common import _escape_html


def _escape_attr(text):
    return _escape_html(text).replace('"', '&quot;')


def _build_meeting_report_html(meeting, base_url):
    """统计页顶部：发布周排期进度三列 + 按人表。"""
    if not meeting:
        return ''

    release = _escape_html(meeting.get('release_label') or '当前发布周')
    week_start = meeting.get('week_start') or meeting.get('previous_date')
    week_end = meeting.get('week_end') or meeting.get('release_date')
    if meeting.get('has_diff'):
        added_value = f"+{meeting['unique_added']}"
        range_parts = []
        if week_start and week_end:
            range_parts.append(f"发布周 {week_start} → {week_end}")
        range_parts.append(
            f"快照 {meeting.get('baseline_date')} → {meeting.get('current_date')}"
        )
        range_parts.append(
            f"已处理 {meeting.get('baseline_count')} → {meeting.get('current_count')}"
        )
        range_note = '；'.join(range_parts)
    else:
        added_value = '—'
        if week_start:
            range_note = (
                f"发布周自 {week_start} 起；尚无周起点快照，净增暂不可算"
            )
        else:
            range_note = '尚无上一发布周，净增暂不可算'

    if meeting.get('previous_label'):
        leftover_note = (
            f"上一发布周未清 {meeting.get('leftover_previous', 0)} + "
            f"当前发布周未完成 {meeting.get('leftover_current', 0)}"
        )
    else:
        leftover_note = '当前发布周仍未处理的排期条目'

    promise_rate = ''
    if meeting.get('promised'):
        rate = round(100 * meeting['done_promised'] / meeting['promised'])
        promise_rate = f"已完成 {meeting['done_promised']}/{meeting['promised']}（{rate}%）"

    owner_rows = []
    detail_blocks = []
    for row in meeting.get('owners') or []:
        owner = row['owner']
        display = _escape_html(row['display'])
        rate = '—' if row.get('promise_rate') is None else f"{row['promise_rate']}%"
        owner_rows.append(
            f'<tr class="meeting-owner-row" data-owner="{owner}" '
            f'onclick="toggleMeetingOwner(\'{owner}\')">'
            f'<td><span class="owner-tag owner-{owner}">{display}</span></td>'
            f'<td>{row["promised"]}</td>'
            f'<td>{row["done_promised"]}</td>'
            f'<td class="num-added">+{row["added"]}</td>'
            f'<td>{row["leftover"]}</td>'
            f'<td>{rate}</td>'
            f'</tr>'
        )

        added_lines = []
        for item in row.get('added_items') or []:
            href = f'{base_url}/browse/{item["key"]}'
            added_lines.append(
                f'<li><a href="{href}" target="_blank">{item["key"]}</a> '
                f'No.{item["index"]} — {_escape_html(item["summary"])}</li>'
            )
        leftover_lines = []
        for item in row.get('leftover_items') or []:
            href = f'{base_url}/browse/{item["key"]}'
            empty_summary = '（无摘要）'
            summary = _escape_html(item["summary"]) or empty_summary
            leftover_lines.append(
                f'<li><a href="{href}" target="_blank">{item["key"]}</a> '
                f'No.{item["index"]} — {summary}</li>'
            )
        if not added_lines and not leftover_lines:
            continue
        added_list = ''.join(added_lines) or '<li class="muted">无</li>'
        leftover_list = ''.join(leftover_lines) or '<li class="muted">无</li>'
        detail_blocks.append(
            f'<div class="meeting-owner-detail" id="meeting-detail-{owner}" hidden>'
            f'<div class="meeting-detail-title">{display}</div>'
            f'<div class="meeting-detail-grid">'
            f'<div><div class="meeting-detail-label">区间净增</div>'
            f'<ul>{added_list}</ul></div>'
            f'<div><div class="meeting-detail-label">未完成排期</div>'
            f'<ul>{leftover_list}</ul></div>'
            f'</div></div>'
        )

    table_body = ''.join(owner_rows) or (
        '<tr><td colspan="6" class="muted">暂无按人数据</td></tr>'
    )
    range_note_html = _escape_html(range_note)
    promise_note = _escape_html(promise_rate) or '当前发布周排期条数'
    leftover_note_html = _escape_html(leftover_note)

    return f"""
        <div class="panel meeting-panel" id="meeting-report">
            <div class="owner-daily-chart-title">{release}</div>
            <div class="owner-daily-chart-subtitle">{range_note_html}</div>
            <div class="meeting-stats">
                <div class="meeting-stat">
                    <div class="meeting-stat-label">排期</div>
                    <div class="meeting-stat-value">{meeting['promised']}</div>
                    <div class="meeting-stat-note">{promise_note}</div>
                </div>
                <div class="meeting-stat meeting-stat-added">
                    <div class="meeting-stat-label">已处理净增</div>
                    <div class="meeting-stat-value">{added_value}</div>
                    <div class="meeting-stat-note">Daily 条目，含 Done / Backlog / Moved</div>
                </div>
                <div class="meeting-stat meeting-stat-leftover">
                    <div class="meeting-stat-label">未完成</div>
                    <div class="meeting-stat-value">{meeting['leftover']}</div>
                    <div class="meeting-stat-note">{leftover_note_html}</div>
                </div>
            </div>
            <table class="meeting-table">
                <thead>
                    <tr>
                        <th>负责人</th>
                        <th>排期</th>
                        <th>已完成</th>
                        <th>净增</th>
                        <th>未完成</th>
                        <th>完成率</th>
                    </tr>
                </thead>
                <tbody>{table_body}</tbody>
            </table>
            <div class="meeting-hint">点击某人展开净增 / 未完成明细</div>
            <div class="meeting-details">{''.join(detail_blocks)}</div>
        </div>
    """
