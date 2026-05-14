"""
Git Hook Installer - Installs pre-commit and post-commit hooks for ai-review
"""
import os
import shutil
from pathlib import Path
import stat

class HookInstaller:
    def __init__(self, repo_root: str):
        self.repo_root = repo_root
        self.hooks_dir = os.path.join(repo_root, ".git", "hooks")

    HOOK_SCRIPTS = {
        "pre-commit": """#!/bin/sh
# ai-review pre-commit hook
ai-review check --pre-commit
exit $?
""",
        "post-commit": """#!/bin/sh
# ai-review post-commit hook - async review
COMMIT_SHA=$(git rev-parse HEAD)
(ai-review check --async --commit "$COMMIT_SHA" > /dev/null 2>&1 &)
""",
    }

    def install(self):
        """Install pre-commit and post-commit hooks"""
        # Create hooks directory if it doesn't exist
        os.makedirs(self.hooks_dir, exist_ok=True)

        # Install each hook
        self._install_hook("pre-commit")
        self._install_hook("post-commit")

        print("✅ Git hooks installed successfully!")

    def _install_hook(self, hook_name: str):
        """Install a single hook, preserving existing content"""
        hook_path = os.path.join(self.hooks_dir, hook_name)
        new_hook_content = self.HOOK_SCRIPTS[hook_name]

        # Check if hook already exists and contains ai-review
        if os.path.exists(hook_path):
            with open(hook_path, 'r') as f:
                existing_content = f.read()

            # If already contains ai-review, we don't need to do anything
            if "ai-review" in existing_content:
                return

            # Create backup
            backup_path = hook_path + ".backup"
            shutil.copy2(hook_path, backup_path)

            # Append new hook to existing
            with open(hook_path, 'a') as f:
                f.write("\n\n" + new_hook_content)
        else:
            # Create new hook file
            with open(hook_path, 'w') as f:
                f.write(new_hook_content)

        # Make hook executable (non-Windows systems)
        if os.name != 'nt':  # nt = Windows
            current_mode = os.stat(hook_path).st_mode
            os.chmod(hook_path, current_mode | stat.S_IEXEC)

    def uninstall(self):
        """Remove ai-review from git hooks"""
        hook_names = ["pre-commit", "post-commit"]

        for hook_name in hook_names:
            hook_path = os.path.join(self.hooks_dir, hook_name)

            if not os.path.exists(hook_path):
                continue

            # Read existing hook
            with open(hook_path, 'r') as f:
                content = f.read()

            # Remove ai-review sections
            lines = content.split('\n')
            new_lines = []
            skip = False
            skip_start = None

            for i, line in enumerate(lines):
                if "# ai-review" in line:
                    if not skip:
                        skip = True
                        skip_start = i
                    continue
                elif skip and line.strip() == "" and i > skip_start + 1:
                    # Check if next line is not part of our script
                    if i < len(lines) - 1 and "ai-review" not in lines[i + 1]:
                        skip = False
                elif not skip:
                    new_lines.append(line)

            # Write back if changed
            if new_lines != lines:
                with open(hook_path, 'w') as f:
                    f.write('\n'.join(new_lines))

        print("✅ ai-review hooks removed successfully!")

def main():
    """Main entry point for hook installation"""
    import typer

    app = typer.Typer()

    @app.command()
    def install(repo_root: str = typer.Option(".", help="Repository root directory")):
        """Install ai-review git hooks"""
        try:
            installer = HookInstaller(repo_root)
            installer.install()
        except Exception as e:
            print(f"❌ Failed to install hooks: {e}", file=sys.stderr)
            raise typer.Exit(1)

    @app.command()
    def uninstall(repo_root: str = typer.Option(".", help="Repository root directory")):
        """Uninstall ai-review git hooks"""
        try:
            installer = HookInstaller(repo_root)
            installer.uninstall()
        except Exception as e:
            print(f"❌ Failed to uninstall hooks: {e}", file=sys.stderr)
            raise typer.Exit(1)

    app()

if __name__ == "__main__":
    main()