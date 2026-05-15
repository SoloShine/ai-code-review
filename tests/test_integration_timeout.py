"""Integration test: verify pre-commit path handles extreme inputs without hanging."""

import os
import sys
import subprocess
import tempfile
import time

import pytest


def _create_git_repo_with_diff(repo_dir: str, file_count: int, lines_per_file: int):
    """Create a git repo, add files, stage changes — ready for pre-commit test."""
    os.makedirs(repo_dir, exist_ok=True)
    subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo_dir, capture_output=True)

    # Create files
    for i in range(file_count):
        filepath = os.path.join(repo_dir, f"file_{i:03d}.py")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("# initial\n")
        subprocess.run(["git", "add", filepath], cwd=repo_dir, capture_output=True)

    subprocess.run(["git", "commit", "-m", "initial", "--no-verify"], cwd=repo_dir, capture_output=True)

    # Now modify all files — create large diffs
    for i in range(file_count):
        filepath = os.path.join(repo_dir, f"file_{i:03d}.py")
        with open(filepath, "w", encoding="utf-8") as f:
            for j in range(lines_per_file):
                f.write(f"x = {j}  # modified line\n")

    # Stage all changes
    subprocess.run(["git", "add", "-A"], cwd=repo_dir, capture_output=True)


def _create_large_vue_repo(repo_dir: str, vue_lines: int):
    """Create a git repo with a single large Vue file change."""
    os.makedirs(repo_dir, exist_ok=True)
    subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo_dir, capture_output=True)

    vue_path = os.path.join(repo_dir, "Dashboard.vue")
    with open(vue_path, "w") as f:
        f.write("<template><div>initial</div></template>\n")
    subprocess.run(["git", "add", vue_path], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial", "--no-verify"], cwd=repo_dir, capture_output=True)

    # Replace with a huge Vue file
    with open(vue_path, "w", encoding="utf-8") as f:
        f.write("<template>\n")
        for i in range(vue_lines // 3):
            f.write(f'  <div class="row-{i}">Content line {i}</div>\n')
        f.write("</template>\n\n")
        f.write("<script setup lang=\"ts\">\n")
        for i in range(vue_lines // 3):
            f.write(f"const item{i} = ref({i});\n")
        f.write("</script>\n\n")
        f.write("<style scoped>\n")
        for i in range(vue_lines // 3):
            f.write(f".row-{i} {{ padding: {i}px; }}\n")
        f.write("</style>\n")

    subprocess.run(["git", "add", vue_path], cwd=repo_dir, capture_output=True)


class TestPreCommitExtremeTimeout:
    """Verify that ai-review check --pre-commit completes quickly even with extreme diffs.

    These tests mock the LLM (it will fail to connect), but the critical thing
    is that the tool processes the diff, decides to auto-pass, and exits quickly.
    """

    def test_large_vue_file_completes_fast(self, tmp_path):
        """The case that caused the original timeout: single large Vue file."""
        repo_dir = str(tmp_path / "vue-repo")
        _create_large_vue_repo(repo_dir, vue_lines=2000)

        start = time.time()
        result = subprocess.run(
            [sys.executable, "-m", "ai_review.cli", "check", "--pre-commit"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout=30,  # if this hangs, the test will fail
            encoding="utf-8",
            errors="replace",
            env={**os.environ, "AI_REVIEW_MODE": "balanced"},
        )
        elapsed = time.time() - start

        # Should complete quickly (LLM will fail -> auto-pass)
        assert elapsed < 15, f"Pre-commit took {elapsed:.1f}s — too slow for LLM failure auto-pass"
        # Should auto-pass (LLM unreachable)
        assert "PASS" in (result.stdout or "") or "pass" in (result.stdout or "").lower() or result.returncode == 0

    def test_many_files_auto_passes(self, tmp_path):
        """30 files should auto-pass via file count threshold."""
        repo_dir = str(tmp_path / "many-files")
        _create_git_repo_with_diff(repo_dir, file_count=35, lines_per_file=20)

        start = time.time()
        result = subprocess.run(
            [sys.executable, "-m", "ai_review.cli", "check", "--pre-commit"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout=15,
            encoding="utf-8",
            errors="replace",
            env={**os.environ, "AI_REVIEW_MODE": "balanced"},
        )
        elapsed = time.time() - start

        # Should be nearly instant — no LLM call at all
        assert elapsed < 5, f"File threshold check took {elapsed:.1f}s"
        assert result.returncode == 0
        stdout = result.stdout or ""
        assert "Large changeset" in stdout or "skipping" in stdout.lower() or "threshold" in stdout.lower()

    def test_large_diff_truncated_and_completes(self, tmp_path):
        """10 files with 500 lines each — should be truncated, then auto-pass on LLM fail."""
        repo_dir = str(tmp_path / "large-diff")
        _create_git_repo_with_diff(repo_dir, file_count=10, lines_per_file=500)

        start = time.time()
        result = subprocess.run(
            [sys.executable, "-m", "ai_review.cli", "check", "--pre-commit", "--verbose"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout=30,
            encoding="utf-8",
            errors="replace",
            env={**os.environ, "AI_REVIEW_MODE": "balanced"},
        )
        elapsed = time.time() - start

        assert elapsed < 15, f"Large diff pre-commit took {elapsed:.1f}s"
        assert result.returncode == 0

    def test_single_small_file_normal_path(self, tmp_path):
        """Small change should go through normal path (LLM will fail -> auto-pass)."""
        repo_dir = str(tmp_path / "small-change")
        _create_git_repo_with_diff(repo_dir, file_count=1, lines_per_file=10)

        result = subprocess.run(
            [sys.executable, "-m", "ai_review.cli", "check", "--pre-commit"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout=30,
            encoding="utf-8",
            errors="replace",
            env={**os.environ, "AI_REVIEW_MODE": "balanced"},
        )

        # Should attempt LLM call (will fail) and auto-pass
        assert result.returncode == 0
