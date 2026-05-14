"""
AI Code Review CLI - Main entry point using Typer
"""
import typer
from pathlib import Path
import os
import subprocess
import sys
import yaml
import logging
import time
from typing import Optional, List

# Fix Windows console encoding for emoji/unicode output
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from ai_review.memory.store import ReviewMemory
from ai_review.llm.base import LLMProvider
from ai_review.rules.loader import RuleEngine
from ai_review.reviewer.screener import FastScreener
from ai_review.hooks.installer import HookInstaller
from ai_review.config import resolve_config

logger = logging.getLogger("ai_review")

app = typer.Typer(
    name="ai-review",
    help="AI-powered code review with pre-commit hooks"
)

from ai_review.cli_inbox import inbox_app
app.add_typer(inbox_app, name="inbox")

def is_git_repo() -> bool:
    """Check if current directory is a git repository"""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=".",
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False

def get_git_diff(base: Optional[str] = None, cached: bool = True) -> str:
    """Get git diff for review"""
    cmd = ["git", "diff"]
    if cached:
        cmd.append("--cached")
    if base:
        cmd.extend(["origin", base])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        return result.stdout
    except subprocess.TimeoutExpired:
        return ""

def get_staged_files() -> List[str]:
    """Get list of staged files"""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        if result.returncode == 0:
            return result.stdout.strip().split('\n') if result.stdout.strip() else []
        return []
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []

def create_ai_review_dir() -> None:
    """Create .ai-review directory structure"""
    ai_review_dir = Path(".ai-review")
    ai_review_dir.mkdir(exist_ok=True)

    # Create rules directory with example rule
    rules_dir = ai_review_dir / "rules"
    rules_dir.mkdir(exist_ok=True)

    # Example rule in proper format (rules: list with applies_to)
    example_rule = {
        "name": "Example Review Rules",
        "description": "Example code review rules",
        "rules": [
            {
                "id": "no-todo-fixme",
                "title": "TODO/FIXME should be resolved before commit",
                "severity": "warning",
                "enabled": True,
                "applies_to": {
                    "extensions": [".py", ".js", ".ts", ".vue", ".java", ".cs"]
                },
                "description": "TODO and FIXME comments should be resolved or tracked before committing code."
            }
        ]
    }

    with open(rules_dir / "example_rule.yaml", "w", encoding="utf-8") as f:
        yaml.dump(example_rule, f, allow_unicode=True)

def generate_config(
    mode: str = "balanced",
    backend: str = "ollama",
    model: str = "qwen2.5-coder:7b"
) -> None:
    """Generate .ai-review.yaml configuration"""
    config = {
        "mode": mode,
        "llm": {
            "backend": backend,
            "model": model
        },
        "rules": {
            "include_categories": ["security", "performance", "style", "best_practices"],
            "exclude_categories": []
        },
        "memory": {
            "enabled": True,
            "memory_file": ".ai-review/memory.json",
            "suppression_file": ".ai-review/suppressions.json"
        },
        "review": {
            "max_file_size_mb": 1,
            "ignore_patterns": [
                "*.pyc",
                "__pycache__",
                "node_modules/",
                ".git/",
                "*.min.js"
            ]
        }
    }

    with open(".ai-review.yaml", "w") as f:
        yaml.dump(config, f)

