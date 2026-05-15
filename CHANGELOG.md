# Changelog

## v0.2.0 (2025-05-15)

### New Features

- **Smart file grouping** (`diff_utils.py`): Large files (>200 lines) get individual LLM requests; small files are merged into batched requests (up to 15 files / 500 lines per batch). Solves timeout on large changesets and batch renames.
- **Sandwich diff truncation**: When a diff exceeds size limits, preserves head + tail while summarizing the middle with add/remove line counts. Prevents losing critical context at file boundaries.
- **Auto .gitignore management**: `ai-review init` now automatically adds generated files to `.gitignore` (memory, suppressions, reports) while keeping `rules/` versioned for team sharing.
- **Early termination on LLM failure**: After first LLM connection failure, remaining batches are skipped instead of timing out individually.

### Changes

- **Default timeout increased**: balanced mode 30s → 60s, strict mode 60s → 90s. Prevents false-negatives on slower LLM responses.
- **Pre-commit review**: Now uses grouped file review instead of single combined request. Each file or batch is reviewed independently.
- **Post-commit review**: Now uses grouped file review with higher limits (300-line threshold, 2000-line batches, 20 files per batch).
- **56 unit tests** covering diff truncation, file grouping, extreme scenarios (1000-file batch renames, 5000-line single files), and integration tests with real git repos.

### Bug Fixes

- Fixed `UnboundLocalError` for `ReviewParser` caused by duplicate local import in cli.py
- Fixed Windows encoding crash in integration tests (subprocess using GBK instead of UTF-8)
- Fixed pre-commit timeout when reviewing 10+ files — each file no longer waits for full timeout on LLM failure


## v0.1.0 (2025-04-20)

### Initial Release

- Pre-commit fast screening via LLM (blocks on ERROR/CRITICAL)
- Post-commit async full review with report generation
- Custom YAML rule system with file extension matching
- Memory system with risk scores, suppression, and decay
- Notification center: terminal inbox + HTML dashboard + system notifications
- LLM backends: Ollama and OpenAI-compatible APIs (智谱 GLM, DeepSeek, etc.)
- Balanced / Strict modes with layered configuration
