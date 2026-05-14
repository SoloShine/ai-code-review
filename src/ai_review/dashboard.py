"""HTML dashboard generator - self-contained report viewer."""

import html
import json
import os
import webbrowser
from datetime import datetime
from typing import List, Optional

from ai_review.inbox import InboxManager


_STATUS_COLORS = {
    "PASS": "#4caf50",
    "WARNING": "#ff9800",
    "BLOCKING": "#f44336",
}

_STATUS_ICONS = {
    "PASS": "✅",
    "WARNING": "⚠️",
    "BLOCKING": "❌",
}

_SEVERITY_COLORS = {
    "CRITICAL": "#f44336",
    "ERROR": "#e57373",
    "WARNING": "#ffb74d",
    "INFO": "#64b5f6",
}

_SEVERITY_ICONS = {
    "CRITICAL": "\U0001f6d1",
    "ERROR": "\U0001f534",
    "WARNING": "\U0001f7e1",
    "INFO": "ℹ️",
}


def _css() -> str:
    return """
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace;
    background: #1a1a2e; color: #e0e0e0; padding: 20px;
    max-width: 960px; margin: 0 auto;
}
header { margin-bottom: 24px; }
h1 { font-size: 22px; color: #fff; margin-bottom: 12px; }
.summary-bar {
    display: flex; gap: 16px; align-items: center;
    margin-bottom: 12px; font-size: 13px; color: #aaa;
}
.summary-bar .badge {
    padding: 2px 8px; border-radius: 10px; font-size: 12px; font-weight: 600;
}
.badge-pass { background: #2e7d32; color: #fff; }
.badge-warning { background: #e65100; color: #fff; }
.badge-blocking { background: #b71c1c; color: #fff; }
.badge-unread { background: #1565c0; color: #fff; }
#filter {
    width: 100%; padding: 8px 12px; background: #16213e; border: 1px solid #333;
    border-radius: 6px; color: #e0e0e0; font-size: 14px; outline: none;
}
#filter:focus { border-color: #2196f3; }
.report-card {
    background: #16213e; border-radius: 8px; margin-bottom: 12px;
    border-left: 4px solid #555; cursor: pointer; transition: background 0.15s;
    overflow: hidden;
}
.report-card:hover { background: #1a2744; }
.report-card.status-PASS { border-left-color: #4caf50; }
.report-card.status-WARNING { border-left-color: #ff9800; }
.report-card.status-BLOCKING { border-left-color: #f44336; }
.card-header {
    display: flex; align-items: center; gap: 10px; padding: 12px 16px;
    flex-wrap: wrap;
}
.status-badge {
    font-size: 12px; font-weight: 700; padding: 2px 8px; border-radius: 4px;
    text-transform: uppercase;
}
.status-badge.PASS { background: #2e7d32; }
.status-badge.WARNING { background: #e65100; }
.status-badge.BLOCKING { background: #b71c1c; }
.timestamp { color: #888; font-size: 12px; }
.issue-count { color: #bbb; font-size: 12px; }
.unread-dot {
    width: 8px; height: 8px; border-radius: 50%; background: #2196f3;
    margin-left: auto; flex-shrink: 0;
}
.card-meta { padding: 0 16px 4px; font-size: 12px; color: #777; }
.card-summary { padding: 0 16px 8px; font-size: 13px; color: #bbb; }
.card-issues {
    display: none; border-top: 1px solid #333; padding: 12px 16px;
}
.card-issues.open { display: block; }
.issue {
    margin-bottom: 16px; padding: 10px 12px;
    background: #0f1528; border-radius: 6px;
}
.issue:last-child { margin-bottom: 0; }
.issue-header {
    display: flex; align-items: center; gap: 8px;
    margin-bottom: 6px; font-size: 13px;
}
.issue-header .severity-icon { font-size: 14px; }
.issue-header .rule-id { color: #888; font-size: 12px; }
.issue-header .location { color: #2196f3; font-size: 12px; }
.issue-message { font-size: 13px; margin-bottom: 8px; line-height: 1.5; }
.code-diff { font-family: monospace; font-size: 12px; line-height: 1.6; }
.code-diff pre {
    padding: 6px 10px; margin: 2px 0; border-radius: 4px;
    white-space: pre-wrap; word-break: break-all; overflow-x: auto;
}
.code-diff pre.bad { background: #3a1f1f; color: #ff8a80; }
.code-diff pre.good { background: #1f3a1f; color: #b9f6ca; }
.issue-note { font-size: 12px; color: #888; font-style: italic; margin-top: 6px; }
.highlights { padding: 0 16px 8px; }
.highlights .hl-item { color: #81c784; font-size: 12px; margin-bottom: 2px; }
.no-reports { text-align: center; color: #666; padding: 40px; font-size: 14px; }
"""


def _js() -> str:
    return """
function toggleReport(id) {
    var el = document.getElementById('issues-' + id);
    if (el) el.classList.toggle('open');
}
document.getElementById('filter').addEventListener('input', function(e) {
    var q = e.target.value.toLowerCase();
    var cards = document.querySelectorAll('.report-card');
    cards.forEach(function(card) {
        var text = card.textContent.toLowerCase();
        card.style.display = text.indexOf(q) >= 0 ? '' : 'none';
    });
});
"""