@app.command()
def init(
    mode: str = typer.Option("balanced", help="Review mode: strict / balanced"),
    backend: str = typer.Option("ollama", help="LLM backend: ollama / openai_compatible"),
    model: str = typer.Option("qwen2.5-coder:7b", help="Model name"),
):
    """
    Initialize ai-review in the current project.
    1. Create .ai-review.yaml with selected mode and LLM config
    2. Install git hooks (pre-commit + post-commit)
    3. Create .ai-review/ directory
    4. Create rules/ directory with example rule
    """
    # Check if we're in a git repo
    if not is_git_repo():
        typer.echo("❌ Error: Not a git repository. Please run this command in a git repo.", err=True)
        raise typer.Exit(1)

    # Check if already initialized
    if os.path.exists(".ai-review.yaml") or os.path.exists(".ai-review"):
        typer.echo("⚠️  Warning: ai-review appears to be already initialized in this project.", err=True)
        if typer.confirm("Do you want to overwrite existing configuration?"):
            # Remove existing config and dir
            if os.path.exists(".ai-review.yaml"):
                os.remove(".ai-review.yaml")
            if os.path.exists(".ai-review"):
                import shutil
                shutil.rmtree(".ai-review")
        else:
            raise typer.Exit(0)

    # Generate configuration
    typer.echo("🔧 Creating .ai-review.yaml...")
    generate_config(mode, backend, model)

    # Create directory structure
    typer.echo("📁 Creating .ai-review directory...")
    create_ai_review_dir()

    # Install hooks
    typer.echo("🪝 Installing git hooks...")
    try:
        hook_installer = HookInstaller(os.getcwd())
        hook_installer.install()
        typer.echo("✅ Hooks installed successfully!")
    except Exception as e:
        typer.echo(f"❌ Failed to install hooks: {e}", err=True)

    typer.echo("\n🎉 AI Code Review initialized successfully!")
    typer.echo("\nNext steps:")
    typer.echo("1. Review your .ai-review.yaml configuration")
    typer.echo("2. Add your custom rules to .ai-review/rules/")
    typer.echo("3. Commit some code to test the pre-commit hook")
    typer.echo("4. Run 'ai-review status' to see pending warnings")

def _setup_logging(verbose: bool, debug: bool) -> None:
    """Configure logging based on verbosity level."""
    if debug:
        level = logging.DEBUG
    elif verbose:
        level = logging.INFO
    else:
        level = logging.WARNING
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s", stream=sys.stderr)


def _create_llm_provider(config):
    """Create LLM provider from config."""
    if config.llm.backend == "ollama":
        from ai_review.llm.ollama import OllamaProvider
        return OllamaProvider(
            model=config.llm.ollama.model,
            base_url=config.llm.ollama.base_url,
            timeout=config.llm.ollama.timeout
        )
    elif config.llm.backend == "openai_compatible":
        from ai_review.llm.openai import OpenAICompatibleProvider
        return OpenAICompatibleProvider(
            model=config.llm.openai_compatible.model,
            api_key_env=config.llm.openai_compatible.api_key_env,
            base_url=config.llm.openai_compatible.base_url,
            timeout=config.llm.openai_compatible.timeout
        )
    else:
        raise ValueError(f"Unsupported backend: {config.llm.backend}")


def _create_rule_engine(config) -> 'RuleEngine':
    """Create rule engine with configured rule directories."""
    rules_dirs = ['.ai-review/rules/']
    if config.rules and config.rules.get("dirs"):
        rules_dirs.extend(config.rules["dirs"])
    return RuleEngine(rules_dirs)


def _build_suppressed_map(memory: ReviewMemory) -> dict:
    """Build a mapping: file_path -> list of suppressed rule_ids.

    Returns dict like {'some/file.ts': ['no-console-log', 'no-any-type'], ...}
    Files with 'ALL' suppression get a special ['ALL'] entry.
    """
    result = {}
    for fp, sup_record in memory.list_suppressed():
        rid = sup_record.get("rule_id") if isinstance(sup_record, dict) else getattr(sup_record, "rule_id", None)
        if rid:
            result.setdefault(fp, []).append(rid)
    return result


def _issue_is_suppressed(issue, changed_files: list, suppressed_map: dict) -> bool:
    """Check if a single issue is covered by any suppression entry.

    Matching strategy:
    1. Exact match after normalizing (hyphens/underscores/case)
    2. Substring match on rule_id
    3. Keyword extraction from rule_id matched against issue message
       e.g. 'no-console-log' -> keywords ['console', 'log'] -> found in 'console.log 调试语句'
    """
    fp = issue.file or ""
    rid_raw = issue.rule_id or ""
    message = (issue.message or "").lower()

    for target_file in [fp] + [f for f in changed_files if f]:
        suppressed_rules = suppressed_map.get(target_file, [])
        if not suppressed_rules:
            continue

        if "ALL" in suppressed_rules:
            return True

        rid_normalized = rid_raw.lower().replace("_", "-").replace(" ", "-")

        for sup_rid in suppressed_rules:
            sup_normalized = sup_rid.lower().replace("_", "-").replace(" ", "-")

            # 1. Exact match
            if rid_normalized == sup_normalized:
                return True

            # 2. Substring match
            if sup_normalized and (sup_normalized in rid_normalized or rid_normalized in sup_normalized):
                return True

            # 3. Keyword match: extract meaningful words from rule_id, check against message
            # e.g. 'no-console-log' -> ['console', 'log']
            # e.g. 'no-any-type' -> ['any', 'type']
            keywords = [w for w in sup_normalized.split("-") if len(w) > 2 and w not in ("the", "and", "not", "use", "for")]
            if keywords and message:
                # All keywords must appear in the message for a match
                if all(kw in message for kw in keywords):
                    return True

    return False


