"""
Rule formatter for AI code review rules.

This module handles formatting rules for various output formats including prompts and reports.
"""

from typing import List
from .loader import Rule


def format_rules_for_prompt(rules: List[Rule]) -> str:
    """
    Format matched rules as a markdown prompt section for AI code review.

    Args:
        rules: List of rules to format

    Returns:
        Formatted markdown string ready for inclusion in a prompt
    """
    if not rules:
        return "No specific rules matched for these files. Apply general code quality standards."

    formatted_rules = []

    for rule in rules:
        # Create severity tag
        severity_tag = f"[{rule.severity.upper()}]"

        # Format the rule
        rule_text = f"### {severity_tag} {rule.title}\n\n"
        rule_text += f"{rule.description}\n\n"

        # Add bad example if provided
        if rule.bad_example:
            rule_text += "**Bad Example:**\n"
            rule_text += f"```{rule.id}\n"
            rule_text += f"{rule.bad_example.strip()}\n"
            rule_text += "```\n\n"

        # Add good example if provided
        if rule.good_example:
            rule_text += "**Good Example:**\n"
            rule_text += f"```{rule.id}\n"
            rule_text += f"{rule.good_example.strip()}\n"
            rule_text += "```\n\n"

        # Add file type information
        if rule.applies_to.extensions:
            if len(rule.applies_to.extensions) == 1:
                rule_text += f"**Applies to:** {rule.applies_to.extensions[0]}\n\n"
            else:
                rule_text += f"**Applies to:** {', '.join(rule.applies_to.extensions)}\n\n"

        # Add path patterns if specified
        if rule.applies_to.paths:
            if len(rule.applies_to.paths) == 1:
                rule_text += f"**Location:** {rule.applies_to.paths[0]}\n\n"
            else:
                rule_text += f"**Locations:** {', '.join(rule.applies_to.paths)}\n\n"

        formatted_rules.append(rule_text)

    # Join all rules with separator
    result = "\n---\n\n".join(formatted_rules)

    return result


def format_rules_for_json(rules: List[Rule]) -> str:
    """
    Format rules as JSON string for API consumption.

    Args:
        rules: List of rules to format

    Returns:
        JSON string representation of the rules
    """
    import json

    rule_data = []
    for rule in rules:
        rule_dict = {
            "id": rule.id,
            "title": rule.title,
            "severity": rule.severity,
            "enabled": rule.enabled,
            "description": rule.description,
            "applies_to": {
                "extensions": rule.applies_to.extensions,
                "paths": rule.applies_to.paths
            }
        }

        if rule.bad_example is not None:
            rule_dict["bad_example"] = rule.bad_example

        if rule.good_example is not None:
            rule_dict["good_example"] = rule.good_example

        rule_data.append(rule_dict)

    return json.dumps(rule_data, indent=2)


def format_rules_for_cli(rules: List[Rule]) -> str:
    """
    Format rules for CLI output.

    Args:
        rules: List of rules to format

    Returns:
        CLI-friendly formatted string
    """
    if not rules:
        return "No rules matched."

    formatted_rules = []

    # Header
    formatted_rules.append("Matched Rules:")
    formatted_rules.append("=" * 50)

    for rule in rules:
        # Severity and title
        severity_icon = {
            "critical": "🛑",
            "error": "❌",
            "warning": "⚠️",
            "info": "ℹ️"
        }.get(rule.severity, "❓")

        formatted_rules.append(f"{severity_icon} [{rule.severity.upper()}] {rule.title}")
        formatted_rules.append(f"    ID: {rule.id}")
        formatted_rules.append(f"    Description: {rule.description}")

        if rule.bad_example:
            # Truncate bad example for CLI display
            bad_example_truncated = rule.bad_example.strip()
            if len(bad_example_truncated) > 100:
                bad_example_truncated = bad_example_truncated[:100] + "..."
            formatted_rules.append(f"    Bad Example: {bad_example_truncated}")

        if rule.good_example:
            # Truncate good example for CLI display
            good_example_truncated = rule.good_example.strip()
            if len(good_example_truncated) > 100:
                good_example_truncated = good_example_truncated[:100] + "..."
            formatted_rules.append(f"    Good Example: {good_example_truncated}")

        # Apply info
        if rule.applies_to.extensions:
            ext_info = ", ".join(rule.applies_to.extensions)
            formatted_rules.append(f"    Extensions: {ext_info}")

        if rule.applies_to.paths:
            path_info = ", ".join(rule.applies_to.paths)
            formatted_rules.append(f"    Paths: {path_info}")

        formatted_rules.append("")  # Empty line between rules

    return "\n".join(formatted_rules)


