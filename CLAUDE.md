# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI-powered code review CLI tool (`ai-review`) that integrates with Git hooks. Reviews code changes via LLM backends (Ollama or OpenAI-compatible APIs like Zhipu GLM, DeepSeek). Written in Chinese-language UI. All user-facing strings and prompts are in Chinese.

## Build & Install

```bash
pip install -e .                    # Install in editable mode
ai-review --help                    # Verify installation
pytest                              # Run all tests (56 tests in tests/)
pytest tests/test_grouping.py -v    # Run a specific test file
python -m ai_review                 # Does NOT work — use the entry point: ai-review
```

Requires Python >= 3.10. Core dependencies: typer, httpx, pyyaml, rich. Dev deps: pytest>=7.0, pytest-mock>=3.10.

## Architecture

### Two-Phase Review Pipeline

1. **Pre-commit (fast screen)**: `FastScreener` in `reviewer/screener.py` — splits diff by file, groups large files individually and small files together, reviews each batch via LLM. Only ERROR/CRITICAL rules, short prompt. Blocks commit on blocking issues. Auto-passes if LLM fails or times out (never blocks on infrastructure failure). LLM failure on one batch skips remaining batches.

2. **Post-commit (async full review)**: Runs in background after commit via `nohup` in the post-commit hook. Uses same smart grouping with higher limits. Full prompt with all rules, memory reminders, generates JSON+MD reports, sends system notifications, opens HTML dashboard.

The `check` command has three modes: `--pre-commit` (fast), `--async --commit <sha>` (post-commit), or default (manual full review of staged changes).

### Key Module Relationships

```
cli.py ─→ config.py (resolve_config: mode defaults → global ~/.ai-review/config.yaml → project .ai-review.yaml)
  ├─→ diff_utils.py (split_diff_by_file, group_files_for_review, truncate_diff, truncate_single_file_diff)
  ├─→ llm/{base,ollama,openai}.py (LLMProvider ABC, two implementations)
  ├─→ rules/loader.py (RuleEngine: loads YAML from .ai-review/rules/, matches by file extension/severity)
  ├─→ rules/formatter.py (formats rules into prompt text)
  ├─→ prompt/builder.py (PromptBuilder: assembles final prompt — "fast" or "full" mode, both request JSON output)
  ├─→ reviewer/screener.py (FastScreener: smart grouped pre-commit screen)
  ├─→ reviewer/parser.py (ReviewParser: JSON-first parsing of LLM output, text fallback)
  ├─→ memory/store.py (ReviewMemory: risk scores, suppression, decay, reminders — persisted to .ai-review/memory.json)
  ├─→ inbox.py (InboxManager: report registry with read/unread state, shares memory.json)
  ├─→ dashboard.py (generates self-contained HTML dashboard from report JSON files)
  ├─→ hooks/installer.py (HookInstaller: writes pre-commit/post-commit scripts inline into .git/hooks/)
  └─→ output/notify.py (SystemNotifier: cross-platform desktop notifications)
```

### Smart File Grouping (`diff_utils.py`)

- `split_diff_by_file(diff)` → list of `FileDiff` objects
- `group_files_for_review(file_diffs)` → batches: files with `line_count > 200` get individual batches; small files are merged (up to 15 files / 500 lines per batch)
- `truncate_diff(diff)` → sandwich truncation: preserves head 60% + tail 40%, middle summarized with add/remove counts; three phases: file count limit → per-file sandwich → hard char limit
- Pre-commit uses: threshold=200, max_lines=500, max_files=15
- Post-commit uses: threshold=300, max_lines=2000, max_files=20

### Prompt Budget Allocation (`prompt/builder.py`)

Full mode prompt uses smart budget allocation with rule-boundary truncation:
- Context: 4000 chars (truncated at line boundaries)
- Rules: 6000 chars (truncated at rule boundaries via `---` separator; rules sorted by severity — critical first)
- Warnings: 1500 chars (line-boundary truncation)
- Diff: 15000 chars hard limit (should already be truncated by caller)
- Rules are never cut mid-rule; low-severity rules are dropped whole when budget exceeded.

### Configuration Layering

`resolve_config()` in `config.py` merges three layers: mode defaults (strict/balanced) → `~/.ai-review/config.yaml` → project `.ai-review.yaml`. Mode defaults define timeout, block_on severity, post-commit enabled/disabled, and memory settings. The `AI_REVIEW_MODE` env var overrides the mode.

### Default Timeouts

- **balanced**: pre-commit 60s, post-commit enabled
- **strict**: pre-commit 90s, post-commit disabled

### .gitignore Management

`ai-review init` calls `_update_gitignore()` which adds entries for generated files (memory.json, suppressions.json, reports/) while keeping `rules/` versioned for team sharing. Idempotent — won't add duplicate entries.

### Hook Installation