def _should_notify(issues: list, changed_files: list, suppressed_map: dict) -> bool:
    """Decide whether to show notification. Returns False if ALL issues are suppressed."""
    if not issues:
        return False

    for issue in issues:
        if not _issue_is_suppressed(issue, changed_files, suppressed_map):
            return True  # At least one non-suppressed issue exists

    return False  # All issues are suppressed


def _save_report(
    tag: str,
    status: str,
    issues: list,
    summary: str = "",
    highlights: list = None,
    files: list = None,
    commit: str = None,
) -> str:
    """Save review report in both JSON and Markdown formats.

    Args:
        tag: Short tag for filename (e.g. "precommit", commit SHA prefix)
        status: Review status (PASS / WARNING / BLOCKING)
        issues: List of Issue objects
        summary: Review summary text
        highlights: List of positive aspects
        files: List of reviewed file paths
        commit: Optional commit SHA

    Returns:
        Path to the Markdown report file.
    """
    import json
    from pathlib import Path as _Path

    reports_dir = _Path(".ai-review/reports")
    reports_dir.mkdir(parents=True, exist_ok=True)

    timestamp = int(time.time())
    base_name = f"review_{tag}_{timestamp}"

    # Prepare issue data
    issue_dicts = []
    for i in issues:
        issue_dicts.append({
            "severity": i.severity,
            "rule_id": i.rule_id,
            "file": i.file,
            "line": i.line,
            "message": i.message,
            "suggestion": i.suggestion,
            "bad_code": getattr(i, 'bad_code', None),
            "fixed_code": getattr(i, 'fixed_code', None),
        })

    # Severity counts
    sev_counts = {}
    for iss in issue_dicts:
        s = iss["severity"]
        sev_counts[s] = sev_counts.get(s, 0) + 1

    # Save JSON
    json_path = reports_dir / f"{base_name}.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump({
            "tag": tag,
            "commit": commit,
            "timestamp": timestamp,
            "status": status,
            "files": files or [],
            "severity_counts": sev_counts,
            "highlights": highlights or [],
            "issues": issue_dicts,
            "summary": summary,
        }, f, indent=2, ensure_ascii=False)

    # Save Markdown
    md_path = reports_dir / f"{base_name}.md"
    with open(md_path, 'w', encoding='utf-8') as f:
        status_icon = {"PASS": "✅", "WARNING": "⚠️", "BLOCKING": "❌"}.get(status, "❓")
        f.write(f"# {status_icon} Code Review Report\n\n")
        f.write(f"| | |\n")
        f.write(f"|---|---|\n")
        f.write(f"| **Status** | {status_icon} {status} |\n")
        if commit:
            f.write(f"| **Commit** | `{commit}` |\n")
        f.write(f"| **Time** | {time.strftime('%Y-%m-%d %H:%M:%S')} |\n")
        if files:
            f.write(f"| **Files** | {len(files)} file(s) |\n")
        if sev_counts:
            sev_line = " · ".join(f"{v} {k.lower()}" for k, v in
                                  sorted(sev_counts.items(),
                                         key=lambda x: ["CRITICAL", "ERROR", "WARNING", "INFO"].index(x[0])
                                         if x[0] in ["CRITICAL", "ERROR", "WARNING", "INFO"] else 99))
            f.write(f"| **Issues** | {sev_line} |\n")
        f.write(f"\n")

        # Summary
        if summary:
            f.write(f"## Summary\n\n{summary}\n\n")

        # Highlights (positive feedback)
        if highlights:
            f.write(f"## Highlights\n\n")
            for h in highlights:
                f.write(f"- ✅ {h}\n")
            f.write(f"\n")

        # Issues
        if issue_dicts:
            f.write(f"## Issues\n\n")
            for idx, iss in enumerate(issue_dicts, 1):
                sev_icon = {
                    "CRITICAL": "🛑", "ERROR": "🔴", "WARNING": "🟡", "INFO": "ℹ️"
                }.get(iss["severity"], "❓")
                f.write(f"### {idx}. {sev_icon} [{iss['severity']}] {iss['message']}\n\n")

                details = []
                if iss.get("rule_id"):
                    details.append(f"**Rule:** `{iss['rule_id']}`")
                if iss.get("file"):
                    line_str = f":{iss['line']}" if iss.get("line") else ""
                    details.append(f"**Location:** `{iss['file']}{line_str}`")
                if details:
                    f.write(" · ".join(details) + "\n\n")

                # Show code fix if available
                if iss.get("bad_code"):
                    f.write("**Problem code:**\n")
                    f.write(f"```diff\n- {iss['bad_code']}\n")
                    if iss.get("fixed_code"):
                        f.write(f"+ {iss['fixed_code']}\n")
                    f.write(f"```\n\n")
                elif iss.get("suggestion"):
                    f.write(f"**Suggestion:** {iss['suggestion']}\n\n")

                # If we have both suggestion and code fix, show suggestion as note
                if iss.get("suggestion") and iss.get("bad_code"):
                    f.write(f"> _{iss['suggestion']}_\n\n")
        else:
            f.write(f"## Issues\n\nNo issues found. 🎉\n\n")

    logger.info("Report saved: %s (json+md)", base_name)

    # Register in inbox
    try:
        from ai_review.inbox import InboxManager
        inbox = InboxManager()
        inbox.register_report(base_name)
    except Exception as e:
        logger.warning("Failed to register report in inbox: %s", e)

    # Update HTML dashboard
    try:
        from ai_review.dashboard import generate_dashboard
        generate_dashboard(str(reports_dir))
    except Exception as e:
        logger.warning("Failed to generate dashboard: %s", e)

    return str(md_path)


