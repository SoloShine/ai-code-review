"""
Diff collector utilities for git operations.

This module provides utilities to collect various types of git diffs
using subprocess calls to git commands.
"""

import subprocess
from typing import List, Optional


class DiffCollector:
    """Collects git diffs using subprocess calls to git commands."""

    def __init__(self, repo_root: str):
        """
        Initialize the diff collector.

        Args:
            repo_root: Path to the root of the git repository
        """
        self.repo_root = repo_root

    def get_staged_diff(self) -> str:
        """
        Get the staged diff using 'git diff --cached'.

        Returns:
            The staged diff as a string, or empty string on failure
        """
        return self._run_git_command(["git", "diff", "--cached"])

    def get_staged_files(self) -> List[str]:
        """
        Get list of staged files using 'git diff --cached --name-only --diff-filter=ACM'.

        Returns:
            List of staged file paths, or empty list on failure
        """
        result = self._run_git_command(["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"])
        if not result:
            return []
        return result.strip().split('\n') if result.strip() else []

    def get_branch_diff(self, base: str = "main") -> str:
        """
        Get diff between current branch and base branch using 'git diff {base}...HEAD'.

        Args:
            base: The base branch to compare against (default: "main")

        Returns:
            The branch diff as a string, or empty string on failure
        """
        return self._run_git_command(["git", "diff", f"{base}...HEAD"])

    def get_file_diff(self, file_path: str) -> str:
        """
        Get diff for a specific file using 'git diff HEAD -- {file_path}'.

        Args:
            file_path: Path to the file to get diff for

        Returns:
            The file diff as a string, or empty string on failure
        """
        return self._run_git_command(["git", "diff", "HEAD", "--", file_path])

    def get_diff_stats(self, files: List[str]) -> str:
        """
        Get diff stats for specified files using 'git diff --cached --stat -- {files}'.

        Args:
            files: List of file paths to get stats for

        Returns:
            The diff stats as a string, or empty string on failure
        """
        if not files:
            return ""
        cmd = ["git", "diff", "--cached", "--stat", "--"] + files
        return self._run_git_command(cmd)

    def get_recent_commits(self, files: List[str], limit: int = 5) -> str:
        """
        Get recent commits for specified files using 'git log -{limit} --oneline -- {files}'.

        Args:
            files: List of file paths to get commits for
            limit: Maximum number of commits to return (default: 5)

        Returns:
            The recent commits as a string, or empty string on failure
        """
        if not files:
            return ""
        cmd = ["git", f"-{limit}", "--oneline", "--"] + files
        return self._run_git_command(cmd)

    def get_commit_diff(self, commit_sha: str) -> str:
        """
        Get diff for a specific commit using 'git diff {sha}^ {sha}'.

        Args:
            commit_sha: The commit SHA to get diff for

        Returns:
            The commit diff as a string, or empty string on failure
        """
        return self._run_git_command(["git", "diff", f"{commit_sha}^", commit_sha])

    def _run_git_command(self, cmd: List[str]) -> str:
        """
        Run a git command using subprocess and return stdout.

        Args:
            cmd: The command to run as a list of strings

        Returns:
            The stdout output as a string, or empty string on failure
        """
        try:
            result = subprocess.run(
                cmd,
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                check=False
            )
            if result.returncode == 0:
                return result.stdout
            else:
                # Return empty string on failure, stderr can be logged if needed
                return ""
        except Exception:
            # Return empty string on any exception
            return ""