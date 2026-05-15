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


def _get_core_hookspath(repo_root: str) -> str | None:
    """Check if core.hookspath is configured. Returns the path or None."""
    try:
        result = subprocess.run(
            ["git", "config", "core.hookspath"],
            cwd=repo_root, capture_output=True, text=True, encoding="utf-8"
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    return None


def _resolve_hookspath_dir(repo_root: str, hookspath: str) -> str:
    """Resolve core.hookspath to an absolute directory."""
    if os.path.isabs(hookspath):
        return hookspath
    return os.path.normpath(os.path.join(repo_root, hookspath))


class HookInstaller:
    def __init__(self, repo_root: str):
        self.repo_root = repo_root
        self.git_dir = _resolve_git_dir(repo_root)
        self.hookspath = _get_core_hookspath(repo_root)

        # Determine where to install hooks
        if self.hookspath:
            self.hooks_dir = _resolve_hookspath_dir(repo_root, self.hookspath)
            self._hookspath_detected = True
        else:
            self.hooks_dir = os.path.join(self.git_dir, "hooks")
            self._hookspath_detected = False

    def _build_hook_scripts(self) -> dict:
        """Build hook scripts with dynamic path lookup."""
        cmd = _find_ai_review_cmd()

        # Use the resolved path in a fallback chain
        if " " in cmd:
            # e.g. "python.exe -m ai_review.cli" — already a fallback
            invoke = cmd
        else:
            invoke = cmd

        return {
            "pre-commit": f"""#!/bin/sh
# ai-review pre-commit hook
# Dynamically resolve ai-review command path
_ai_review_cmd="{invoke}"
if [ ! -f "$_ai_review_cmd" ] && [ ! -x "$_ai_review_cmd" ]; then
    _ai_review_cmd=$(command -v ai-review 2>/dev/null)
fi
if [ -z "$_ai_review_cmd" ]; then
    _ai_review_cmd="{sys.executable.replace(chr(92), '/')} -m ai_review.cli"
fi
"$_ai_review_cmd" check --pre-commit
exit $?
""",
            "post-commit": f"""#!/bin/sh
# ai-review post-commit hook - async review
COMMIT_SHA=$(git rev-parse HEAD)
_ai_review_cmd="{invoke}"
if [ ! -f "$_ai_review_cmd" ] && [ ! -x "$_ai_review_cmd" ]; then
    _ai_review_cmd=$(command -v ai-review 2>/dev/null)
fi
if [ -z "$_ai_review_cmd" ]; then
    _ai_review_cmd="{sys.executable.replace(chr(92), '/')} -m ai_review.cli"
fi
("$_ai_review_cmd" check --async --commit "$COMMIT_SHA" > /dev/null 2>&1 &)
""",
        }

    def install(self):
        """Install pre-commit and post-commit hooks"""
        # If core.hookspath is detected, install there and warn about it
        if self._hookspath_detected:
            print(f"ℹ️  Detected core.hookspath={self.hookspath}")
            print(f"   Installing hooks to {self.hooks_dir} (core.hookspath directory)")
        else:
            # Check if core.hookspath points somewhere but we're installing to .git/hooks/
            # This means hooks in .git/hooks/ won't be executed — warn the user
            pass

        os.makedirs(self.hooks_dir, exist_ok=True)

        hook_scripts = self._build_hook_scripts()

        for hook_name in hook_scripts:
            self._install_hook(hook_name, hook_scripts[hook_name])

        print(f"✅ Git hooks installed to {self.hooks_dir}")

        # If we installed to .git/hooks/ but core.hookspath is set elsewhere,
        # that's already handled above. But double-check edge case:
        # core.hookspath was empty during __init__ but is now set (race condition)
        current_hookspath = _get_core_hookspath(self.repo_root)
        if current_hookspath and not self._hookspath_detected:
            custom_dir = _resolve_hookspath_dir(self.repo_root, current_hookspath)
            if os.path.normpath(self.hooks_dir) != os.path.normpath(custom_dir):
                print(f"")
                print(f"⚠️  WARNING: core.hookspath is set to '{current_hookspath}'")
                print(f"   Hooks were installed to {self.hooks_dir} but Git will look in {custom_dir}")
                print(f"   The hooks will NOT be executed by Git.")
                print(f"")
                print(f"   Options:")
                print(f"   1. Remove: git config --unset core.hookspath")
                print(f"   2. Re-run: ai-review init (will auto-detect core.hookspath)")

    def _install_hook(self, hook_name: str, new_content: str):
        """Install a single hook, preserving existing content."""
        hook_path = os.path.join(self.hooks_dir, hook_name)

        if os.path.exists(hook_path):
            with open(hook_path, 'r', encoding="utf-8") as f:
                existing = f.read()

            if "ai-review" in existing:
                # Replace existing ai-review block with updated version
                # Extract the new ai-review section
                new_lines = new_content.strip().split('\n')
                old_lines = existing.split('\n')

                # Find and remove old ai-review section
                filtered = []
                in_ai_review = False
                for line in old_lines:
                    if "# ai-review" in line:
                        in_ai_review = True
                        continue
                    if in_ai_review:
                        # End of ai-review section: empty line or next section
                        if line.strip() == "" or (not line.startswith(' ') and line.strip()):
                            in_ai_review = False
                            # Don't skip this line, it belongs to the next section
                            if line.strip():
                                filtered.append(line)
                        continue
                    filtered.append(line)

                # Append new ai-review content
                result = '\n'.join(filtered).rstrip('\n')
                result += '\n\n' + new_content.strip() + '\n'

                with open(hook_path, 'w', encoding="utf-8") as f:
                    f.write(result)
                return

            # Existing hook without ai-review — append
            with open(hook_path, 'a', encoding="utf-8") as f:
                f.write("\n\n" + new_content)
            print(f"   ℹ️  Appended ai-review to existing {hook_name} hook")
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
