"""
File filter utilities for excluding files based on patterns.

This module provides utilities to filter files based on glob patterns,
both by basename and full path matching.
"""

import fnmatch
from typing import List, Tuple


class FileFilter:
    """Filters files based on exclusion patterns."""

    def __init__(self, exclude_patterns: List[str]):
        """
        Initialize the file filter.

        Args:
            exclude_patterns: List of glob patterns to exclude
                             (e.g., ["*.lock", "*.min.js", ".env*"])
        """
        self.exclude_patterns = exclude_patterns

    def filter(self, files: List[str]) -> Tuple[List[str], List[str]]:
        """
        Filter files based on exclusion patterns.

        Args:
            files: List of file paths to filter

        Returns:
            Tuple of (kept_files, skipped_files) where:
            - kept_files: Files that don't match any exclude pattern
            - skipped_files: Files that match at least one exclude pattern
        """
        kept = []
        skipped = []

        for file_path in files:
            if self._should_skip(file_path):
                skipped.append(file_path)
            else:
                kept.append(file_path)

        return kept, skipped

    def _should_skip(self, file_path: str) -> bool:
        """
        Determine if a file should be skipped based on exclusion patterns.

        Args:
            file_path: Path to the file to check

        Returns:
            True if the file should be skipped, False otherwise
        """
        # Check basename (last part of the path)
        basename = file_path.split('/')[-1] if '/' in file_path else file_path
        if self._matches_any_pattern(basename):
            return True

        # Check full path
        if self._matches_any_pattern(file_path):
            return True

        return False

    def _matches_any_pattern(self, text: str) -> bool:
        """
        Check if text matches any of the exclusion patterns.

        Args:
            text: Text to check against patterns

        Returns:
            True if text matches any pattern, False otherwise
        """
        for pattern in self.exclude_patterns:
            if fnmatch.fnmatch(text, pattern):
                return True
        return False

    def add_patterns(self, patterns: List[str]) -> None:
        """
        Add additional exclusion patterns.

        Args:
            patterns: List of glob patterns to add to exclusions
        """
        self.exclude_patterns.extend(patterns)

    def clear_patterns(self) -> None:
        """Clear all exclusion patterns."""
        self.exclude_patterns.clear()

    def set_patterns(self, patterns: List[str]) -> None:
        """
        Set new exclusion patterns, replacing existing ones.

        Args:
            patterns: List of glob patterns to set as exclusions
        """
        self.exclude_patterns = patterns.copy()