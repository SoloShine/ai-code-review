"""
Rule loader for AI code review rules.

This module handles loading and managing code review rules from YAML and Markdown files.
"""

import os
import glob
import yaml
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from pathlib import Path


@dataclass
class AppliesTo:
    """File matching criteria for a rule."""
    extensions: List[str]
    paths: Optional[List[str]] = None

    def matches_file(self, file_path: str) -> bool:
        """Check if a file path matches this rule's criteria."""
        file_ext = Path(file_path).suffix.lower()

        # Check file extension
        if file_ext not in self.extensions:
            return False

        # Check path patterns if provided
        if self.paths:
            file_path_normalized = os.path.normpath(file_path)
            for pattern in self.paths:
                # Convert glob pattern to regex-like matching
                if self._matches_pattern(file_path_normalized, pattern):
                    return True
            return False

        return True

    def _matches_pattern(self, file_path: str, pattern: str) -> bool:
        """Check if file path matches a glob pattern."""
        pattern_normalized = os.path.normpath(pattern)
        file_path_lower = file_path.lower()
        pattern_lower = pattern.lower()

        # Simple glob matching - can be enhanced with proper glob library if needed
        if pattern.startswith('./'):
            pattern = pattern[2:]
        if pattern.startswith('**/'):
            pattern = pattern[3:]

        # Convert glob patterns to regex-like matching
        pattern_regex = pattern.replace('*', '.*').replace('?', '.').replace('[', '[').replace(']', ']')
        pattern_regex = f'.*{pattern_regex}.*'

        import re
        return re.match(pattern_regex, file_path_lower) is not None


@dataclass
class Rule:
    """A single code review rule."""
    id: str
    title: str
    severity: str  # "critical", "error", "warning", "info"
    enabled: bool
    applies_to: AppliesTo
    description: str
    bad_example: Optional[str] = None
    good_example: Optional[str] = None

    def __post_init__(self):
        """Validate the rule after initialization."""
        if self.severity not in ["critical", "error", "warning", "info"]:
            raise ValueError(f"Invalid severity: {self.severity}. Must be 'critical', 'error', 'warning', or 'info'")


class RuleEngine:
    """Manages loading and matching of code review rules."""

    def __init__(self, rules_dirs: List[str]):
        """Initialize the rule engine with directories containing rule files."""
        self.rules_dirs = rules_dirs
        self.rules: List[Rule] = []
        self._load_all_rules()

    def _load_all_rules(self) -> None:
        """Load rules from all configured directories."""
        self.rules = []

        for rules_dir in self.rules_dirs:
            if not os.path.exists(rules_dir):
                continue

            self._load_from_dir(rules_dir)

    def _load_from_dir(self, dir_path: str) -> None:
        """Load rules from a single directory."""
        # Load YAML files
        yaml_files = glob.glob(os.path.join(dir_path, "*.yaml")) + glob.glob(os.path.join(dir_path, "*.yml"))

        for yaml_file in yaml_files:
            try:
                with open(yaml_file, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)

                    if not data or 'rules' not in data:
                        continue

                    rule_list = data['rules']
                    if not isinstance(rule_list, list):
                        continue

                    for rule_data in rule_list:
                        rule = self._parse_rule(rule_data, os.path.basename(yaml_file))
                        if rule:
                            self.rules.append(rule)

            except Exception as e:
                print(f"Warning: Failed to load YAML file {yaml_file}: {e}")

        # Load Markdown files as single rules
        md_files = glob.glob(os.path.join(dir_path, "*.md"))

        for md_file in md_files:
            try:
                rule = self._load_markdown(md_file)
                if rule:
                    self.rules.append(rule)

            except Exception as e:
                print(f"Warning: Failed to load Markdown file {md_file}: {e}")

    def _parse_rule(self, rule_data: Dict[str, Any], source_file: str) -> Optional[Rule]:
        """Parse a single rule from YAML data."""
        try:
            # Extract required fields
            rule_id = rule_data.get('id')
            title = rule_data.get('title')
            severity = rule_data.get('severity', 'warning')
            enabled = rule_data.get('enabled', True)
            description = rule_data.get('description', '')
            bad_example = rule_data.get('bad_example')
            good_example = rule_data.get('good_example')

            if not rule_id or not title:
                return None

            # Parse applies_to section
            applies_to_data = rule_data.get('applies_to', {})
            extensions = applies_to_data.get('extensions', [])
            paths = applies_to_data.get('paths')

            applies_to = AppliesTo(extensions=extensions, paths=paths)

            return Rule(
                id=rule_id,
                title=title,
                severity=severity,
                enabled=enabled,
                applies_to=applies_to,
                description=description,
                bad_example=bad_example,
                good_example=good_example
            )

        except Exception as e:
            print(f"Warning: Failed to parse rule from {source_file}: {e}")
            return None

    def _load_markdown(self, file_path: str) -> Optional[Rule]:
        """Load a Markdown file as a single rule."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()

            if not content:
                return None

            # Extract rule ID from filename
            rule_id = Path(file_path).stem

            return Rule(
                id=rule_id,
                title=rule_id.replace('_', ' ').title(),
                severity="warning",  # Default severity for markdown rules
                enabled=True,
                applies_to=AppliesTo(extensions=[".md"]),  # Markdown files only by default
                description=content,
                bad_example=None,
                good_example=None
            )

        except Exception as e:
            print(f"Warning: Failed to load markdown file {file_path}: {e}")
            return None

    def match(self, changed_files: List[str], severity_filter: Optional[List[str]] = None) -> List[Rule]:
        """
        Return rules that match any of the changed files, optionally filtered by severity.

        Args:
            changed_files: List of file paths that have changed
            severity_filter: Optional list of severities to include (e.g., ["error", "warning"])

        Returns:
            List of matching rules, sorted by severity and title
        """
        matching_rules = []

        for rule in self.rules:
            # Skip disabled rules
            if not rule.enabled:
                continue

            # Skip rules that don't match severity filter
            if severity_filter:
                rule_sev = rule.severity.lower()
                if rule_sev not in severity_filter:
                    # "error" filter also matches "critical" (critical >= error)
                    if not (rule_sev == "critical" and "error" in severity_filter):
                        continue

            # Check if rule matches any changed file
            for file_path in changed_files:
                if rule.applies_to.matches_file(file_path):
                    matching_rules.append(rule)
                    break  # Rule matches, no need to check other files

        # Sort rules: errors first, then warnings, then info; then by title
        def sort_key(rule):
            severity_order = {"critical": 0, "error": 1, "warning": 2, "info": 3}
            return (severity_order.get(rule.severity, 999), rule.title.lower())

        return sorted(matching_rules, key=sort_key)

    def _file_matches(self, file_path: str, applies_to: AppliesTo) -> bool:
        """Check if a file path matches the applies_to criteria."""
        return applies_to.matches_file(file_path)

    def format_for_prompt(self, rules: List[Rule]) -> str:
        """Format rules for use in a prompt, delegating to the formatter."""
        from .formatter import format_rules_for_prompt
        return format_rules_for_prompt(rules)