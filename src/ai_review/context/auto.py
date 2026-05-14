"""
AutoContextCollector - Collects basic context without language-specific analysis.
"""

import os
import subprocess
import json
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime


@dataclass
class AutoContext:
    file_tree: str          # Project directory tree (2 levels deep)
    git_log: str            # Recent commits related to changed files
    diff_stats: str         # Stats of the current diff
    nearby_files: List[str] # Files in same directory as changed files


class AutoContextCollector:
    """
    Collects basic context information for AI code review.
    Provides foundational context without language-specific analysis.
    """

    def __init__(self, repo_root: str):
        """
        Initialize the context collector.

        Args:
            repo_root: Root path of the git repository
        """
        self.repo_root = repo_root

    def collect(self, changed_files: List[str]) -> AutoContext:
        """
        Collect all context information for the given changed files.

        Args:
            changed_files: List of file paths that have been changed

        Returns:
            AutoContext object containing all collected information
        """
        return AutoContext(
            file_tree=self._get_file_tree(),
            git_log=self._get_related_commits(changed_files),
            diff_stats=self._get_diff_stats(changed_files),
            nearby_files=self._get_nearby_files(changed_files)
        )

    def _get_file_tree(self, depth: int = 2) -> str:
        """
        Get project file tree structure with specified depth.
        Excludes common build/dist directories.

        Args:
            depth: Maximum depth for the file tree

        Returns:
            Formatted string representation of the file tree
        """
        try:
            # Build the find command with exclusions
            exclude_patterns = [
                "*/node_modules/*",
                "*/.git/*",
                "*/bin/*",
                "*/obj/*",
                "*/dist/*",
                "*/build/*",
                "*/.vs/*",
                "*/vendor/*"
            ]

            find_cmd = ["find", ".", "-maxdepth", str(depth), "-type", "f"]

            # Add exclusions
            for pattern in exclude_patterns:
                find_cmd.extend(["-not", "-path", pattern])

            result = subprocess.run(
                find_cmd,
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                return "Error getting file tree"

            # Format the output
            files = result.stdout.strip().split('\n') if result.stdout.strip() else []
            formatted_files = [f"./{f}" for f in files if f]

            # Group by directory
            tree_structure = {}
            for file_path in formatted_files:
                parts = file_path.split('/')
                directory = '/'.join(parts[:depth])
                if directory not in tree_structure:
                    tree_structure[directory] = []
                tree_structure[directory].append(parts[-1])

            # Build formatted tree
            tree_lines = ["# Project File Tree", ""]
            for directory, files in sorted(tree_structure.items()):
                tree_lines.append(f"📁 {directory}/")
                for file in sorted(files):
                    tree_lines.append(f"  📄 {file}")

            return '\n'.join(tree_lines)

        except Exception as e:
            return f"Error getting file tree: {str(e)}"

    def _get_related_commits(self, files: List[str], limit: int = 5) -> str:
        """
        Get recent git commits related to the specified files.

        Args:
            files: List of file paths to get commits for
            limit: Maximum number of commits to return

        Returns:
            Formatted string of recent commits
        """
        if not files:
            return "No files specified for commit history"

        try:
            # Build git log command
            git_cmd = ["git", "log", f"--oneline", f"-{limit}", "--"]
            git_cmd.extend(files)

            result = subprocess.run(
                git_cmd,
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                return "Error getting commit history"

            if not result.stdout.strip():
                return "No recent commits for these files"

            # Format the output
            commits = result.stdout.strip().split('\n')
            formatted_commits = ["# Recent Commits", ""]

            for commit in commits:
                if commit.strip():
                    formatted_commits.append(f"• {commit.strip()}")

            return '\n'.join(formatted_commits)

        except Exception as e:
            return f"Error getting commit history: {str(e)}"

    def _get_diff_stats(self, files: List[str]) -> str:
        """
        Get diff statistics for the current changes.

        Args:
            files: List of file paths to get diff stats for

        Returns:
            Formatted string of diff statistics
        """
        if not files:
            return "No files specified for diff stats"

        try:
            # Build git diff command
            git_cmd = ["git", "diff", "--cached", "--stat"]
            git_cmd.extend(files)

            result = subprocess.run(
                git_cmd,
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                return "Error getting diff stats"

            if not result.stdout.strip():
                return "No staged changes"

            # Format the output
            stats_lines = ["# Current Changes (Staged)", ""]
            stats_lines.append(result.stdout.strip())

            return '\n'.join(stats_lines)

        except Exception as e:
            return f"Error getting diff stats: {str(e)}"

    def _get_nearby_files(self, changed_files: List[str], max_files: int = 20) -> List[str]:
        """
        Get files in the same directories as changed files, excluding the changed files themselves.

        Args:
            changed_files: List of file paths that have been changed
            max_files: Maximum number of nearby files to return

        Returns:
            List of nearby file paths
        """
        if not changed_files:
            return []

        try:
            # Get directories containing changed files
            directories = set()
            for file_path in changed_files:
                abs_path = os.path.join(self.repo_root, file_path)
                if os.path.exists(abs_path):
                    directory = os.path.dirname(abs_path)
                    directories.add(directory)

            nearby_files = []
            for directory in directories:
                try:
                    # Get files in the directory (excluding node_modules, .git, etc.)
                    for root, dirs, files in os.walk(directory):
                        # Skip excluded directories
                        dirs[:] = [d for d in dirs if not any(
                            d.startswith(exclude) or exclude in d
                            for exclude in ['.git', 'node_modules', 'bin', 'obj', 'dist', 'build', '.vs', 'vendor']
                        )]

                        for file in files:
                            file_path = os.path.relpath(os.path.join(root, file), self.repo_root)
                            if file_path not in changed_files and file_path not in nearby_files:
                                nearby_files.append(file_path)

                        # Stop at shallow depth
                        if len(os.path.relpath(root, self.repo_root).split(os.sep)) > 2:
                            break

                except (OSError, PermissionError):
                    continue  # Skip directories we can't access

            # Limit and return
            return nearby_files[:max_files]

        except Exception as e:
            print(f"Error getting nearby files: {str(e)}")
            return []

    def format_for_prompt(self, context: AutoContext) -> str:
        """
        Format collected context as a markdown section for prompt injection.

        Args:
            context: AutoContext object to format

        Returns:
            Formatted markdown string
        """
        sections = [
            "## 📋 Project Context\n",
            f"**Collected at:** {datetime.now().isoformat()}\n",
            "---\n",
            context.file_tree,
            "\n---\n",
            context.git_log,
            "\n---\n",
            context.diff_stats,
            "\n---\n",
            "### 📁 Nearby Files\n",
            "\n".join(f"• {file}" for file in context.nearby_files[:10]),
            f"\n*(Showing first 10 of {len(context.nearby_files)} nearby files)*" if len(context.nearby_files) > 10 else ""
        ]

        return '\n'.join(sections)