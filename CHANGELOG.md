# Changelog

## v0.2.1 (2025-05-15)

### Bug Fixes

- **BUG-1 (崩溃)**: `parser.py` 文本解析分支缺少 `highlights=[]`，LLM 返回非 JSON 时 `TypeError` 崩溃
- **BUG-2**: Git Submodule / Worktree 下 `.git` 是文件不是目录，hooks 安装失败。改用 `gitdir:` 文件解析 + `git rev-parse --git-dir` 回退
- **BUG-3+4**: Hook 脚本在最小化 shell 环境中找不到 `ai-review` 命令。`init` 时写入 `ai-review` 完整路径（解析 pip 安装位置）
- **BUG-5**: 规则引擎不接受 `severity: "critical"`。统一支持 critical / error / warning / info 四级，且 `error` filter 自动匹配 `critical`

### Changes

- **ISSUE-6**: Full 模式 prompt 过大导致 reasoning 模型超时。context_text 和 rules_prompt 各截断至 3000 字符
- **ISSUE-7**: `max_tokens` 硬编码 4000 改为可配置（默认 8000），通过 `.ai-review.yaml` 的 `llm.openai_compatible.max_tokens` 设置


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
