"""Tests for diff_utils.truncate_diff — extreme condition coverage."""

import pytest
from ai_review.diff_utils import truncate_diff


# --- Helpers ---

def make_single_file_diff(filename: str, added_lines: int) -> str:
    """Generate a diff for a single file with N added lines."""
    lines = [f"diff --git a/{filename} b/{filename}"]
    lines.append(f"--- a/{filename}")
    lines.append(f"+++ b/{filename}")
    lines.append(f"@@ -0,0 +1,{added_lines} @@")
    for i in range(added_lines):
        lines.append(f"+line {i+1}: some code here with enough content to fill chars")
    return "\n".join(lines) + "\n"


def make_multi_file_diff(file_count: int, lines_per_file: int = 50) -> str:
    """Generate a diff with N files, each with M added lines."""
    parts = []
    for f in range(file_count):
        parts.append(make_single_file_diff(f"src/file_{f:03d}.py", lines_per_file))
    return "\n".join(parts)


def make_vue_diff(lines: int = 2000) -> str:
    """Simulate a large Vue SFC diff (template + script + style)."""
    sections = [
        ("template", 400),
        ("script setup", 800),
        ("style scoped", 600),
    ]
    parts = [f"diff --git a/views/Dashboard.vue b/views/Dashboard.vue"]
    parts.append("--- a/views/Dashboard.vue")
    parts.append("+++ b/views/Dashboard.vue")
    parts.append(f"@@ -0,0 +1,{lines} @@")

    remaining = lines
    for section_name, section_lines in sections:
        parts.append(f"+<{section_name}>")
        for i in range(min(section_lines, remaining)):
            parts.append(f"+  content line {i} of {section_name} with enough padding text here")
            remaining -= 1
            if remaining <= 0:
                break
        parts.append(f"+</{section_name}>")
        if remaining <= 0:
            break

    return "\n".join(parts) + "\n"


def make_mixed_diff(filename: str, total_lines: int) -> str:
    """Generate a diff with both additions and removals."""
    lines = [f"diff --git a/{filename} b/{filename}"]
    lines.append(f"--- a/{filename}")
    lines.append(f"+++ b/{filename}")
    lines.append(f"@@ -1,{total_lines//2} +1,{total_lines//2 + total_lines//4} @@")
    for i in range(total_lines):
        if i % 3 == 0:
            lines.append(f"-old line {i}")
        elif i % 3 == 1:
            lines.append(f"+new line {i} with code")
        else:
            lines.append(f" context line {i}")
    return "\n".join(lines) + "\n"


# --- Test: small diff passes through unchanged ---

class TestSmallDiff:
    def test_empty_diff(self):
        result = truncate_diff("")
        assert result.diff == ""
        assert not result.truncated

    def test_small_single_file(self):
        diff = make_single_file_diff("app.py", 10)
        result = truncate_diff(diff, max_lines=500, max_chars=30000)
        assert not result.truncated
        assert result.diff == diff

    def test_small_multi_file(self):
        diff = make_multi_file_diff(5, 20)
        result = truncate_diff(diff, max_lines=500, max_chars=30000)
        assert not result.truncated


# --- Test: large single file (the Vue case) ---

class TestLargeSingleFile:
    def test_vue_file_truncated_by_lines(self):
        """A 2000-line Vue diff should be truncated."""
        diff = make_vue_diff(2000)
        assert len(diff.splitlines()) > 500

        result = truncate_diff(diff, max_lines=500, max_chars=30000)
        assert result.truncated
        assert result.kept_lines <= 520
        assert result.original_lines > 1000

    def test_vue_file_fits_with_higher_limit(self):
        """Same Vue diff should pass with higher limits."""
        diff = make_vue_diff(200)
        result = truncate_diff(diff, max_lines=500, max_chars=30000)
        assert not result.truncated

    def test_single_file_very_large(self):
        """A single file with 10000 lines."""
        diff = make_single_file_diff("big_file.py", 10000)
        result = truncate_diff(diff, max_lines=500, max_chars=30000, max_files=20)
        assert result.truncated
        assert result.kept_lines < result.original_lines


# --- Test: sandwich truncation preserves head AND tail ---

class TestSandwichTruncation:
    def test_single_file_preserves_head_and_tail(self):
        """Sandwich truncation keeps both beginning and end of a file."""
        diff = make_single_file_diff("big.py", 1000)
        result = truncate_diff(diff, max_lines=200, max_chars=30000, max_files=20)
        assert result.truncated

        # Should contain early lines
        assert "line 1:" in result.diff
        assert "line 2:" in result.diff
        # Should contain late lines (tail)
        assert "line 1000:" in result.diff
        assert "line 999:" in result.diff
        # Should NOT contain middle lines
        assert "line 500:" not in result.diff

    def test_vue_sandwich_preserves_template_and_style(self):
        """Vue file: sandwich keeps template (head) and style (tail)."""
        diff = make_vue_diff(1500)
        result = truncate_diff(diff, max_lines=300, max_chars=30000, max_files=20)
        assert result.truncated

        # Head: template section
        assert "<template>" in result.diff
        # Tail: should contain closing tag or style content
        assert "style scoped" in result.diff or "</style" in result.diff
        # Should have truncation marker
        assert "省略了" in result.diff

    def test_mixed_diff_sandwich(self):
        """Mixed add/remove diff preserves both ends."""
        diff = make_mixed_diff("app.py", 800)
        result = truncate_diff(diff, max_lines=200, max_chars=30000, max_files=20)
        assert result.truncated
        # Should have early and late content
        assert "old line 0" in result.diff or "new line 1" in result.diff
        assert "line 799" in result.diff or "line 798" in result.diff

    def test_sandwich_summary_contains_counts(self):
        """Truncation note should contain add/remove counts."""
        diff = make_mixed_diff("app.py", 600)
        result = truncate_diff(diff, max_lines=150, max_chars=30000, max_files=20)
        # Summary should mention line counts
        assert "省略了" in result.diff or "lines" in result.diff.lower()