`HookInstaller` in `hooks/installer.py` resolves the git directory via `_resolve_git_dir()` which handles three cases: normal repo (`.git/` is a dir), submodule/worktree (`.git` is a file with `gitdir:` pointer), and fallback via `git rev-parse --git-dir`. It also detects `core.hookspath` via `_get_core_hookspath()` — if set (e.g. by husky, lefthook), hooks are installed to that directory instead of `.git/hooks/`. Hook scripts include a three-level path fallback chain: resolved install path → `command -v ai-review` → `python -m ai_review.cli`. Existing hooks are detected and ai-review content is appended rather than overwriting.

### LLM Provider Abstraction

`LLMProvider` (abstract base in `llm/base.py`) defines `review(prompt, timeout) → LLMResponse`. Two implementations:
- `OllamaProvider` — local model via HTTP
- `OpenAICompatibleProvider` — any OpenAI-compatible API. `_get_chat_url()` handles `/v1`, `/v4` suffixes automatically. API key read from env var specified in config (`api_key_env` field). `max_tokens` is configurable (default 16000) via `OpenAICompatibleConfig.max_tokens`.

### Rule System

Rules are YAML files in `.ai-review/rules/`. Each file has a `rules:` list; each rule has `id`, `title`, `severity` (critical/error/warning/info), `applies_to.extensions`, and `description`. Four severity levels supported. `RuleEngine.match()` filters by changed file extensions and optional severity filter. When `severity_filter` is `["error"]`, `critical` rules are also matched (critical ≥ error). The prompt builder includes matched rules in the LLM prompt.

### Memory System

`ReviewMemory` in `memory/store.py` tracks per-file warning history in `.ai-review/memory.json`. Calculates risk scores (0–10). Reminder levels decay: full → short → minimal → suppressed as `remind_count` increases. Supports manual suppression (`ai-review suppress`) with fuzzy matching (exact → substring → keyword extraction). Warnings decay after 30 days.

### Report & Inbox

Reports saved as JSON+MD pairs in `.ai-review/reports/`. `InboxManager` tracks read/unread state. `dashboard.py` generates a self-contained `index.html` with inline CSS/JS.

## Key Design Decisions

- **LLM failure = auto-pass**: Pre-commit never blocks on LLM timeout/error. Fail-open, not fail-closed.
- **Early termination on LLM failure**: After first LLM connection failure, remaining batches are skipped (`llm_failed` flag in screener).
- **JSON-first LLM output**: Both fast and full prompts request strict JSON format. Parser tries JSON extraction first (handles markdown code block wrapping), falls back to regex text parsing.
- **Smart grouping over single request**: Large files reviewed individually for quality; small files merged for efficiency. Batch renames handled gracefully.
- **Hook scripts resolve command path at install time**: `_find_ai_review_cmd()` writes the full path into hook scripts, avoiding PATH issues in minimal shell environments. Scripts include a runtime fallback chain (`command -v` → `python -m`) in case the install-time path becomes stale.
- **Submodule-aware hook installation**: `_resolve_git_dir()` reads `gitdir:` files and falls back to `git rev-parse`, supporting submodules and worktrees.
- **core.hookspath detection**: `_get_core_hookspath()` checks if the project uses a custom hook directory (husky, lefthook, etc.). If set, hooks install there instead of `.git/hooks/`.
- **Hook merge, not overwrite**: When a pre-commit hook already exists, ai-review content is appended. If ai-review content already exists, it's replaced with updated version.
- **Rule-boundary truncation**: Prompt builder truncates rules at `---` boundaries, sorted by severity. Never cuts mid-rule.
- **Four-level severity**: Rules support critical/error/warning/info. The `error` severity filter implicitly matches `critical` (critical ≥ error).
- **Hook scripts are inline**: `HookInstaller` embeds shell scripts as string constants, no external template files.
- **Rules search path**: `.ai-review/rules/` first, then any dirs in config `rules.dirs`.
- **`async_reviewer.py` is unused**: The async review logic is implemented directly in `cli.py` rather than through this module. It has known bugs and is effectively dead code.
- **`context/auto.py` and `output/terminal.py` are unused**: Written but not yet integrated into the review flow.
- **Windows encoding**: `cli.py` reconfigures stdout/stderr to UTF-8 at startup; all `subprocess.run` calls use `encoding="utf-8"`.

## CLI Entry Points

Defined in `pyproject.toml` under `[project.scripts]`:
- `ai-review` → `ai_review.cli:app` (typer app)

Main commands: `init`, `check`, `suppress`, `status`, `config-show`, `inbox` (sub-app in `cli_inbox.py`).

## Known Issues & Incomplete Work

- `reviewer/async_reviewer.py` is dead code with bugs — actual async logic lives in `cli.py`
- `context/auto.py` (AutoContextCollector) is not wired into full reviews
- `output/terminal.py` (Rich terminal formatting) is not used — output goes through `typer.echo`
- Memory `decay()` is implemented but never auto-triggered
- Post-commit hook uses `nohup ... &` which may not work on Windows