def format_rules_for_html(rules: List[Rule]) -> str:
    """
    Format rules for HTML output.

    Args:
        rules: List of rules to format

    Returns:
        HTML string representation of the rules
    """
    if not rules:
        return "<p>No rules matched.</p>"

    html_parts = []

    # Header
    html_parts.append("<div class='ai-code-review-rules'>")
    html_parts.append("<h2>Matched Rules</h2>")

    for rule in rules:
        # Severity-based styling
        severity_class = f"severity-{rule.severity}"
        rule_html = f"""
        <div class='rule {severity_class}'>
            <div class='rule-header'>
                <span class='severity-badge {severity_class}'>{rule.severity.upper()}</span>
                <h3>{rule.title}</h3>
            </div>
            <div class='rule-content'>
                <p class='description'>{rule.description}</p>
        """

        # Bad example
        if rule.bad_example:
            rule_html += f"""
                <div class='example bad-example'>
                    <h4>Bad Example:</h4>
                    <pre><code>{rule.bad_example.strip()}</code></pre>
                </div>
            """

        # Good example
        if rule.good_example:
            rule_html += f"""
                <div class='example good-example'>
                    <h4>Good Example:</h4>
                    <pre><code>{rule.good_example.strip()}</code></pre>
                </div>
            """

        # Apply info
        if rule.applies_to.extensions or rule.applies_to.paths:
            rule_html += "<div class='applies-to'>"

            if rule.applies_to.extensions:
                ext_text = ", ".join(rule.applies_to.extensions)
                rule_html += f"<span><strong>Extensions:</strong> {ext_text}</span>"

            if rule.applies_to.paths:
                path_text = ", ".join(rule.applies_to.paths)
                rule_html += f"<span><strong>Paths:</strong> {path_text}</span>"

            rule_html += "</div>"

        rule_html += "</div></div>"
        html_parts.append(rule_html)

    html_parts.append("</div>")

    # Add basic CSS
    css = """
    <style>
    .ai-code-review-rules {
        font-family: Arial, sans-serif;
        line-height: 1.6;
    }
    .rule {
        border: 1px solid #ddd;
        border-radius: 8px;
        margin-bottom: 20px;
        overflow: hidden;
    }
    .rule-header {
        background-color: #f5f5f5;
        padding: 12px;
        border-bottom: 1px solid #ddd;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .severity-badge {
        padding: 4px 8px;
        border-radius: 4px;
        font-weight: bold;
        font-size: 0.8em;
        text-transform: uppercase;
    }
    .severity-error { background-color: #ffebee; color: #c62828; }
    .severity-warning { background-color: #fff3e0; color: #ef6c00; }
    .severity-info { background-color: #e3f2fd; color: #1565c0; }
    .rule-content {
        padding: 16px;
    }
    .description {
        margin-bottom: 16px;
    }
    .example {
        margin-bottom: 16px;
    }
    .example h4 {
        margin-bottom: 8px;
        color: #333;
    }
    .example pre {
        background-color: #f8f9fa;
        border: 1px solid #e9ecef;
        border-radius: 4px;
        padding: 12px;
        overflow-x: auto;
    }
    .example code {
        font-family: 'Courier New', monospace;
        font-size: 14px;
    }
    .applies-to {
        margin-top: 16px;
        font-size: 0.9em;
        color: #666;
    }
    .applies-to span {
        margin-right: 16px;
    }
    </style>
    """

    return css + "\n".join(html_parts)