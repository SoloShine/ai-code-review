"""Parser for converting LLM output into structured review results."""

import json
import logging
import re
from dataclasses import dataclass
from typing import Optional, List, Tuple

logger = logging.getLogger(__name__)


@dataclass
class Issue:
    """Represents a single issue found in the code review."""
    severity: str          # CRITICAL / ERROR / WARNING / INFO
    rule_id: Optional[str]  # If mentioned in output
    file: Optional[str]    # If mentioned
    line: Optional[int]   # If mentioned
    message: str
    suggestion: Optional[str]
    bad_code: Optional[str] = None
    fixed_code: Optional[str] = None


@dataclass
class ReviewResult:
    """Structured result of a code review."""
    status: str            # PASS / WARNING / BLOCKING
    issues: List[Issue]
    summary: str           # First paragraph of LLM output
    highlights: List[str]  # Positive aspects noted by LLM
    raw_output: str        # Full LLM output for report


class ReviewParser:
    """Parses LLM output into structured results.

    Strategy:
    1. Try to extract JSON from the output (primary)
    2. Fall back to text-based parsing if JSON fails
    """

    def parse(self, llm_output: str) -> ReviewResult:
        """Parse LLM output into structured ReviewResult."""
        if not llm_output or not llm_output.strip():
            return ReviewResult(status="PASS", issues=[], summary="", highlights=[], raw_output="")

        # Try JSON parsing first
        result = self._try_json_parse(llm_output)
        if result:
            return result

        # Fall back to text-based parsing
        logger.info("JSON parse failed, falling back to text parsing")
        cleaned_output = self._clean_output(llm_output)
        status = self._detect_status(cleaned_output)
        issues = self._parse_issues_text(cleaned_output)
        summary = self._extract_summary(cleaned_output)

        return ReviewResult(
            status=status,
            issues=issues,
            summary=summary,
            highlights=[],
            raw_output=llm_output
        )

    def _try_json_parse(self, output: str) -> Optional[ReviewResult]:
        """Try to extract and parse JSON from LLM output."""
        json_str = self._extract_json(output)
        if not json_str:
            return None

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            return None

        # Validate required fields
        if not isinstance(data, dict) or "status" not in data:
            return None

        status = data.get("status", "PASS").upper()
        if status not in ("PASS", "WARNING", "BLOCKING"):
            status = "PASS"

        issues = []
        for item in data.get("issues", []):
            if not isinstance(item, dict):
                continue
            issue = Issue(
                severity=item.get("severity", "WARNING").upper(),
                rule_id=item.get("rule_id"),
                file=item.get("file"),
                line=self._safe_int(item.get("line")),
                message=item.get("message", ""),
                suggestion=item.get("suggestion"),
                bad_code=item.get("bad_code"),
                fixed_code=item.get("fixed_code"),
            )
            if issue.message:
                issues.append(issue)

        summary = data.get("summary", "")
        highlights = data.get("highlights", [])
        if isinstance(highlights, str):
            highlights = [highlights]

        logger.debug("JSON parse success: status=%s, issues=%d, highlights=%d",
                     status, len(issues), len(highlights))
        return ReviewResult(
            status=status,
            issues=issues,
            summary=summary,
            highlights=highlights,
            raw_output=output
        )

    def _extract_json(self, output: str) -> Optional[str]:
        """Extract JSON string from output, handling markdown code blocks."""
        # Try to find JSON in markdown code block
        match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', output, re.DOTALL)
        if match:
            return match.group(1).strip()

        # Try to find raw JSON object
        match = re.search(r'\{[^{}]*"status"[^{}]*\}', output, re.DOTALL)
        if match:
            return match.group(0)

        # Try the entire output if it looks like JSON
        stripped = output.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            return stripped

        return None

    def _safe_int(self, value) -> Optional[int]:
        """Safely convert a value to int."""
        if value is None:
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    def _clean_output(self, output: str) -> str:
        """Clean the LLM output for text-based parsing."""
        output = re.sub(r'```.*?```', '', output, flags=re.DOTALL)
        output = re.sub(r'^[\"\']|[\"\']$', '', output.strip())
        return output

    def _detect_status(self, output: str) -> str:
        """Detect the review status from the output."""
        lines = output.strip().split('\n')
        if not lines:
            return "WARNING"

        first_line = lines[0].upper().strip()

        # Check first line for explicit status
        if 'BLOCKING' in first_line or '❌' in first_line:
            return "BLOCKING"
        elif 'WARNING' in first_line or '⚠️' in first_line:
            return "WARNING"
        elif 'PASS' in first_line or '✅' in first_line:
            return "PASS"

        # Check entire output for blocking issues
        if 'BLOCKING' in output.upper() or '❌' in output:
            return "BLOCKING"

        # Default based on content
        if self._contains_issues(output):
            return "WARNING"
        else:
            return "PASS"

    def _contains_issues(self, output: str) -> bool:
        """Check if output contains any issues."""
        # Look for common issue indicators
        issue_indicators = [
            r'问题|问题|issue|problem|error|错误|warning|警告',
            r'[🛑🔴🟡🟢ℹ️]',  # emoji markers
            r'\[.*?\]',  # rule IDs in brackets
            r'建议|建议|suggestion|recommendation|fix|修复|改正'
        ]

        for pattern in issue_indicators:
            if re.search(pattern, output):
                return True
        return False

    def _parse_issues_text(self, output: str) -> List[Issue]:
        """Parse individual issues from the output."""
        issues = []

        # Look for emoji markers
        emoji_issues = self._parse_emoji_issues(output)
        issues.extend(emoji_issues)

        # Look for bracketed rule IDs
        rule_id_issues = self._parse_rule_id_issues(output)
        issues.extend(rule_id_issues)

        # Look for numbered/bulleted issues
        numbered_issues = self._parse_numbered_issues(output)
        issues.extend(numbered_issues)

        # If no structured issues found, try to extract from plain text
        if not issues and self._contains_issues(output):
            issues = self._parse_plain_text_issues(output)

        return issues

    def _parse_emoji_issues(self, output: str) -> List[Issue]:
        """Parse issues marked with severity emojis."""
        emoji_map = {
            '🛑': 'CRITICAL',
            '🔴': 'ERROR',
            '🟡': 'WARNING',
            '🟢': 'INFO',
            'ℹ️': 'INFO'
        }

        issues = []
        patterns = [
            r'(🛑|🔴|🟡|🟢|ℹ️)\s*(.*?)(?=(🛑|🔴|🟡|🟢|ℹ️|$))',
            r'(🛑|🔴|🟡|🟢|ℹ️)[\s\n]*(.*?)(?=(🛑|🔴|🟡|🟢|ℹ️|[\n\n]))'
        ]

        for pattern in patterns:
            matches = re.finditer(pattern, output, re.DOTALL)
            for match in matches:
                emoji, text = match.group(1), match.group(2).strip()
                if emoji in emoji_map:
                    severity = emoji_map[emoji]
                    message, suggestion = self._extract_message_and_suggestion(text)
                    issues.append(Issue(
                        severity=severity,
                        rule_id=None,
                        file=self._extract_file(text),
                        line=self._extract_line(text),
                        message=message,
                        suggestion=suggestion
                    ))

        return issues

    def _parse_rule_id_issues(self, output: str) -> List[Issue]:
        """Parse issues with rule IDs in brackets."""
        issues = []
        pattern = r'\[([^\]]+)\][\s\n]*(.*?)(?=(\[[^\]]+\]|$))'

        matches = re.finditer(pattern, output, re.DOTALL)
        for match in matches:
            rule_id, text = match.group(1), match.group(2).strip()
            message, suggestion = self._extract_message_and_suggestion(text)
            issues.append(Issue(
                severity=self._estimate_severity(text, rule_id),
                rule_id=rule_id,
                file=self._extract_file(text),
                line=self._extract_line(text),
                message=message,
                suggestion=suggestion
            ))

        return issues

    def _parse_numbered_issues(self, output: str) -> List[Issue]:
        """Parse numbered issues."""
        issues = []
        pattern = r'^\s*(\d+)[\.\)]\s*(.*?)(?=(\d+[\.\)]|$))'

        matches = re.finditer(pattern, output, re.MULTILINE)
        for match in matches:
            text = match.group(2).strip()
            if text and len(text) > 10:  # Filter out very short entries
                message, suggestion = self._extract_message_and_suggestion(text)
                issues.append(Issue(
                    severity=self._estimate_severity(text),
                    rule_id=None,
                    file=self._extract_file(text),
                    line=self._extract_line(text),
                    message=message,
                    suggestion=suggestion
                ))

        return issues

    def _parse_plain_text_issues(self, output: str) -> List[Issue]:
        """Parse issues from plain text when no structured format is found."""
        issues = []
        # Split by common delimiters
        sections = re.split(r'\n\s*\n', output)

        for section in sections:
            section = section.strip()
            if section and len(section) > 20:  # Reasonable length for an issue
                # Skip the status line
                if section.upper().startswith(('BLOCKING', 'WARNING', 'PASS', '✅', '⚠️', '❌')):
                    continue

                message, suggestion = self._extract_message_and_suggestion(section)
                if message:
                    issues.append(Issue(
                        severity=self._estimate_severity(section),
                        rule_id=None,
                        file=self._extract_file(section),
                        line=self._extract_line(section),
                        message=message,
                        suggestion=suggestion
                    ))

        return issues

    def _extract_message_and_suggestion(self, text: str) -> Tuple[str, Optional[str]]:
        """Extract message and suggestion from text."""
        # Split by common suggestion indicators
        suggestion_patterns = [
            r'建议[:：]\s*(.*?)(?=\n|$)',
            r'suggestion[:：]\s*(.*?)(?=\n|$)',
            r'修复[:：]\s*(.*?)(?=\n|$)',
            r'fix[:：]\s*(.*?)(?=\n|$)',
            r'改正[:：]\s*(.*?)(?=\n|$)',
        ]

        suggestion = None
        for pattern in suggestion_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                suggestion = match.group(1).strip()
                break

        # Message is the text before suggestion indicators
        for pattern in suggestion_patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)

        # Clean up the message
        message = text.strip()
        if message.startswith('- '):
            message = message[2:].strip()

        return message, suggestion

    def _extract_file(self, text: str) -> Optional[str]:
        """Extract file path from text."""
        # Look for file patterns
        patterns = [
            r'[/\\]?[\w\-\.]+(?:\.py|\.js|\.ts|\.java|\.cpp|\.c|\.go|\.rs|\.rb|\.php)(?:[:：]\d+)?',
            r'`?[\w\-\./\\\\]+\.(?:py|js|ts|java|cpp|c|go|rs|rb|php)`?',
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                file_path = match.group(0)
                # Clean up markdown formatting
                file_path = file_path.strip('`')
                return file_path

        return None

    def _extract_line(self, text: str) -> Optional[int]:
        """Extract line number from text."""
        # Look for line number patterns
        patterns = [
            r':(\d+)',
            r'第\s*(\d+)\s*行',
            r'line\s*(\d+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    return int(match.group(1))
                except ValueError:
                    continue

        return None

    def _estimate_severity(self, text: str, rule_id: Optional[str] = None) -> str:
        """Estimate severity based on text content."""
        text_lower = text.lower()

        # Critical indicators
        critical_keywords = [
            '安全漏洞', 'security', 'vulnerability', '漏洞',
            '凭证泄露', 'credential', '泄露', 'exposure',
            'inject', 'injection', 'xss', 'csrf', 'sql injection',
            'memory leak', 'buffer overflow', 'crash', '崩溃'
        ]

        for keyword in critical_keywords:
            if keyword in text_lower:
                return "CRITICAL"

        # Error indicators
        error_keywords = [
            'error', '错误', 'exception', '异常', 'fail', 'failed',
            'bug', '缺陷', '逻辑错误', 'logic error',
            'type error', '类型错误'
        ]

        for keyword in error_keywords:
            if keyword in text_lower:
                return "ERROR"

        # Warning indicators
        warning_keywords = [
            'warning', '警告', '注意', 'caution',
            'deprecated', '弃用', 'todo', 'fixme',
            'performance', '性能', '优化', 'optimize'
        ]

        for keyword in warning_keywords:
            if keyword in text_lower:
                return "WARNING"

        # Default to INFO
        return "INFO"

    def _extract_summary(self, output: str) -> str:
        """Extract summary from the first paragraph."""
        # Split into paragraphs
        paragraphs = re.split(r'\n\s*\n', output.strip())

        if paragraphs:
            # Clean up the first paragraph
            summary = paragraphs[0].strip()
            # Remove status indicators
            summary = re.sub(r'^(BLOCKING|WARNING|PASS|✅|⚠️|❌)[:：]?\s*', '', summary, flags=re.IGNORECASE)
            return summary

        return ""