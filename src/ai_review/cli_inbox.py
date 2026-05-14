"""Inbox CLI commands - browse and manage review reports."""

import os
import webbrowser
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ai_review.inbox import InboxManager

inbox_app = typer.Typer(name="inbox", help="Review report inbox")
console = Console()

_STATUS_ICONS = {
    "PASS": "✅",
    "WARNING": "⚠️",
    "BLOCKING": "❌",
}

_SEVERITY_ICONS = {
    "CRITICAL": "\U0001f6d1",
    "ERROR": "\U0001f534",
    "WARNING": "\U0001f7e1",
    "INFO": "ℹ️",
}


@inbox_app.callback(invoke_without_command=True)
def inbox_list(
    ctx: typer.Context,
    unread: bool = typer.Option(False, "--unread", "-u", help="Show unread only"),
    status: Optional[str] = typer.Option(None, "--status", "-s", help="Filter by status (PASS/WARNING/BLOCKING)"),
    limit: int = typer.Option(20, "--limit", "-n", help="Max reports to show"),
    all_reports: bool = typer.Option(False, "--all", help="Include archived"),
):
    """List review reports in the inbox."""
    if ctx.invoked_subcommand is not None:
        return
    mgr = InboxManager()
    reports = mgr.list_reports(
        status=status.upper() if status else None,
        unread_only=unread,
        limit=limit,
        include_archived=all_reports,
    )

    unread_count = mgr.get_unread_count()
    if unread_count > 0:
        typer.echo(f"🔔 You have {unread_count} unread report(s)\n")

    if not reports:
        typer.echo("📭 No reports found")
        return

    table = Table(show_header=True, header_style="bold", padding=(0, 2))
    table.add_column("Status", width=8)
    table.add_column("Time", width=18)
    table.add_column("Tag", width=20)
    table.add_column("Files", width=5, justify="right")
    table.add_column("Issues", width=7, justify="right")
    table.add_column("", width=3)

    for r in reports:
        icon = _STATUS_ICONS.get(r.status, "?")
        read_marker = "" if r.read else "🔵"
        tag_display = r.tag[:18] if r.tag else r.report_id[:18]
        table.add_row(
            f"{icon} {r.status}",
            r.time_str,
            tag_display,
            str(r.file_count),
            str(r.issue_count),
            read_marker,
        )

    console.print(table)
    typer.echo(f"\nUse 'ai-review inbox show <report-id>' to view details")


@inbox_app.command("show")
def inbox_show(
    report_id: str = typer.Argument(help="Report ID to view"),
    md: bool = typer.Option(False, "--md", help="Open markdown report in browser"),
):
    """Show a specific report and mark it as read."""
    mgr = InboxManager()

    if md:
        path = mgr.get_report_path(report_id, "md")
        if not path:
            typer.echo(f"❌ Report not found: {report_id}", err=True)
            raise typer.Exit(1)
        url = "file:///" + os.path.abspath(path).replace("\\", "/")
        webbrowser.open(url)
        typer.echo(f"📄 Opened: {path}")
        mgr.mark_read(report_id)
        return

    data = mgr.get_report(report_id)
    if not data:
        typer.echo(f"❌ Report not found: {report_id}", err=True)
        raise typer.Exit(1)

    mgr.mark_read(report_id)

    status = data.get("status", "PASS")
    icon = _STATUS_ICONS.get(status, "?")
    summary = data.get("summary", "")
    issues = data.get("issues", [])
    highlights = data.get("highlights", [])
    files = data.get("files", [])
    commit = data.get("commit", "")
    ts = data.get("timestamp", 0)

    from datetime import datetime
    time_str = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S") if ts else ""

    # Header
    header = Text()
    header.append(f"{icon} {status}", style="bold")
    header.append(f"  |  {time_str}")
    if commit:
        header.append(f"  |  commit: {commit[:8]}")
    if files:
        header.append(f"  |  {len(files)} file(s)")
    console.print(Panel(header, title=f"Report: {report_id}"))

    # Summary
    if summary:
        typer.echo(f"\n📝 {summary}\n")

    # Highlights
    if highlights:
        typer.echo("Highlights:")
        for h in highlights:
            typer.echo(f"  ✅ {h}")
        typer.echo("")

    # Issues
    if issues:
        typer.echo(f"Issues ({len(issues)}):")
        for idx, iss in enumerate(issues, 1):
            sev = iss.get("severity", "INFO")
            sev_icon = _SEVERITY_ICONS.get(sev, "?")
            msg = iss.get("message", "")
            rule = iss.get("rule_id", "")
            loc = ""
            if iss.get("file"):
                loc = iss["file"]
                if iss.get("line"):
                    loc += f":{iss['line']}"

            typer.echo(f"\n  {idx}. {sev_icon} [{sev}] {msg}")
            if rule:
                typer.echo(f"     Rule: {rule}")
            if loc:
                typer.echo(f"     Location: {loc}")

            bad = iss.get("bad_code")
            fixed = iss.get("fixed_code")
            if bad:
                typer.echo(f"     - {bad[:100]}{'...' if len(bad) > 100 else ''}")
            if fixed:
                typer.echo(f"     + {fixed[:100]}{'...' if len(fixed) > 100 else ''}")
            elif iss.get("suggestion"):
                typer.echo(f"     💡 {iss['suggestion'][:120]}")
    else:
        typer.echo("No issues found. 🎉")


@inbox_app.command("read")
def inbox_read(
    report_id: str = typer.Argument(help="Report ID to mark as read"),
):
    """Mark a report as read."""
    mgr = InboxManager()
    data = mgr.get_report(report_id)
    if not data:
        typer.echo(f"❌ Report not found: {report_id}", err=True)
        raise typer.Exit(1)
    mgr.mark_read(report_id)
    typer.echo(f"✅ Marked as read: {report_id}")


@inbox_app.command("unread")
def inbox_unread(
    report_id: str = typer.Argument(help="Report ID to mark as unread"),
):
    """Mark a report as unread."""
    mgr = InboxManager()
    data = mgr.get_report(report_id)
    if not data:
        typer.echo(f"❌ Report not found: {report_id}", err=True)
        raise typer.Exit(1)
    mgr.mark_unread(report_id)
    typer.echo(f"🔵 Marked as unread: {report_id}")


@inbox_app.command("mark-all-read")
def inbox_mark_all_read():
    """Mark all reports as read."""
    mgr = InboxManager()
    count = mgr.mark_all_read()
    if count:
        typer.echo(f"✅ Marked {count} report(s) as read")
    else:
        typer.echo("All reports already read")


@inbox_app.command("dashboard")
def inbox_dashboard():
    """Generate and open the HTML dashboard in browser."""
    from ai_review.dashboard import generate_dashboard, open_dashboard

    path = generate_dashboard()
    typer.echo(f"📊 Dashboard: {path}")

    if open_dashboard(path):
        typer.echo("🌐 Opened in browser")
    else:
        typer.echo("⚠️  Could not open browser, please open the file manually")
