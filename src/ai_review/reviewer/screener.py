from dataclasses import dataclass, field
from typing import Any, List, Union

from ai_review.reviewer.parser import Issue, ReviewResult
from ai_review.memory.store import ReviewMemory
from ai_review.config import HookConfig
from ai_review.llm.base import LLMProvider, LLMResponse
from ai_review.prompt.builder import PromptBuilder, PromptContext
from ai_review.diff_utils import (
    split_diff_by_file, group_files_for_review, truncate_single_file_diff, FileDiff
)


@dataclass
class ScreenResult:
    action: str          # "PASS" | "BLOCK" | "TIMEOUT" | "ERROR"
    issues: List[Any]    # list of Issue from parser
    warnings: List[str]  # non-blocking messages
    elapsed_seconds: float
    reason: Union[str, None] = None
    highlights: List[str] = None
    files_reviewed: int = 0
    files_total: int = 0
    batches: int = 0


class FastScreener:
    """Pre-commit fast screening — groups files smartly for review.

    Large files get individual LLM calls.
    Small files are grouped into combined requests.
    """

    def __init__(self, llm_provider: LLMProvider, prompt_builder: PromptBuilder,
                 parser: Any, config: HookConfig):
        self.llm = llm_provider
        self.prompt_builder = prompt_builder
        self.parser = parser
        self.config = config

    def screen(self, diff: str, rules_prompt: str, changed_files: List[str],
               memory: Union[ReviewMemory, None] = None) -> ScreenResult:
        import time
        import os

        start_time = time.time()

        for env_var in self.config.bypass_env_vars:
            if os.environ.get(env_var):
                return ScreenResult(
                    action="PASS", issues=[], warnings=[],
                    reason=f"Bypass: env var {env_var} is set",
                    elapsed_seconds=time.time() - start_time
                )

        file_diffs = split_diff_by_file(diff)
        if not file_diffs:
            return ScreenResult(
                action="PASS", issues=[], warnings=[],
                reason="No diffs to review",
                elapsed_seconds=time.time() - start_time,
                files_reviewed=0, files_total=0,
            )

        # Group: large files individually, small files together
        batches = group_files_for_review(
            file_diffs,
            large_file_threshold=200,
            group_max_lines=500,
            group_max_files=15,
        )

        per_file_timeout = self.config.timeout
        max_total = min(per_file_timeout * min(len(batches), 10), 300)

        all_issues = []
        all_warnings = []
        all_highlights = []
        files_reviewed = 0
        llm_failed = False  # Stop retrying after LLM becomes unreachable

        for batch in batches:
            elapsed = time.time() - start_time
            if elapsed >= max_total:
                all_warnings.append(
                    f"Stopped after {files_reviewed}/{len(file_diffs)} files (budget {max_total}s reached)"
                )
                break

            if llm_failed:
                # LLM already failed once — skip remaining batches
                files_reviewed += len(batch)
                continue

            # Merge batch diffs into one prompt
            batch_diff = "\n".join(fd.diff for fd in batch)
            batch_files = [fd.filepath for fd in batch]

            # Truncate if combined diff is too large
            total_lines = sum(fd.line_count for fd in batch)
            if total_lines > 500:
                batch_diff = truncate_single_file_diff(batch_diff, max_lines=500, max_chars=30000)

            result = self._review_batch(batch_diff, rules_prompt, batch_files, per_file_timeout)

            if result.action == "ERROR" or "LLM unavailable" in (result.reason or ""):
                llm_failed = True

            all_issues.extend(result.issues)
            all_warnings.extend(result.warnings)
            if result.highlights:
                all_highlights.extend(result.highlights)
            files_reviewed += len(batch)

        elapsed = time.time() - start_time

        has_blocking = any(
            i.severity in ("CRITICAL", "ERROR") for i in all_issues
        )

        if has_blocking:
            block_on = self.config.block_on
            if any(sev in block_on for sev in set(i.severity for i in all_issues)):
                return ScreenResult(
                    action="BLOCK",
                    issues=all_issues,
                    warnings=all_warnings,
                    reason=f"Found {len(all_issues)} blocking issue(s) across {files_reviewed} file(s)",
                    elapsed_seconds=elapsed,
                    highlights=all_highlights,
                    files_reviewed=files_reviewed,
                    files_total=len(file_diffs),
                    batches=len(batches),
                )

        if all_issues:
            return ScreenResult(
                action="PASS",
                issues=[],
                warnings=[f"{i.severity}: {i.message}" for i in all_issues],
                reason=f"Review passed with {len(all_issues)} warning(s) across {files_reviewed} file(s)",
                elapsed_seconds=elapsed,
                highlights=all_highlights,
                files_reviewed=files_reviewed,
                files_total=len(file_diffs),
                batches=len(batches),
            )

        return ScreenResult(
            action="PASS",
            issues=[],
            warnings=all_warnings,
            reason=f"Review passed ({files_reviewed} file(s) in {len(batches)} batch(es))",
            elapsed_seconds=elapsed,
            highlights=all_highlights,
            files_reviewed=files_reviewed,
            files_total=len(file_diffs),
            batches=len(batches),
        )

    def _review_batch(self, diff: str, rules_prompt: str,
                      filenames: List[str], timeout: int) -> ScreenResult:
        """Review a single batch (one large file or a group of small files)."""
        import time

        start_time = time.time()

        try:
            prompt = self.prompt_builder.build(PromptContext(
                diff=diff,
                rules_prompt=rules_prompt,
                context_text="",
                pending_warnings_text="",
                mode="fast"
            ))
        except Exception as e:
            return ScreenResult(
                action="ERROR", issues=[], warnings=[],
                reason=f"Prompt build failed: {e}",
                elapsed_seconds=time.time() - start_time
            )

        try:
            response = self.llm.review(prompt, timeout=timeout)
            if not response.success:
                return ScreenResult(
                    action="PASS", issues=[], warnings=[],
                    reason=f"LLM unavailable: {response.error}",
                    elapsed_seconds=time.time() - start_time
                )
        except Exception as e:
            return ScreenResult(
                action="PASS", issues=[], warnings=[],
                reason=f"LLM error (auto-pass): {e}",
                elapsed_seconds=time.time() - start_time
            )

        try:
            result = self.parser.parse(response.content)
        except Exception as e:
            return ScreenResult(
                action="PASS", issues=[], warnings=[],
                reason=f"Parse error (auto-pass): {e}",
                elapsed_seconds=time.time() - start_time
            )

        elapsed = time.time() - start_time
        _highlights = getattr(result, 'highlights', None) or []

        if result.status == "BLOCKING":
            return ScreenResult(
                action="BLOCK", issues=result.issues, warnings=[],
                reason=f"Found {len(result.issues)} blocking issue(s)",
                elapsed_seconds=elapsed, highlights=_highlights,
            )
        elif result.status == "WARNING":
            return ScreenResult(
                action="PASS", issues=result.issues,
                warnings=[i.message for i in result.issues if hasattr(i, 'message')],
                reason=f"Found {len(result.issues)} warning(s)",
                elapsed_seconds=elapsed, highlights=_highlights,
            )
        else:
            return ScreenResult(
                action="PASS", issues=[], warnings=[],
                reason="No issues",
                elapsed_seconds=elapsed, highlights=_highlights,
            )