def _render_issue(iss: dict) -> str:
    sev = iss.get("severity", "INFO")
    icon = _SEVERITY_ICONS.get(sev, "?")
    rule = html.escape(iss.get("rule_id") or "")
    loc = ""
    if iss.get("file"):
        loc = html.escape(iss["file"])
        if iss.get("line"):
            loc += f":{iss['line']}"
    msg = html.escape(iss.get("message", ""))

    parts = [
        f'<div class="issue">',
        f'<div class="issue-header">',
        f'<span class="severity-icon">{icon}</span>',
    ]
    if rule:
        parts.append(f'<span class="rule-id">{rule}</span>')
    if loc:
        parts.append(f'<span class="location">{loc}</span>')
    parts.append(f'</div>')
    parts.append(f'<div class="issue-message">{msg}</div>')

    bad = iss.get("bad_code")
    fixed = iss.get("fixed_code")
    if bad or fixed:
        parts.append('<div class="code-diff">')
        if bad:
            parts.append(f'<pre class="bad">- {html.escape(bad)}</pre>')
        if fixed:
            parts.append(f'<pre class="good">+ {html.escape(fixed)}</pre>')
        parts.append('</div>')

    suggestion = iss.get("suggestion")
    if suggestion and not (bad or fixed):
        parts.append(f'<div class="issue-note">{html.escape(suggestion)}</div>')

    parts.append('</div>')
    return "\n".join(parts)


def generate_dashboard(reports_dir: str = ".ai-review/reports") -> str:
    """Generate index.html dashboard from all report JSON files."""
    memory_path = os.path.join(os.path.dirname(reports_dir), "memory.json")
    mgr = InboxManager(memory_path)
    reports = mgr.get_all_reports_data(limit=50)

    # Count summary
    counts = {"PASS": 0, "WARNING": 0, "BLOCKING": 0}
    unread = 0
    for r in reports:
        s = r.get("status", "PASS")
        if s in counts:
            counts[s] += 1
        if not r.get("_inbox", {}).get("read", False):
            unread += 1

    summary_html = ""
    for status, cnt in counts.items():
        if cnt:
            summary_html += f'<span class="badge badge-{status.lower()}">{status}: {cnt}</span> '
    if unread:
        summary_html += f'<span class="badge badge-unread">{unread} unread</span>'

    cards_html = ""
    if not reports:
        cards_html = '<div class="no-reports">No review reports found.</div>'
    else:
        for r in reports:
            rid = r.get("_inbox", {}).get("report_id", "")
            status = r.get("status", "PASS")
            ts = r.get("timestamp", 0)
            time_str = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M") if ts else ""
            tag = html.escape(r.get("tag", ""))
            summary = html.escape(r.get("summary", ""))
            files = r.get("files", [])
            issues = r.get("issues", [])
            highlights = r.get("highlights", [])
            is_read = r.get("_inbox", {}).get("read", False)
            sev_counts = r.get("severity_counts", {})
            issue_total = sum(sev_counts.values())
            commit = r.get("commit", "")

            cards_html += f'<div class="report-card status-{status}" onclick="toggleReport(\'{rid}\')">\n'
            cards_html += f'  <div class="card-header">\n'
            cards_html += f'    <span class="status-badge {status}">{status}</span>\n'
            cards_html += f'    <span class="timestamp">{time_str}</span>\n'
            cards_html += f'    <span class="issue-count">{issue_total} issue(s)</span>\n'
            if tag:
                cards_html += f'    <span class="issue-count">{tag}</span>\n'
            if commit:
                cards_html += f'    <span class="issue-count">commit: {html.escape(commit[:8])}</span>\n'
            if not is_read:
                cards_html += f'    <span class="unread-dot" title="Unread"></span>\n'
            cards_html += f'  </div>\n'

            if files:
                cards_html += f'  <div class="card-meta">{len(files)} file(s): {html.escape(", ".join(files[:5]))}'
                if len(files) > 5:
                    cards_html += f' +{len(files)-5} more'
                cards_html += '</div>\n'

            if summary:
                cards_html += f'  <div class="card-summary">{summary}</div>\n'

            if highlights:
                cards_html += f'  <div class="highlights">\n'
                for h in highlights:
                    cards_html += f'    <div class="hl-item">+ {html.escape(h)}</div>\n'
                cards_html += f'  </div>\n'

            cards_html += f'  <div class="card-issues" id="issues-{rid}">\n'
            for iss in issues:
                cards_html += _render_issue(iss)
            if not issues:
                cards_html += '<div class="no-reports">No issues found.</div>'
            cards_html += f'  </div>\n'
            cards_html += f'</div>\n'

    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI Code Review Dashboard</title>
<style>{_css()}</style>
</head>
<body>
<header>
<h1>AI Code Review Dashboard</h1>
<div class="summary-bar">{summary_html}</div>
<input type="text" id="filter" placeholder="Filter reports..." autofocus />
</header>
<main>
{cards_html}
</main>
<script>{_js()}</script>
</body>
</html>"""

    output_path = os.path.join(reports_dir, "index.html")
    os.makedirs(reports_dir, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(page)

    return output_path


def open_dashboard(path: str) -> bool:
    """Open the dashboard HTML file in the default browser."""
    try:
        url = "file:///" + os.path.abspath(path).replace("\\", "/")
        return webbrowser.open(url)
    except Exception:
        return False
