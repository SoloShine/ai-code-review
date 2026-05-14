from dataclasses import dataclass
from typing import Any, List, Union
import os
import time
import json
from pathlib import Path

from ai_review.reviewer.parser import Issue
from ai_review.memory.store import ReviewMemory
from ai_review.config import HookConfig
from ai_review.llm.base import LLMProvider
from ai_review.prompt.builder import PromptBuilder
from ai_review.context.auto import AutoContextCollector
from ai_review.rules.loader import RuleEngine
from ai_review.output.notify import SystemNotifier


@dataclass
class AsyncReviewResult:
    status: str            # PASS / WARNING / BLOCKING
    issues: list           # list of Issue
    file_warnings: dict    # {file_path: [Issue]}
    summary: str
    report_path: Union[str, None]


class AsyncReviewer:
    """Post-commit async reviewer - full review with context"""

    def __init__(self, llm_provider: LLMProvider, prompt_builder: PromptBuilder,
                 parser: Any, context_collector: AutoContextCollector,
                 rule_engine: RuleEngine, memory: ReviewMemory, config: HookConfig):
        self.llm = llm_provider
        self.prompt_builder = prompt_builder
        self.parser = parser
        self.context_collector = context_collector
        self.rule_engine = rule_engine
        self.memory = memory
        self.config = config
        self.notifier = SystemNotifier()
        self.reports_dir = Path(".ai-review/reports")
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def review(self, commit_sha: str, changed_files: list[str],
               diff: str) -> AsyncReviewResult:
        """
        1. Collect context (AutoContextCollector)
        2. Match rules for changed files (all severities)
        3. Get pending warnings from memory for context
        4. Build full-mode prompt
        5. Call LLM (longer timeout, 120s)
        6. Parse result
        7. Record warnings in memory
        8. Save report to .ai-review/reports/
        9. Send system notification
        10. Return result
        """
        start_time = time.time()

        # 1. Collect context
        try:
            context = self.context_collector.collect(changed_files)
        except Exception as e:
            print(f"Warning: Context collection failed: {str(e)}")
            context = {}

        # 2. Match rules for changed files (all severities)
        rule_matches = {}
        try:
            matched_rules = self.rule_engine.match(changed_files)
            for file_path in changed_files:
                file_rules = [rule for rule in matched_rules if rule.applies_to.matches_file(file_path)]
                if file_rules:
                    rule_matches[file_path] = file_rules
        except Exception as e:
            print(f"Warning: Rule matching failed: {str(e)}")

        # 3. Get pending warnings from memory for context
        memory_warnings = {}
        try:
            for file_path in changed_files:
                file_memory = self.memory.get_file_memory(file_path)
                if file_memory and file_memory.pending_warnings:
                    memory_warnings[file_path] = [w.last_message for w in file_memory.pending_warnings]
        except Exception as e:
            print(f"Warning: Memory retrieval failed: {str(e)}")

        # 4. Build full-mode prompt
        try:
            from ai_review.prompt.builder import PromptContext
            full_prompt = self.prompt_builder.build(PromptContext(
                diff=diff,
                rules_prompt=self._build_rules_prompt(rule_matches),
                context_text="",
                pending_warnings_text="",
                mode="full"
            ))
        except Exception as e:
            return AsyncReviewResult(
                status="ERROR",
                issues=[],
                file_warnings={},
                summary=f"Prompt building failed: {str(e)}",
                report_path=None
            )

        # 5. Call LLM (longer timeout, 120s)
        try:
            response = self.llm.review(
                prompt=full_prompt,
                timeout=120  # Longer timeout for full review
            )

            # 6. Parse result
            parsed_result = self.parser.parse(response)

            # Parse issues into Issue objects
            issues = parsed_result.issues

            # Group warnings by file
            file_warnings = {}
            for issue in issues:
                if issue.severity in ['WARNING', 'INFO']:  # Non-blocking issues
                    if issue.file_path not in file_warnings:
                        file_warnings[issue.file_path] = []
                    file_warnings[issue.file_path].append(issue)

            # Determine overall status
            if any(issue.severity == 'BLOCKING' for issue in issues):
                status = "BLOCKING"
            elif any(issue.severity == 'WARNING' for issue in issues):
                status = "WARNING"
            else:
                status = "PASS"

            summary = parsed_result.get('summary', 'Review completed successfully')

            # 7. Record warnings in memory
            try:
                for file_path, warnings in file_warnings.items():
                    warning_dicts = [{'rule_id': 'generic', 'message': w.message} for w in warnings]
                    self.memory.record_warnings(file_path, warning_dicts)
            except Exception as e:
                print(f"Warning: Memory recording failed: {str(e)}")

            # 8. Save report to .ai-review/reports/
            report_path = None
            try:
                report_filename = f"review_{commit_sha}_{int(time.time())}.json"
                report_path = self.reports_dir / report_filename
                report_data = {
                    'commit_sha': commit_sha,
                    'timestamp': time.time(),
                    'status': status,
                    'summary': summary,
                    'issues': issues,
                    'file_warnings': file_warnings,
                    'context': context
                }
                with open(report_path, 'w') as f:
                    json.dump(report_data, f, indent=2)
            except Exception as e:
                print(f"Warning: Report saving failed: {str(e)}")
                report_path = None

            # 9. Send system notification
            try:
                if status == "BLOCKING":
                    self.notifier.notify(
                        title="AI Review: BLOCKING Issues",
                        message=f"Found blocking issues in commit {commit_sha[:8]}. Summary: {summary}"
                    )
                elif status == "WARNING":
                    self.notifier.notify(
                        title="AI Review: Warnings",
                        message=f"Found warnings in commit {commit_sha[:8]}. Summary: {summary}"
                    )
                else:
                    self.notifier.notify(
                        title="AI Review: Passed",
                        message=f"Review passed for commit {commit_sha[:8]}. Summary: {summary}"
                    )
            except Exception as e:
                print(f"Warning: Notification failed: {str(e)}")

            # 10. Return result
            return AsyncReviewResult(
                status=status,
                issues=issues,
                file_warnings=file_warnings,
                summary=summary,
                report_path=str(report_path) if report_path else None
            )

        except Exception as e:
            return AsyncReviewResult(
                status="ERROR",
                issues=[],
                file_warnings={},
                summary=f"Review failed: {str(e)}",
                report_path=None
            )

    def _build_rules_prompt(self, rule_matches: dict) -> str:
        """Build the rules prompt from matched rules"""
        if not rule_matches:
            return "No specific rules matched for the changed files."

        rules_text = []
        for file_path, rules in rule_matches.items():
            rules_text.append(f"\nFile: {file_path}")
            for rule in rules:
                rules_text.append(f"  - {rule['name']}: {rule['description']}")

        return "\n".join(rules_text)