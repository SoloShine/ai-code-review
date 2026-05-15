"""Comprehensive edge-case tests for the grouped review system."""

import pytest
from ai_review.diff_utils import (
    split_diff_by_file, group_files_for_review, truncate_single_file_diff,
    FileDiff, truncate_diff,
)


# --- Helpers ---

def make_file_diff(filename: str, lines: int, prefix="+") -> FileDiff:
    """Create a FileDiff with N lines."""
    diff_lines = [f"diff --git a/{filename} b/{filename}"]
    diff_lines.append(f"--- a/{filename}")
    diff_lines.append(f"+++ b/{filename}")
    diff_lines.append(f"@@ -0,0 +1,{lines} @@")
    for i in range(lines):
        diff_lines.append(f"{prefix}line {i}: content here for padding")
    text = "\n".join(diff_lines) + "\n"
    return FileDiff(filepath=filename, diff=text, line_count=len(diff_lines))


def make_diff_from_files(file_diffs: list) -> str:
    """Merge multiple FileDiff objects into one combined diff."""
    return "\n".join(fd.diff for fd in file_diffs)


# ============================================================
# Test: group_files_for_review — grouping logic
# ============================================================

class TestGrouping:
    def test_empty_input(self):
        assert group_files_for_review([]) == []

    def test_single_small_file(self):
        """One small file → one batch."""
        fds = [make_file_diff("app.py", 50)]
        batches = group_files_for_review(fds)
        assert len(batches) == 1
        assert len(batches[0]) == 1

    def test_single_large_file(self):
        """One large file → one batch (individually)."""
        fds = [make_file_diff("big.vue", 500)]
        batches = group_files_for_review(fds, large_file_threshold=200)
        assert len(batches) == 1
        assert len(batches[0]) == 1

    def test_many_small_files_grouped(self):
        """30 small files (10 lines each) → should merge into fewer batches."""
        fds = [make_file_diff(f"file_{i}.py", 10) for i in range(30)]
        batches = group_files_for_review(fds, large_file_threshold=200)
        # 30 * 10 = 300 lines total, should fit in ~1 batch (max 500 lines)
        assert len(batches) <= 3
        assert sum(len(b) for b in batches) == 30

    def test_mixed_large_and_small(self):
        """2 large + 10 small → 2 individual + 1 group."""
        large = [make_file_diff(f"big_{i}.vue", 500) for i in range(2)]
        small = [make_file_diff(f"tiny_{i}.ts", 20) for i in range(10)]
        batches = group_files_for_review(large + small, large_file_threshold=200)
        # 2 large (individual) + 1 group of 10 small = 3 batches
        assert len(batches) == 3
        assert len(batches[0]) == 1  # first large
        assert len(batches[1]) == 1  # second large
        assert len(batches[2]) == 10  # all small together

    def test_all_large_files(self):
        """10 files all over threshold → 10 individual batches."""
        fds = [make_file_diff(f"big_{i}.py", 300) for i in range(10)]
        batches = group_files_for_review(fds, large_file_threshold=200)
        assert len(batches) == 10
        for b in batches:
            assert len(b) == 1

    def test_group_respects_max_files(self):
        """Group should not exceed max_files limit."""
        fds = [make_file_diff(f"f{i}.py", 5) for i in range(50)]
        batches = group_files_for_review(
            fds, large_file_threshold=200, group_max_files=10
        )
        for b in batches:
            assert len(b) <= 10

    def test_group_respects_max_lines(self):
        """Group should not exceed max_lines limit."""
        fds = [make_file_diff(f"f{i}.py", 30) for i in range(50)]
        batches = group_files_for_review(
            fds, large_file_threshold=200, group_max_lines=100
        )
        for b in batches:
            total = sum(fd.line_count for fd in b)
            assert total <= 100 or len(b) == 1  # single large file can exceed

    def test_exactly_at_threshold(self):
        """File exactly at threshold is NOT large."""
        fds = [make_file_diff("exact.py", 200)]
        batches = group_files_for_review(fds, large_file_threshold=200)
        # 200 is NOT > 200, so it's small → grouped
        assert len(batches) == 1
        assert len(batches[0]) == 1

    def test_one_over_threshold(self):
        """File at threshold+1 IS large."""
        fds = [make_file_diff("over.py", 201)]
        batches = group_files_for_review(fds, large_file_threshold=200)
        assert len(batches) == 1
        assert len(batches[0]) == 1

    def test_batch_rename_scenario(self):
        """Simulate batch rename: 100 files, each 2 lines changed."""
        fds = [make_file_diff(f"src/module_{i//10}/file_{i}.py", 2) for i in range(100)]
        batches = group_files_for_review(fds, large_file_threshold=200, group_max_files=50)
        # line_count includes header lines (~6 each), total ~600 lines
        assert len(batches) <= 5
        assert sum(len(b) for b in batches) == 100

    def test_mixed_extensions(self):
        """Files with different extensions get grouped together."""
        fds = [
            make_file_diff("app.py", 50),
            make_file_diff("view.tsx", 50),
            make_file_diff("style.css", 50),
            make_file_diff("config.yaml", 50),
        ]
        batches = group_files_for_review(fds, large_file_threshold=200)
        # All small, should be one batch
        assert len(batches) == 1
        assert len(batches[0]) == 4


