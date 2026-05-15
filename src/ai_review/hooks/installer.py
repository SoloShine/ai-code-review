"""
Git Hook Installer - Installs pre-commit and post-commit hooks for ai-review
"""
import os
import shutil
import subprocess
import stat
import sys
from pathlib import Path


def _resolve_git_dir(repo_root: str) -> str:
    """Resolve the actual .git directory, handling submodules and worktrees.

    In a normal repo, .git is a directory.
    In a submodule or worktree, .git is a file containing 'gitdir: <path>'.
    Falls back to `git rev-parse --git-dir` for edge cases.
    """
    git_path = os.path.join(repo_root, ".git")

    # Normal repo: .git is a directory
    if os.path.isdir(git_path):
        return git_path

    # Submodule / worktree: .git is a file pointing to the real git dir
    if os.path.isfile(git_path):
        try:
            content = Path(git_path).read_text(encoding="utf-8").strip()
            if content.startswith("gitdir:"):
                real_git_dir = content[len("gitdir:"):].strip()
                if not os.path.isabs(real_git_dir):
                    real_git_dir = os.path.join(repo_root, real_git_dir)
                real_git_dir = os.path.normpath(real_git_dir)
                if os.path.isdir(real_git_dir):
                    return real_git_dir
        except Exception:
            pass

    # Last resort: ask git
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=repo_root, capture_output=True, text=True, encoding="utf-8"
        )
        if result.returncode == 0:
            git_dir = result.stdout.strip()
            if not os.path.isabs(git_dir):
                git_dir = os.path.join(repo_root, git_dir)
            git_dir = os.path.normpath(git_dir)
            if os.path.isdir(git_dir):
                return git_dir
    except Exception:
        pass

    raise FileNotFoundError(
        f"Cannot resolve .git directory in {repo_root}. "
        "Ensure this is a Git repository."
    )


def _find_ai_review_cmd() -> str:
    """Find the full path to the ai-review command."""
    # 1. Try the current Python's Scripts directory (where pip installs entry points)
    python_dir = os.path.dirname(sys.executable)
    if os.name == 'nt':
        candidates = [
            os.path.join(python_dir, "ai-review.exe"),
            os.path.join(python_dir, "ai-review.cmd"),
            os.path.join(python_dir, "Scripts", "ai-review.exe"),
        ]
    else:
        candidates = [
            os.path.join(python_dir, "ai-review"),
            os.path.join(python_dir, "bin", "ai-review"),
        ]

    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate.replace("\\", "/")

    # 2. Try shutil.which
    which_result = shutil.which("ai-review")
    if which_result:
        return which_result.replace("\\", "/")

    # 3. Fallback: use python -m (works everywhere)
    return f"{sys.executable.replace(chr(92), '/')} -m ai_review.cli"


class HookInstaller:
    def __init__(self, repo_root: str):
        self.repo_root = repo_root
        self.git_dir = _resolve_git_dir(repo_root)
        self.hooks_dir = os.path.join(self.git_dir, "hooks")

    def _build_hook_scripts(self) -> dict:
        """Build hook scripts with the resolved command path."""
        cmd = _find_ai_review_cmd()

        # Check if cmd is a simple path or needs shell invocation
        if " " in cmd:
            # e.g. "python.exe -m ai_review.cli" — use as-is
            invoke = cmd
        else:
            invoke = cmd

        return {
            "pre-commit": f"""#!/bin/sh
# ai-review pre-commit hook
{invoke} check --pre-commit
exit $?
""",
            "post-commit": f"""#!/bin/sh
# ai-review post-commit hook - async review
COMMIT_SHA=$(git rev-parse HEAD)
({invoke} check --async --commit "$COMMIT_SHA" > /dev/null 2>&1 &)
""",
        }

    def install(self):
        """Install pre-commit and post-commit hooks"""
        os.makedirs(self.hooks_dir, exist_ok=True)

        hook_scripts = self._build_hook_scripts()

        for hook_name in hook_scripts:
            self._install_hook(hook_name, hook_scripts[hook_name])

        print(f"✅ Git hooks installed to {self.hooks_dir}")

    def _install_hook(self, hook_name: str, new_content: str):
        """Install a single hook, preserving existing content."""
        hook_path = os.path.join(self.hooks_dir, hook_name)

        if os.path.exists(hook_path):
            with open(hook_path, 'r', encoding="utf-8") as f:
                existing = f.read()

            if "ai-review" in existing:
                # Replace existing ai-review block with updated version
                return

            # Append to existing hook
            with open(hook_path, 'a', encoding="utf-8") as f:
                f.write("\n\n" + new_content)
        else:
            with open(hook_path, 'w', encoding="utf-8") as f:
                f.write(new_content)

        # Make executable (non-Windows)
        if os.name != 'nt':
            os.chmod(hook_path, os.stat(hook_path).st_mode | stat.S_IEXEC)

    def uninstall(self):
        """Remove ai-review from git hooks"""
        for hook_name in ["pre-commit", "post-commit"]:
            hook_path = os.path.join(self.hooks_dir, hook_name)
            if not os.path.exists(hook_path):
                continue

            with open(hook_path, 'r', encoding="utf-8") as f:
                content = f.read()

            # Remove ai-review sections
            lines = content.split('\n')
            new_lines = []
            skip = False

            for i, line in enumerate(lines):
                if "# ai-review" in line:
                    skip = True
                    continue
                elif skip and line.strip() == "":
                    skip = False
                    continue
                elif not skip:
                    new_lines.append(line)

            if new_lines != lines:
                with open(hook_path, 'w', encoding="utf-8") as f:
                    f.write('\n'.join(new_lines))

        print("✅ ai-review hooks removed successfully!")
