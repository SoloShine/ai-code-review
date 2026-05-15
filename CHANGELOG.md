# Changelog

## v0.2.3 (2025-05-15)

### Bug Fixes

- **BUG-9 (高优先级)**: `ai-review init` 未检测 `core.hookspath` 配置，导致 hook 静默不生效。当项目配置了 `core.hookspath`（如使用 husky、lefthook 等工具），ai-review 仍将 hook 安装到 `.git/hooks/`，但 Git 实际查找 `core.hookspath` 指定的目录
  - 现在 `init` 自动检测 `core.hookspath`，将 hook 安装到正确的目录
  - 安装路径信息明确输出给用户

### Changes

- **Hook 脚本动态路径查找**: hook 脚本不再仅依赖安装时的硬编码绝对路径，增加了回退查找链：
  1. 安装时解析的路径
  2. `command -v ai-review` 动态查找
  3. `python -m ai_review.cli` 最终回退
  - 解决 Python 重装、虚拟环境切换后 hook 失效的问题
- **已有 hook 合并改进**: 检测到已有 hook 时自动追加而非覆盖；检测到已有 ai-review 段落时智能替换更新


## v0.2.2 (2025-05-15)

### Changes

- **Prompt 智能预算分配**: full 模式 prompt 不再硬截断规则文本，改为按规则边界截断
  - 规则按 severity 排序（critical > error > warning > info），优先保留高优先级规则
  - 每条规则保持完整，不会从中间截断
  - 预算分配：context 4000 字符 / rules 6000 字符 / warnings 1500 字符 / diff 15000 字符
- **max_tokens 默认值提升**: 8000 → 16000，给 reasoning 模型更多输出空间


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
