"""Prompt builder for assembling the final prompt from components."""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PromptContext:
    """Context for building the review prompt."""
    diff: str
    rules_prompt: str           # Formatted rules from rule engine
    context_text: str           # Formatted context from auto-collector (can be empty for fast screen)
    pending_warnings_text: str  # Memory reminders (can be empty)
    mode: str                   # "fast" or "full"


class PromptBuilder:
    """Assembles the final prompt from components."""

    def build(self, ctx: PromptContext) -> str:
        """Build the complete prompt string.

        For "fast" mode (pre-commit):
          - No context section
          - Only error severity rules
          - Focus on: CRITICAL/ERROR issues only
          - Ask for brief output

        For "full" mode (async review):
          - Full context section
          - All severity rules
          - Include pending warnings context for memory feedback
          - Ask for detailed output with rule IDs
        """
        if ctx.mode == "fast":
            return self._build_fast_mode_prompt(ctx)
        elif ctx.mode == "full":
            return self._build_full_mode_prompt(ctx)
        else:
            raise ValueError(f"Unknown mode: {ctx.mode}")

    def build_full(self, diff: str, rules_prompt: str,
                   context_text: str = "", pending_warnings_text: str = "") -> str:
        """Convenience method to build a full-mode prompt without PromptContext."""
        return self._build_full_mode_prompt(PromptContext(
            diff=diff,
            rules_prompt=rules_prompt,
            context_text=context_text,
            pending_warnings_text=pending_warnings_text,
            mode="full"
        ))

    def _build_fast_mode_prompt(self, ctx: PromptContext) -> str:
        """Build fast mode prompt for pre-commit checks."""
        rules_section = f"\n## 审查规范\n{ctx.rules_prompt}\n" if ctx.rules_prompt.strip() else ""

        return f"""你是一名严格的代码审查专家。请快速审查以下代码变更，只关注严重问题。
{rules_section}
## 代码变更
{ctx.diff}

## 输出要求（必须严格遵守）
请按以下JSON格式输出，不要输出其他内容：
```json
{{
  "status": "PASS" | "BLOCKING",
  "issues": [
    {{
      "severity": "CRITICAL" | "ERROR",
      "message": "问题描述",
      "file": "文件名",
      "line": 行号（数字，可选）,
      "bad_code": "有问题的原始代码片段",
      "fixed_code": "修复后的代码片段",
      "suggestion": "简要修复说明"
    }}
  ]
}}
```

注意：
- 只关注安全漏洞、凭证泄露、明显逻辑错误
- 不要报告风格问题或建议
- 如果没有严重问题，status 设为 PASS，issues 为空数组
- bad_code 必须是 diff 中实际出现的有问题代码
- fixed_code 必须是可以直接替换的修复代码
"""

    def _build_full_mode_prompt(self, ctx: PromptContext) -> str:
        """Build full mode prompt for detailed review."""
        sections = []

        if ctx.context_text:
            sections.append("## 项目结构")
            sections.append(ctx.context_text)

        if ctx.rules_prompt.strip():
            sections.append("## 审查规范")
            sections.append(ctx.rules_prompt)

        if ctx.pending_warnings_text:
            sections.append("## 历史审查警告")
            sections.append(ctx.pending_warnings_text)

        sections.append("## 代码变更")
        sections.append(ctx.diff)

        content = "\n".join(sections)

        return f"""你是一名资深的代码审查专家。请对以下代码变更进行全面审查，既指出问题，也认可好的实践。

{content}

## 输出要求（必须严格遵守）
请按以下JSON格式输出，不要输出其他内容：
```json
{{
  "status": "PASS" | "WARNING" | "BLOCKING",
  "summary": "一段话总结审查结论（50字以内）",
  "highlights": ["做得好的地方1", "做得好的地方2"],
  "issues": [
    {{
      "severity": "CRITICAL" | "ERROR" | "WARNING" | "INFO",
      "rule_id": "触发的规则ID（如有）",
      "message": "问题描述（说清楚为什么这是个问题）",
      "file": "文件名（如能识别）",
      "line": 行号（数字，如能识别）,
      "bad_code": "有问题的原始代码片段",
      "fixed_code": "修复后的完整代码片段",
      "suggestion": "修复说明"
    }}
  ]
}}
```

审查要求：
- status：严重错误/安全漏洞=BLOCKING，建议/风格问题=WARNING，无问题=PASS
- highlights：列出代码中做得好的实践（如错误处理完善、类型安全、命名清晰等），即使有问题也要认可优点
- issues 每条必须包含：
  - bad_code：从 diff 中提取的有问题代码片段（保持原始缩进）
  - fixed_code：可直接替换的修复代码（完整可用，不只是示意）
  - suggestion：用一句话解释为什么要这样改
- 如果没有任何问题，issues 为空数组，highlights 至少列一条
"""