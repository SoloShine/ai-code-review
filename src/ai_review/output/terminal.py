from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich import box
from typing import List, Optional, Union

from ai_review.reviewer.screener import ScreenResult
from ai_review.reviewer.parser import Issue
from ai_review.memory.store import ReviewMemory


class TerminalOutput:
    def __init__(self):
        self.console = Console()

    def screen_result(self, result: ScreenResult, memory_reminder: Union[str, None] = None):
        """Print fast screen result with colors"""
        if result.action == "PASS":
            self._print_pass_result(result, memory_reminder)
        elif result.action == "BLOCK":
            self._print_block_result(result)
        elif result.action == "TIMEOUT":
            self._print_timeout_result(result)
        elif result.action == "ERROR":
            self._print_error_result(result)

    def _print_pass_result(self, result: ScreenResult, memory_reminder: Union[str, None]):
        """Print PASS result with optional memory reminder"""
        panel_content = Text()
        panel_content.append("✅ Review PASSED\n", style="green bold")

        if result.reason:
            panel_content.append(f"Reason: {result.reason}\n", style="green")

        if result.warnings:
            panel_content.append("\n⚠️  Warnings:\n", style="yellow")
            for warning in result.warnings:
                panel_content.append(f"  • {warning}\n", style="yellow")

        if memory_reminder:
            panel_content.append("\n💡 Memory Reminder:\n", style="yellow italic")
            panel_content.append(memory_reminder, style="yellow italic")

        elapsed_text = f"\n⏱️  Completed in {result.elapsed_seconds:.2f}s"
        panel_content.append(elapsed_text, style="dim")

        self.console.print(Panel(panel_content, title="Fast Screen Result", border_style="green"))

    def _print_block_result(self, result: ScreenResult):
        """Print BLOCK result with issues"""
        panel_content = Text()
        panel_content.append("🛑 Review BLOCKED\n", style="red bold")

        if result.reason:
            panel_content.append(f"Reason: {result.reason}\n", style="red")

        if result.issues:
            panel_content.append("\n🔴 Critical Issues:\n", style="red bold")
            for issue in result.issues:
                panel_content.append(f"  • {issue}\n", style="red")

        if result.warnings:
            panel_content.append("\n⚠️  Warnings:\n", style="yellow")
            for warning in result.warnings:
                panel_content.append(f"  • {warning}\n", style="yellow")

        elapsed_text = f"\n⏱️  Completed in {result.elapsed_seconds:.2f}s"
        panel_content.append(elapsed_text, style="dim")

        self.console.print(Panel(panel_content, title="Fast Screen Result", border_style="red"))

    def _print_timeout_result(self, result: ScreenResult):
        """Print TIMEOUT result (auto-pass)"""
        panel_content = Text()
        panel_content.append("⚠️  Review TIMEOUT - Auto-PASS\n", style="yellow bold")
        panel_content.append(f"Reason: {result.reason}\n", style="yellow")

        disclaimer = "\n⚠️  Note: No review was performed due to timeout. Changes are allowed but not checked."
        panel_content.append(disclaimer, style="yellow italic")

        elapsed_text = f"\n⏱️  Timed out after {result.elapsed_seconds:.2f}s"
        panel_content.append(elapsed_text, style="dim")

        self.console.print(Panel(panel_content, title="Fast Screen Result", border_style="yellow"))

    def _print_error_result(self, result: ScreenResult):
        """Print ERROR result"""
        panel_content = Text()
        panel_content.append("❌ Review ERROR\n", style="yellow bold")
        panel_content.append(f"Reason: {result.reason}\n", style="yellow")

        disclaimer = "\n⚠️  Note: Review service unavailable. Changes are allowed but not checked."
        panel_content.append(disclaimer, style="yellow italic")

        elapsed_text = f"\n⏱️  Failed after {result.elapsed_seconds:.2f}s"
        panel_content.append(elapsed_text, style="dim")

        self.console.print(Panel(panel_content, title="Fast Screen Result", border_style="yellow"))

    def reminder(self, file_path: str, level: str, warnings_text: str):
        """Print memory reminder with appropriate detail level"""
        if level == "full":
            self._print_full_reminder(file_path, warnings_text)
        elif level == "short":
            self._print_short_reminder(file_path, warnings_text)
        elif level == "minimal":
            self._print_minimal_reminder(file_path, warnings_text)

    def _print_full_reminder(self, file_path: str, warnings_text: str):
        """Print full memory reminder panel"""
        panel_content = Text()
        panel_content.append("💡 Memory Reminder\n", style="yellow bold")
        panel_content.append(f"File: {file_path}\n\n", style="yellow")
        panel_content.append(warnings_text, style="yellow")

        self.console.print(Panel(panel_content, title="Memory Reminder", border_style="yellow"))

    def _print_short_reminder(self, file_path: str, warnings_text: str):
        """Print short memory reminder (single line with more detail)"""
        self.console.print(
            f"[yellow]💡 Memory Reminder for {file_path}: {warnings_text}[/yellow]",
            style="yellow"
        )

    def _print_minimal_reminder(self, file_path: str, warnings_text: str):
        """Print minimal memory reminder (single dim line)"""
        self.console.print(
            f"[dim]💡 {file_path}: {warnings_text}[/dim]",
            style="dim"
        )

    def async_summary(self, result):
        """Print async review summary (called from system notification context)"""
        if result.status == "BLOCKING":
            self._print_async_block_summary(result)
        elif result.status == "WARNING":
            self._print_async_warning_summary(result)
        else:
            self._print_async_pass_summary(result)

    def _print_async_block_summary(self, result):
        """Print async review BLOCKING summary"""
        panel_content = Text()
        panel_content.append("🛑 Async Review: BLOCKING Issues Found\n", style="red bold")
        panel_content.append(f"Summary: {result.summary}\n\n", style="red")

        if result.issues:
            panel_content.append("🔴 Critical Issues:\n", style="red bold")
            table = Table(box=box.ROUNDED, show_header=False, padding=(0, 2))

            for issue in result.issues[:5]:  # Show first 5 issues
                table.add_row(f"• {issue.file_path}:{issue.line_number}", str(issue.message))

            panel_content.append(table)

            if len(result.issues) > 5:
                panel_content.append(f"\n  ... and {len(result.issues) - 5} more issues", style="dim")

        if result.report_path:
            panel_content.append(f"\n\n📄 Full report: {result.report_path}", style="blue")

        self.console.print(Panel(panel_content, title="Async Review Summary", border_style="red"))

    def _print_async_warning_summary(self, result):
        """Print async review WARNING summary"""
        panel_content = Text()
        panel_content.append("⚠️  Async Review: Warnings Found\n", style="yellow bold")
        panel_content.append(f"Summary: {result.summary}\n\n", style="yellow")

        if result.file_warnings:
            panel_content.append("⚠️  Warnings by file:\n", style="yellow bold")
            table = Table(box=box.ROUNDED, show_header=False, padding=(0, 2))

            for file_path, issues in list(result.file_warnings.items())[:3]:  # Show first 3 files
                table.add_row(f"• {file_path}", f"{len(issues)} warning(s)")

            panel_content.append(table)

            if len(result.file_warnings) > 3:
                panel_content.append(f"\n  ... and {len(result.file_warnings) - 3} more files with warnings", style="dim")

        if result.report_path:
            panel_content.append(f"\n\n📄 Full report: {result.report_path}", style="blue")

        self.console.print(Panel(panel_content, title="Async Review Summary", border_style="yellow"))

    def _print_async_pass_summary(self, result):
        """Print async review PASS summary"""
        panel_content = Text()
        panel_content.append("✅ Async Review: PASSED\n", style="green bold")
        panel_content.append(f"Summary: {result.summary}", style="green")

        if result.report_path:
            panel_content.append(f"\n\n📄 Full report: {result.report_path}", style="blue")

        self.console.print(Panel(panel_content, title="Async Review Summary", border_style="green"))