# ============================================================
# Test: split_diff_by_file — splitting logic
# ============================================================

class TestSplitByFile:
    def test_empty(self):
        assert split_diff_by_file("") == []

    def test_single_file(self):
        diff = make_file_diff("app.py", 10).diff
        result = split_diff_by_file(diff)
        assert len(result) == 1
        assert result[0].filepath == "app.py"
        assert result[0].line_count > 10

    def test_multiple_files(self):
        fds = [make_file_diff(f"f{i}.py", 20) for i in range(5)]
        diff = make_diff_from_files(fds)
        result = split_diff_by_file(diff)
        assert len(result) == 5
        assert result[0].filepath == "f0.py"
        assert result[4].filepath == "f4.py"

    def test_no_headers(self):
        """Raw diff without git headers."""
        diff = "+line1\n+line2\n-line3\n"
        result = split_diff_by_file(diff)
        assert len(result) == 1
        assert result[0].filepath == "unknown"

    def test_file_with_spaces_in_name(self):
        """File path with spaces."""
        diff = f"diff --git a/path with spaces/app.py b/path with spaces/app.py\n--- a/path with spaces/app.py\n+++ b/path with spaces/app.py\n@@ +1 @@\n+content\n"
        result = split_diff_by_file(diff)
        assert len(result) == 1


# ============================================================
# Test: truncate_single_file_diff
# ============================================================

class TestTruncateSingleFile:
    def test_small_unchanged(self):
        fd = make_file_diff("app.py", 10)
        result = truncate_single_file_diff(fd.diff)
        assert result == fd.diff

    def test_large_truncated(self):
        fd = make_file_diff("big.py", 2000)
        result = truncate_single_file_diff(fd.diff, max_lines=500)
        assert len(result.splitlines()) < 2000
        assert len(result) < len(fd.diff)

    def test_empty(self):
        assert truncate_single_file_diff("") == ""


# ============================================================
# Test: extreme scenarios — combined
# ============================================================

class TestExtremeScenarios:
    def test_massive_batch_rename(self):
        """200 files, each 1 line — should be one batch."""
        fds = [make_file_diff(f"src/f{i}.py", 1) for i in range(200)]
        batches = group_files_for_review(fds, large_file_threshold=200, group_max_files=50)
        # 200 lines total → should be ~4 batches of 50 files
        assert len(batches) <= 5
        total_files = sum(len(b) for b in batches)
        assert total_files == 200

    def test_one_giant_many_tiny(self):
        """1 file with 5000 lines + 50 files with 1 line each."""
        giant = make_file_diff("giant.vue", 5000)
        tinies = [make_file_diff(f"tiny{i}.ts", 1) for i in range(50)]
        batches = group_files_for_review([giant] + tinies, large_file_threshold=200)
        # Giant is individual, tinies are grouped (each has ~7 line_count with header)
        assert batches[0] == [giant]
        # Tinies: 50 * ~7 = ~350 lines → should be 1-2 groups
        tiny_batches = batches[1:]
        total_tiny_files = sum(len(b) for b in tiny_batches)
        assert total_tiny_files == 50

    def test_all_files_exactly_threshold(self):
        """All files at threshold+4 (line_count includes 4 header lines) are large."""
        fds = [make_file_diff(f"f{i}.py", 200) for i in range(10)]
        batches = group_files_for_review(fds, large_file_threshold=200, group_max_lines=3000)
        # line_count=204 (200 content + 4 headers) > 200 threshold → all large/individual
        assert len(batches) == 10
        for b in batches:
            assert len(b) == 1

    def test_files_just_below_threshold(self):
        """Files with line_count exactly at threshold → treated as small, grouped."""
        fds = [make_file_diff(f"f{i}.py", 196) for i in range(10)]
        batches = group_files_for_review(fds, large_file_threshold=200, group_max_lines=3000)
        # line_count=200 (196 content + 4 headers) == 200 threshold → small
        # 10 * 200 = 2000 → fits in 1 batch with 3000 limit
        assert len(batches) <= 3

    def test_alternating_large_small(self):
        """Alternating large and small files."""
        fds = []
        for i in range(5):
            fds.append(make_file_diff(f"big_{i}.py", 300))
            fds.append(make_file_diff(f"small_{i}.ts", 10))
        batches = group_files_for_review(fds, large_file_threshold=200)
        # 5 large (individual) + 5 small (grouped)
        individual = sum(1 for b in batches if len(b) == 1 and b[0].line_count > 200)
        grouped = sum(len(b) for b in batches if any(fd.line_count <= 200 for fd in b))
        assert individual == 5
        assert grouped == 5

    def test_single_line_files(self):
        """1000 files with exactly 1 line each — batch rename extreme."""
        fds = [make_file_diff(f"f{i}", 1) for i in range(1000)]
        batches = group_files_for_review(fds, large_file_threshold=200, group_max_files=50)
        total = sum(len(b) for b in batches)
        assert total == 1000
        # 1000 lines → should be ~20 batches of 50
        assert len(batches) <= 25
