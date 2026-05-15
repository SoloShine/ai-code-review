"""Prompt builder for assembling the final prompt from components."""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Prompt section budgets (chars)
CONTEXT_BUDGET = 4000
RULES_BUDGET = 6000
WARNINGS_BUDGET = 1500
DIFF_HARD_LIMIT = 15000


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
        """Build full mode prompt with smart budget allocation."""
        sections = []

        # Context: truncate at line boundaries
        if ctx.context_text:
            context = _truncate_at_lines(ctx.context_text, CONTEXT_BUDGET)
            sections.append("## 项目结构")
            sections.append(context)

        # Rules: truncate at rule boundaries (split by '---')
        if ctx.rules_prompt.strip():
            rules = _truncate_rules(ctx.rules_prompt, RULES_BUDGET)
            sections.append("## 审查规范")
            sections.append(rules)

        # Warnings: simple truncation
        if ctx.pending_warnings_text:
            warnings = _truncate_at_lines(ctx.pending_warnings_text, WARNINGS_BUDGET)
            sections.append("## 历史审查警告")
            sections.append(warnings)

        # Diff: hard limit as safety net (should already be truncated by caller)
        diff = ctx.diff
        if len(diff) > DIFF_HARD_LIMIT:
            diff = diff[:DIFF_HARD_LIMIT] + "\n... (代码变更已截断)"

        sections.append("## 代码变更")
        sections.append(diff)

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


def _truncate_at_lines(text: str, budget: int) -> str:
    """Truncate text at line boundaries to fit within budget."""
    if len(text) <= budget:
        return text

    lines = text.splitlines()
    result = []
    total = 0
    for line in lines:
        if total + len(line) + 1 > budget - 50:
            break
        result.append(line)
        total += len(line) + 1

    result.append(f"... (已截断，保留前 {len(result)}/{len(lines)} 行)")
    return "\n".join(result)


def _truncate_rules(rules_text: str, budget: int) -> str:
    """Truncate rules at rule boundaries (split by '---').

    Keeps complete rules, never cuts mid-rule.
    Prioritizes rules by severity: critical > error > warning > info.
    """
    if len(rules_text) <= budget:
        return rules_text

    # Split into individual rule blocks
    rule_blocks = rules_text.split("\n---\n")
    if not rule_blocks:
        return rules_text[:budget]

    # Sort by severity (critical first, then error, then warning, then info)
    def severity_rank(block: str) -> int:
        lower = block.lower()
        if "[critical]" in lower:
            return 0
        if "[error]" in lower:
            return 1
        if "[warning]" in lower:
            return 2
        return 3

    rule_blocks.sort(key=severity_rank)

    # Add rules until budget is exhausted
    kept = []
    total = 0
    for block in rule_blocks:
        needed = len(block) + 5  # 5 for "\n---\n"
        if total + needed > budget:
            break
        kept.append(block)
        total += needed

    if not kept:
        # Even one rule exceeds budget — keep first rule truncated
        return rule_blocks[0][:budget]

    dropped = len(rule_blocks) - len(kept)
    result = "\n---\n".join(kept)
    if dropped > 0:
        result += f"\n\n... (已省略 {dropped} 条优先级较低的规则)"
    return result