# --- Test: many files ---

class TestManyFiles:
    def test_50_files_truncated(self):
        """50 files should be truncated to max_files=20."""
        diff = make_multi_file_diff(50, 10)
        result = truncate_diff(diff, max_lines=500, max_chars=100000, max_files=20)
        assert result.truncated
        assert len(result.skipped_files) == 30
        assert "file_020" in result.skipped_files[0]
        assert "file_000" in result.diff
        assert "file_019" in result.diff
        # file_020's diff should not be in the main content (may appear in summary)
        assert "diff --git a/src/file_020" not in result.diff

    def test_exactly_max_files(self):
        """Exactly max_files should not be truncated."""
        diff = make_multi_file_diff(20, 10)
        result = truncate_diff(diff, max_lines=500, max_chars=100000, max_files=20)
        assert not result.truncated

    def test_skipped_files_have_summaries(self):
        """Skipped files should get summary info in the diff."""
        diff = make_multi_file_diff(30, 30)
        result = truncate_diff(diff, max_lines=2000, max_chars=100000, max_files=20)
        assert result.truncated
        assert len(result.skipped_files) == 10
        # Should have summaries
        assert result.skipped_file_summaries
        # Diff should mention skipped files
        assert "已跳过的文件" in result.diff

    def test_many_files_each_large(self):
        """30 files with 200 lines each."""
        diff = make_multi_file_diff(30, 200)
        result = truncate_diff(diff, max_lines=500, max_chars=30000, max_files=20)
        assert result.truncated
        assert len(result.skipped_files) == 10


# --- Test: character limit ---

class TestCharLimit:
    def test_hard_char_truncation(self):
        """Diff exceeding max_chars gets hard truncated."""
        diff = make_single_file_diff("huge.py", 1000)
        result = truncate_diff(diff, max_lines=5000, max_chars=5000, max_files=20)
        assert result.truncated
        assert len(result.diff) <= 5500

    def test_char_limit_does_not_apply_when_under(self):
        diff = make_single_file_diff("small.py", 5)
        result = truncate_diff(diff, max_lines=500, max_chars=30000, max_files=20)
        assert not result.truncated


# --- Test: edge cases ---

class TestEdgeCases:
    def test_no_diff_git_headers(self):
        """Diff with no 'diff --git' headers."""
        diff = "+line1\n+line2\n+line3\n"
        result = truncate_diff(diff, max_lines=500, max_chars=30000)
        assert result.diff

    def test_all_limits_zero(self):
        """Very aggressive limits."""
        diff = make_single_file_diff("test.py", 100)
        result = truncate_diff(diff, max_lines=1, max_chars=100, max_files=1)
        assert result.truncated
        assert len(result.diff) <= 200

    def test_unicode_content(self):
        """Chinese characters in diff."""
        lines = ["diff --git a/你好.py b/你好.py", "--- a/你好.py", "+++ b/你好.py", "@@ -1 +1 @@"]
        for i in range(100):
            lines.append(f"+第{i}行代码：一些中文内容在这里添加")
        diff = "\n".join(lines) + "\n"
        result = truncate_diff(diff, max_lines=50, max_chars=30000)
        assert result.truncated

    def test_mixed_add_remove(self):
        """Diff with both additions and removals."""
        diff = make_mixed_diff("app.py", 200)
        result = truncate_diff(diff, max_lines=100, max_chars=30000)
        assert result.truncated
        assert result.kept_lines < 200

    def test_per_file_budget_very_small(self):
        """When per-file budget is tiny (e.g. 1 file, 50 budget)."""
        diff = make_single_file_diff("big.py", 500)
        result = truncate_diff(diff, max_lines=50, max_chars=30000, max_files=20)
        assert result.truncated
        # Should still have content
        assert len(result.diff) > 100


# --- Test: pre-commit thresholds (simulating the CLI logic) ---

class TestPreCommitThresholds:
    def test_vue_file_pre_commit_limits(self):
        """A typical large Vue file should fit within pre-commit limits."""
        diff = make_vue_diff(300)
        result = truncate_diff(diff, max_lines=500, max_chars=30000, max_files=20)
        assert not result.truncated or result.kept_lines <= 500

    def test_massive_vue_file_pre_commit(self):
        """A huge Vue file (2000 lines changed) should be truncated for pre-commit."""
        diff = make_vue_diff(2000)
        result = truncate_diff(diff, max_lines=500, max_chars=30000, max_files=20)
        assert result.truncated
        assert "Dashboard.vue" in result.diff
        assert len(result.diff) > 1000

    def test_15_files_pre_commit(self):
        """15 files with moderate changes."""
        diff = make_multi_file_diff(15, 30)
        result = truncate_diff(diff, max_lines=500, max_chars=30000, max_files=20)
        assert not result.truncated

    def test_post_commit_higher_limits(self):
        """Post-commit should handle more with generous limits."""
        diff = make_multi_file_diff(30, 50)
        result = truncate_diff(diff, max_lines=2000, max_chars=100000, max_files=50)
        assert not result.truncated

    def test_post_commit_large_still_truncates(self):
        """Post-commit with truly huge diff should still truncate safely."""
        diff = make_multi_file_diff(40, 50)
        result = truncate_diff(diff, max_lines=2000, max_chars=100000, max_files=50)
        assert result.truncated
        assert result.kept_lines > 1000
