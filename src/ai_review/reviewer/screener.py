from dataclasses import dataclass
from typing import Any, List, Union

from ai_review.reviewer.parser import Issue, ReviewResult
from ai_review.memory.store import ReviewMemory
from ai_review.config import HookConfig
from ai_review.llm.base import LLMProvider, LLMResponse
from ai_review.prompt.builder import PromptBuilder, PromptContext


@dataclass
class ScreenResult:
    action: str          # "PASS" | "BLOCK" | "TIMEOUT" | "ERROR"
    issues: List[Any]    # list of Issue from parser
    warnings: List[str]  # non-blocking messages
    elapsed_seconds: float
    reason: Union[str, None] = None
    highlights: List[str] = None  # positive feedback from LLM


class FastScreener:
    """Pre-commit fast screening - seconds-level, only catches critical issues"""

    def __init__(self, llm_provider: LLMProvider, prompt_builder: PromptBuilder,
                 parser: Any, config: HookConfig):
        self.llm = llm_provider
        self.prompt_builder = prompt_builder
        self.parser = parser
        self.config = config  # HookConfig for pre_commit

    def screen(self, diff: str, rules_prompt: str, changed_files: List[str],
               memory: Union[ReviewMemory, None] = None) -> ScreenResult:
        import time
        import os

        start_time = time.time()

        # 1. Check bypass patterns
        bypass_patterns = self.config.bypass_message_patterns
        for env_var in self.config.bypass_env_vars:
            if os.environ.get(env_var):
                return ScreenResult(
                    action="PASS", issues=[], warnings=[],
                    reason=f"Bypass: env var {env_var} is set",
                    elapsed_seconds=time.time() - start_time
                )

        # 2. Build fast-mode prompt
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

        # 3. Call LLM with timeout
        try:
            timeout = self.config.timeout
            response = self.llm.review(prompt, timeout=timeout)

            if not response.success:
                # LLM call failed - don't block the commit
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

        # 4. Parse LLM output
        try:
            result: ReviewResult = self.parser.parse(response.content)
        except Exception as e:
            return ScreenResult(
                action="PASS", issues=[], warnings=[],
                reason=f"Parse error (auto-pass): {e}",
                elapsed_seconds=time.time() - start_time
            )

        elapsed = time.time() - start_time

        # 5. Decide action based on result status and config
        _highlights = getattr(result, 'highlights', None) or []

        if result.status == "BLOCKING":
            if "BLOCKING" in self.config.block_on or "ERROR" in self.config.block_on:
                return ScreenResult(
                    action="BLOCK",
                    issues=result.issues,
                    warnings=[],
                    reason=f"Found {len(result.issues)} blocking issue(s)",
                    elapsed_seconds=elapsed,
                    highlights=_highlights
                )
            else:
                return ScreenResult(
                    action="PASS",
                    issues=result.issues,
                    warnings=["Blocking issues found but configured to pass"],
                    elapsed_seconds=elapsed,
                    highlights=_highlights
                )
        elif result.status == "WARNING":
            return ScreenResult(
                action="PASS",
                issues=[],
                warnings=[i.message for i in result.issues if hasattr(i, 'message')],
                reason=f"Review passed with {len(result.issues)} warning(s)",
                elapsed_seconds=elapsed,
                highlights=_highlights
            )
        else:
            return ScreenResult(
                action="PASS",
                issues=[],
                warnings=[],
                reason="Review passed",
                elapsed_seconds=elapsed,
                highlights=_highlights
            )