@app.command()
def check(
    pre_commit: bool = typer.Option(False, "--pre-commit", help="Run as pre-commit hook"),
    base: str = typer.Option(None, "--base", help="Base branch for diff comparison"),
    no_block: bool = typer.Option(False, "--no-block", help="Report only, don't block"),
    path: str = typer.Option(None, "--path", help="Review specific file"),
    async_mode: bool = typer.Option(False, "--async", help="Run async post-commit review"),
    commit: str = typer.Option(None, "--commit", help="Commit SHA to review"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed output"),
    debug: bool = typer.Option(False, "--debug", help="Show debug output including prompts and raw LLM responses"),
    open_dashboard: bool = typer.Option(False, "--open-dashboard", help="Open HTML dashboard in browser after review"),
):
    """
    Run code review.

    Default: review staged changes (git diff --cached)
    --pre-commit: run as pre-commit hook (fast screen)
    --base main: review branch diff
    """
    _setup_logging(verbose, debug)

    try:
        # Load configuration
        config = resolve_config()
        logger.info("Config loaded: mode=%s, backend=%s, model=%s",
                     config.mode, config.llm.backend,
                     config.llm.ollama.model if config.llm.backend == 'ollama'
                     else config.llm.openai_compatible.model)

        # Create LLM provider
        llm_provider = _create_llm_provider(config)

        if pre_commit:
            # Fast screen mode for pre-commit
            typer.echo("🔍 Running fast pre-commit screen...")

            # Get staged files
            staged_files = get_staged_files()
            logger.info("Staged files: %s", staged_files)
            if not staged_files:
                typer.echo("✅ No staged files to review")
                raise typer.Exit(0)

            # Get diff and files
            diff = get_git_diff(cached=True)
            if not diff and not path:
                typer.echo("✅ No staged changes to review")
                raise typer.Exit(0)

            logger.debug("Diff content:\n%s", diff[:2000])

            # Create fast screener
            from ai_review.reviewer.screener import FastScreener
            from ai_review.prompt.builder import PromptBuilder
            from ai_review.reviewer.parser import ReviewParser

            fast_screener = FastScreener(llm_provider, PromptBuilder(), ReviewParser(), config.hooks["pre_commit"])

            # Load rules and filter by configured severities
            rule_engine = _create_rule_engine(config)
            severity_filter = config.hooks["pre_commit"].rules_filter.severities
            # "all" means no filter
            if severity_filter == ["all"]:
                severity_filter = None
            matched_rules = rule_engine.match(staged_files, severity_filter)
            logger.info("Matched %d rules (filter=%s): %s",
                        len(matched_rules), severity_filter,
                        [r.id for r in matched_rules])
            rules_prompt = rule_engine.format_for_prompt(matched_rules)

            if debug:
                typer.echo(f"\n[DEBUG] Rules prompt:\n{rules_prompt}\n", err=True)

            result = fast_screener.screen(diff, rules_prompt, staged_files)

            logger.info("Screen result: action=%s, issues=%d, elapsed=%.1fs, reason=%s",
                        result.action, len(result.issues), result.elapsed_seconds, result.reason)

            if result.action == "BLOCK" and not no_block:
                typer.echo("\n❌ Code review blocked - commit rejected", err=True)
                if result.issues:
                    typer.echo("\nIssues found:")
                    for issue in result.issues:
                        typer.echo(f"  🔴 {issue.message}")

                # Save report and send notification for blocked commits
                report_md = _save_report(
                    tag="precommit-blocked",
                    status="BLOCKING",
                    issues=result.issues,
                    summary=result.reason or "",
                    highlights=result.highlights,
                    files=staged_files,
                )
                typer.echo(f"\n📄 Report: {report_md}", err=True)
                dashboard_path = os.path.join(".ai-review", "reports", "index.html")
                if os.path.exists(dashboard_path):
                    typer.echo(f"📊 Dashboard: {dashboard_path}", err=True)

                from ai_review.output.notify import SystemNotifier
                issue_summary = "; ".join(i.message for i in result.issues[:3])
                SystemNotifier().notify(
                    "AI Review: Commit Blocked",
                    f"{len(result.issues)} issue(s): {issue_summary}",
                    duration=15,
                )
                raise typer.Exit(1)
            else:
                typer.echo("✅ Code review passed")
                if result.issues:
                    typer.echo("\n⚠️  Warnings found (but not blocking):")
                    for issue in result.issues:
                        typer.echo(f"  🟡 {issue.message}")
                if result.warnings:
                    for w in result.warnings:
                        typer.echo(f"  ℹ️  {w}")
                if verbose and result.reason:
                    typer.echo(f"\n  Reason: {result.reason}")
                    typer.echo(f"  Time: {result.elapsed_seconds:.1f}s")
                raise typer.Exit(0)

        elif async_mode:
            # Async post-commit review - full review of the commit
            if not commit:
                typer.echo("❌ Error: --commit is required for async mode", err=True)
                raise typer.Exit(1)

            typer.echo(f"🔄 Running async review for commit: {commit[:8]}")

            # Get commit diff and changed files
            try:
                diff_result = subprocess.run(
                    ["git", "diff-tree", "--no-commit-id", "-r", "--name-only", commit],
                    capture_output=True, text=True, encoding="utf-8", errors="replace"
                )
                changed_files = [f for f in diff_result.stdout.strip().split('\n') if f] if diff_result.stdout.strip() else []

                diff_content_result = subprocess.run(
                    ["git", "show", commit],
                    capture_output=True, text=True, encoding="utf-8", errors="replace"
                )
                diff = diff_content_result.stdout
            except Exception as e:
                typer.echo(f"❌ Failed to get commit info: {e}", err=True)
                raise typer.Exit(1)

            if not diff or not changed_files:
                typer.echo("✅ No changes to review")
                raise typer.Exit(0)

            logger.info("Async review: commit=%s, files=%s", commit[:8], changed_files)

            # Load rules (all severities for full review)
            rule_engine = _create_rule_engine(config)
            matched_rules = rule_engine.match(changed_files, None)
            rules_prompt = rule_engine.format_for_prompt(matched_rules)

            # Build memory reminders
            memory = ReviewMemory(".ai-review/memory.json")
            pending_warnings_text = ""
            if config.memory.enabled:
                reminders = []
                for fp in changed_files:
                    level = memory.get_reminder_level(fp)
                    if level:
                        reminders.append(memory.format_reminder(fp, level))
                        memory.increment_remind_count(fp)
                pending_warnings_text = "\n\n".join(reminders)

            # Build full prompt
            from ai_review.prompt.builder import PromptBuilder
            prompt_builder = PromptBuilder()
            prompt = prompt_builder.build_full(
                diff=diff,
                rules_prompt=rules_prompt,
                pending_warnings_text=pending_warnings_text,
            )

            if debug:
                typer.echo(f"\n[DEBUG] Async prompt:\n{prompt[:3000]}\n", err=True)

            # Call LLM with longer timeout
            timeout = (config.llm.openai_compatible.timeout if config.llm.backend == "openai_compatible"
                       else config.llm.ollama.timeout)
            response = llm_provider.review(prompt, timeout=min(timeout * 2, 120))

            if not response.success:
                logger.warning("Async review LLM failed: %s", response.error)
                raise typer.Exit(0)

            # Parse response
            from ai_review.reviewer.parser import ReviewParser
            parser = ReviewParser()
            result = parser.parse(response.content)

            # Build suppression map for notification control
            suppressed_map = _build_suppressed_map(memory) if config.memory.enabled else {}

            # Save report (all issues, even suppressed ones)
            report_md = _save_report(
                tag=commit[:8],
                status=result.status,
                issues=result.issues,
                summary=result.summary,
                highlights=result.highlights,
                files=changed_files,
                commit=commit,
            )

            # Record to memory
            if config.memory.enabled and result.status != "PASS":
                for fp in changed_files:
                    memory.record_warnings(fp, [
                        {"rule_id": i.rule_id or "unknown", "message": i.message}
                        for i in result.issues
                    ])

            # Send notification only if there are non-suppressed issues
            if _should_notify(result.issues, changed_files, suppressed_map):
                from ai_review.output.notify import SystemNotifier
                notifier = SystemNotifier()
                if result.status == "BLOCKING":
                    issue_summary = "; ".join(i.message for i in result.issues[:3])
                    notifier.notify(
                        "AI Review: Issues Found",
                        f"Blocking in {commit[:8]}: {issue_summary}",
                        duration=15,
                    )
                elif result.status == "WARNING":
                    issue_summary = "; ".join(i.message for i in result.issues[:3])
                    notifier.notify(
                        "AI Review: Warnings",
                        f"Warnings in {commit[:8]}: {issue_summary}",
                        duration=10,
                    )

            if verbose:
                typer.echo(f"\n📝 Status: {result.status}")
                for issue in result.issues:
                    typer.echo(f"  {issue.severity}: {issue.message}")
                typer.echo(f"\n📄 Report: {report_md}")

            # Print dashboard path
            dashboard_path = os.path.join(".ai-review", "reports", "index.html")
            if os.path.exists(dashboard_path):
                typer.echo(f"📊 Dashboard: {dashboard_path}")

            # Auto-open dashboard if requested or configured
            if open_dashboard or config.dashboard.auto_open:
                from ai_review.dashboard import open_dashboard as _open_dash
                _open_dash(dashboard_path)

            raise typer.Exit(0)

        else:
            # Manual review mode - full review
            typer.echo("🔍 Running full code review...")

            # Get appropriate diff
            if path:
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    diff = f"--- a/{path}\n+++ b/{path}\n@@ -0,0 +1,{content.count(chr(10))+1} @@\n"
                    for line in content.splitlines(True):
                        diff += f"+{line}"
                    files_to_review = [path]
                except FileNotFoundError:
                    typer.echo(f"❌ Error: File not found: {path}", err=True)
                    raise typer.Exit(1)
            elif base:
                typer.echo(f"Reviewing diff against branch: {base}")
                diff = get_git_diff(base=base, cached=False)
                files_to_review = get_staged_files()
            else:
                diff = get_git_diff(cached=True)
                files_to_review = get_staged_files()

            if not diff:
                typer.echo("✅ No changes to review")
                raise typer.Exit(0)

            logger.debug("Diff content:\n%s", diff[:3000])

            # Load rules (all severities for full review)
            rule_engine = _create_rule_engine(config)
            if files_to_review:
                matched_rules = rule_engine.match(files_to_review, None)
            else:
                matched_rules = rule_engine.rules
            rules_prompt = rule_engine.format_for_prompt(matched_rules)
            logger.info("Full review: %d rules matched", len(matched_rules))

            # Build memory reminders
            memory = ReviewMemory(".ai-review/memory.json")
            pending_warnings_text = ""
            if config.memory.enabled and files_to_review:
                reminders = []
                for fp in files_to_review:
                    level = memory.get_reminder_level(fp)
                    if level:
                        reminders.append(memory.format_reminder(fp, level))
                        memory.increment_remind_count(fp)
                pending_warnings_text = "\n\n".join(reminders)

            # Build full prompt
            from ai_review.prompt.builder import PromptBuilder
            prompt_builder = PromptBuilder()
            prompt = prompt_builder.build_full(
                diff=diff,
                rules_prompt=rules_prompt,
                context_text="",
                pending_warnings_text=pending_warnings_text,
            )

            if debug:
                typer.echo(f"\n[DEBUG] Full prompt:\n{prompt[:3000]}\n", err=True)

            # Call LLM
            typer.echo("📡 Calling LLM for review...")
            response = llm_provider.review(prompt, timeout=config.llm.openai_compatible.timeout
                                           if config.llm.backend == "openai_compatible"
                                           else config.llm.ollama.timeout)

            if not response.success:
                typer.echo(f"⚠️  LLM call failed: {response.error}")
                typer.echo("✅ Review skipped (LLM unavailable)")
                raise typer.Exit(0)

            logger.debug("LLM response:\n%s", response.content[:3000])

            # Parse response
            from ai_review.reviewer.parser import ReviewParser
            parser = ReviewParser()
            result = parser.parse(response.content)

            # Display results
            if result.status == "PASS":
                typer.echo("✅ Code review passed - no issues found")
            elif result.status == "BLOCKING":
                typer.echo("❌ Code review found blocking issues:", err=True)
                for issue in result.issues:
                    severity_icon = {"CRITICAL": "🛑", "ERROR": "🔴", "WARNING": "🟡", "INFO": "ℹ️"}.get(issue.severity, "❓")
                    typer.echo(f"  {severity_icon} [{issue.severity}] {issue.message}")
                    if issue.suggestion:
                        typer.echo(f"     Suggestion: {issue.suggestion}")
                    if issue.file:
                        typer.echo(f"     File: {issue.file}" + (f":{issue.line}" if issue.line else ""))
            elif result.status == "WARNING":
                typer.echo("⚠️  Code review passed with warnings:")
                for issue in result.issues:
                    typer.echo(f"  🟡 {issue.message}")
                    if issue.suggestion:
                        typer.echo(f"     Suggestion: {issue.suggestion}")

            # Show summary
            if result.summary:
                typer.echo(f"\n📝 Summary: {result.summary}")

            # Record to memory
            if config.memory.enabled and result.status != "PASS" and files_to_review:
                for fp in files_to_review:
                    memory.record_warnings(fp, [
                        {"rule_id": issue.rule_id or "unknown",
                         "message": issue.message}
                        for issue in result.issues
                    ])

            # Save report
            if result.status != "PASS":
                tag = "manual"
                if base:
                    tag = f"vs-{base}"
                elif path:
                    tag = os.path.basename(path).rsplit(".", 1)[0]
                report_md = _save_report(
                    tag=tag,
                    status=result.status,
                    issues=result.issues,
                    summary=result.summary or "",
                    highlights=result.highlights,
                    files=files_to_review or [],
                )
                typer.echo(f"\n📄 Report: {report_md}")
                dashboard_path = os.path.join(".ai-review", "reports", "index.html")
                if os.path.exists(dashboard_path):
                    typer.echo(f"📊 Dashboard: {dashboard_path}")
                if open_dashboard:
                    from ai_review.dashboard import open_dashboard as _open_dash
                    _open_dash(dashboard_path)

            raise typer.Exit(1 if result.status == "BLOCKING" and not no_block else 0)

    except typer.Exit:
        raise
    except Exception as e:
        logger.exception("Review failed with exception")
        typer.echo(f"❌ Error during review: {e}", err=True)
        raise typer.Exit(1)

@app.command()
def suppress(
    file: str = typer.Argument(None, help="File path"),
    rule_id: str = typer.Argument(None, help="Rule ID to suppress (or --all)"),
    all_rules: bool = typer.Option(False, "--all", help="Suppress all warnings for file"),
    reason: str = typer.Option("", "--reason", help="Reason for suppression"),
    cancel: bool = typer.Option(False, "--cancel", help="Cancel suppression"),
    list_suppressed: bool = typer.Option(False, "--list", help="List suppressed warnings"),
):
    """Manage suppressed review warnings."""
    try:
        config = resolve_config()
        memory = ReviewMemory(".ai-review/memory.json")

        if list_suppressed:
            suppressed = memory.list_suppressed()
            if not suppressed:
                typer.echo("📝 No suppressed warnings found")
                return

            typer.echo("📝 Suppressed warnings:")
            for file_path, suppression in suppressed:
                typer.echo(f"  📁 {file_path}")
                if isinstance(suppression, dict):
                    typer.echo(f"    Rule: {suppression.get('rule_id', 'N/A')}")
                    typer.echo(f"    Reason: {suppression.get('reason', 'N/A')}")
                    typer.echo(f"    Suppressed at: {suppression.get('suppressed_at', 'N/A')}")
                else:
                    typer.echo(f"    Rule: {suppression.rule_id}")
                    typer.echo(f"    Reason: {suppression.reason}")
                    typer.echo(f"    Suppressed at: {suppression.suppressed_at}")
            return

        if cancel:
            # Remove suppression - use ALL if --all flag
            rid = "ALL" if all_rules else rule_id
            memory.cancel_suppress(file, rid)
            typer.echo(f"✅ Suppression removed for {file}:{rid}")
            return

        if all_rules:
            # Suppress all rules for the file
            memory.suppress_rule(file, "ALL", reason or "Suppressed all rules")
            typer.echo(f"✅ All rules suppressed for {file}")
        else:
            # Suppress specific rule
            memory.suppress_rule(file, rule_id, reason)
            typer.echo(f"✅ Suppression added for {file}:{rule_id}")
        if reason:
            typer.echo(f"   Reason: {reason}")

    except Exception as e:
        typer.echo(f"❌ Error managing suppressions: {e}", err=True)
        raise typer.Exit(1)

@app.command()
def status():
    """Show current review status and pending warnings."""
    try:
        config = resolve_config()
        memory = ReviewMemory(".ai-review/memory.json")

        # Get high-risk files
        high_risk_files = memory.get_risk_files()

        if not high_risk_files:
            typer.echo("✅ No pending review warnings")
            return

        typer.echo("📋 High-risk files:")
        typer.echo("")

        for file_path in high_risk_files:
            file_memory = memory.get_file_memory(file_path)
            if file_memory:
                typer.echo(f"📁 {file_path} (risk: {file_memory.risk_score}/10)")
                for warning in file_memory.pending_warnings:
                    typer.echo(f"  🔴 {warning.rule_id}: {warning.last_message}")
            typer.echo("")

        typer.echo(f"Total: {len(high_risk_files)} high-risk files")

    except Exception as e:
        typer.echo(f"❌ Error getting status: {e}", err=True)
        raise typer.Exit(1)

@app.command()
def config_show():
    """Show current effective configuration."""
    try:
        config = resolve_config()

        typer.echo("🔧 Current AI Review Configuration:")
        typer.echo("")
        typer.echo(f"Mode: {config.mode}")
        typer.echo(f"LLM Backend: {config.llm.backend}")
        typer.echo(f"Model: {config.llm.ollama.model if config.llm.backend == 'ollama' else config.llm.openai_compatible.model}")
        typer.echo("")
        typer.echo(f"Memory Enabled: {config.memory.enabled}")
        typer.echo(f"Risk Threshold: {config.memory.risk_threshold}")
        typer.echo("")
        typer.echo("Pre-commit Hook:")
        typer.echo(f"  Block on: {config.hooks['pre_commit'].block_on}")
        typer.echo(f"  Timeout: {config.hooks['pre_commit'].timeout}s")
        typer.echo(f"  Context: {config.hooks['pre_commit'].context}")

    except FileNotFoundError:
        typer.echo("❌ No .ai-review.yaml found. Run 'ai-review init' first.")
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"❌ Error loading config: {e}", err=True)
        raise typer.Exit(1)

if __name__ == "__main__":
    app()